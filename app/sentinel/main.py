"""Sentinel: the front door and the sole permission authority.

* Serves the web UI and reverse-proxies /api/* to the Agent Runtime.
* /internal/* is for the runtime only (RUNTIME_TOKEN): tool catalog, act, audit, notify.
* /sentinel/api/* is for the user (via the Olares entrance): approvals, connections,
  credentials, audit, browser live view / takeover.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.common.util import VERSION, token_ok, truncate
from app.sentinel import actions, guard, ledger, mailboxes, suggest, mailproviders, mcp_hub, watchers
from app.sentinel.actions import ActionError
from app.sentinel.catalog import TOOLS, llm_schemas
from app.sentinel.policy import ALLOW, ASK, DENY, PER_USE_TOOLS, decide
from app.sentinel.store import Store
from app.sentinel.telegram_bot import TelegramBot
from app.sentinel import phone
from app.sentinel import dialmcp, mcp_oauth
from app.sentinel import billing
from app.sentinel import passwd
from app.sentinel import vault

SDATA = os.environ.get("SENTINEL_DATA", "/sdata")
RUNTIME_URL = os.environ.get("RUNTIME_URL", "http://127.0.0.1:8081")
RUNTIME_TOKEN = os.environ.get("RUNTIME_TOKEN", "")
WEB_DIR = os.environ.get("WEB_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))
SHOTS = os.path.join(SDATA, "shots")
EDITABLE = {"phone_call": ["purpose"], "gmail_send": ["to", "cc", "subject", "body"], "gmail_reply": ["to", "cc", "subject", "body"],
            "gmail_create_draft": ["to", "cc", "subject", "body"], "gmail_forward": ["to", "note"],
            "browser_type": ["text"], "browser_click_at": ["text"], "gmail_unsubscribe": ["message_ids"], "slack_send_message": ["text"],
            "notion_create_page": ["title", "content"], "notion_append": ["content"],
            "calendar_create_event": ["title", "start", "end", "location", "description"],
            "calendar_update_event": ["title", "start", "end", "location", "description"]}
CONNECTORS = ("gmail", "browser", "telegram", "notion", "slack", "calendar", "phone")
SCOPE_TTL = {"SESSION": 8 * 3600, "PERMANENT": None, "TASK": None}

store: Store = None  # type: ignore
proxy_client: httpx.AsyncClient = None  # type: ignore
bot: TelegramBot = None  # type: ignore
_resolving: set[str] = set()   # approvals being resolved right now (web + Telegram may race)


@asynccontextmanager
async def lifespan(app):
    global store, proxy_client, bot
    os.makedirs(SHOTS, exist_ok=True)
    from app.common import stallwatch
    stallwatch.start(SDATA, "sentinel")
    store = Store(SDATA)
    # keep-alive shorter than uvicorn's (5 s): reusing a connection the runtime is closing gave sporadic 503s
    proxy_client = httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0), limits=httpx.Limits(keepalive_expiry=3.0))
    store.audit("sentinel", "sentinel.start", detail={"version": VERSION})
    try:
        mcp_hub.sync_catalog(store)
    except Exception as e:  # never block startup on a bad MCP config
        store.audit("sentinel", "mcp.sync", result="error", detail={"error": repr(e)[:300]})
    bot = TelegramBot(store, RUNTIME_URL, resolve_core)
    if os.environ.get("TELEGRAM_BOT", "1") != "0":
        bot.start()
    voice_server = None
    if os.environ.get("VOICE_PORT", "8083") != "0":
        import uvicorn
        from app.sentinel import voice_app
        voice_app.STATE["store"] = store
        voice_server = uvicorn.Server(uvicorn.Config(voice_app.app, host="0.0.0.0", port=int(os.environ.get("VOICE_PORT", "8083")),
                                                     proxy_headers=True, forwarded_allow_ips="*", log_level="warning",
                                                     ws_max_size=1 << 20))
        voice_server.install_signal_handlers = lambda: None
        asyncio.create_task(voice_server.serve())
    yield
    if voice_server:
        voice_server.should_exit = True
    await bot.stop()
    for sid in list(mcp_hub._sessions):
        await mcp_hub._drop(sid)
    await proxy_client.aclose()


app = FastAPI(lifespan=lifespan, title="OMuse Sentinel")


# ================================================================== auth helpers
def runtime_auth(x_persona_runtime: str | None = Header(default=None)):
    if not token_ok(x_persona_runtime, RUNTIME_TOKEN):
        raise HTTPException(401, "runtime token required")


def ui_auth(request: Request, x_persona_ui: str | None = Header(default=None)):
    """User endpoints: must come through the web UI (custom header => no cross-site form posts)."""
    if request.method not in ("GET", "HEAD") and x_persona_ui != "1":
        raise HTTPException(403, "UI header required")
    origin = request.headers.get("origin")
    if origin and request.method not in ("GET", "HEAD"):
        host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
        if origin.split("://", 1)[-1].split("/")[0] != host.split(",")[0].strip():
            raise HTTPException(403, "cross-origin request rejected")


async def notify_runtime(path: str, payload: dict):
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            await c.post(RUNTIME_URL + path, json=payload, headers={"X-Persona-Runtime": RUNTIME_TOKEN})
    except Exception as e:
        store.audit("sentinel", "runtime.notify_failed", resource=path, result="error", detail={"error": str(e)[:200]})


async def notify_phone(text: str):
    """Best-effort Telegram push for approvals / takeover requests."""
    conn = store.connection("telegram")
    if conn["enabled"] and conn["config"].get("notify_approvals", True) and store.has_secret("cred_telegram_1"):
        try:
            await actions.telegram_send(store, text)
        except Exception:
            pass


async def _safe(coro):
    try:
        await coro
    except Exception as e:
        store.audit("sentinel", "telegram.send_failed", result="error", detail={"error": str(e)[:300]})


def gmail_ready() -> bool:
    return bool(mailboxes.ready_accounts(store))


def _from_account(tool: str, args: dict) -> str:
    """Which mailbox an outgoing email will be sent from (shown in the approval so nobody sends as the wrong you)."""
    try:
        rid = args.get("reply_to_message_id") or (args.get("message_id") if tool in ("gmail_reply", "gmail_forward") else None)
        if rid:
            aid, _ = mailboxes.split_id(str(rid))
            acc = mailboxes.find(store, aid)
        else:
            acc = mailboxes.find(store, args.get("from_account"))
        return acc["email"] if acc else str(args.get("from_account") or "")
    except Exception:
        return ""


def _safe_args(tool: str, args: dict) -> dict:
    out = {}
    for k, v in (args or {}).items():
        out[k] = truncate(v, 2000) if isinstance(v, str) else v
    return out


# ================================================================== internal API (runtime only)
@app.get("/internal/catalog", dependencies=[Depends(runtime_auth)])
async def catalog():
    enabled = set()
    status = {}
    for name in CONNECTORS:
        c = store.connection(name)
        ready = c["enabled"]
        if name in ("notion", "slack", "calendar"):
            ready = ready and store.has_secret(f"cred_{name}_1")
        if name == "gmail":
            ready = ready and gmail_ready()
        if name == "telegram":
            ready = ready and store.has_secret("cred_telegram_1") and bool(c["config"].get("chat_id"))
        if name == "phone":
            ready = ready and phone.ready(store)
        if ready:
            enabled.add(name)
        status[name] = {"ready": bool(ready), "permissions": c["permissions"],
                        "workspace": c["config"].get("workspace") or c["config"].get("team") or "" if name in ("notion", "slack") else "",
                        "account": c["config"].get("email", "") if name in ("gmail", "calendar") else "",
                        "time_zone": c["config"].get("time_zone", "") if name == "calendar" else "",
                        "read_only": actions.calendar_read_only(store) if name == "calendar" else False,
                        "lines": phone.lines_summary(store) if name == "phone" and ready else "",
                        "accounts": [a["email"] for a in sorted(mailboxes.ready_accounts(store), key=lambda a: a["id"] != mailboxes.default_id(store))] if name == "gmail" else [],
                        "providers": {a["email"]: mailproviders.label(a["provider"]) for a in mailboxes.ready_accounts(store)} if name == "gmail" else {}}
    status["mcp"] = mcp_hub.status(store)
    enabled |= {f"mcp:{x['id']}" for x in status["mcp"]["servers"] if x["enabled"]}

    def allowed(name: str) -> bool:
        t = TOOLS[name]
        if str(t["connector"]).startswith("mcp:"):
            return True  # sync_catalog only publishes enabled, reviewed, non-"off" tools
        if t["connector"] == "calendar" and t["capability"] == "write" and actions.calendar_read_only(store):
            return False   # read-only iCal feed: don't offer writes the agent can't do
        return bool(store.connection(t["connector"])["permissions"].get(t["capability"]))
    schemas = [s for s in llm_schemas(enabled) if allowed(s["function"]["name"])]
    if not vault.list_items(store):
        schemas = [s for s in schemas if s["function"]["name"] != "browser_fill_secret"]
    return {"tools": schemas, "connections": status,
            "risk": {k: v["risk"] for k, v in TOOLS.items()}}


@app.post("/internal/audit", dependencies=[Depends(runtime_auth)])
async def internal_audit(req: Request):
    b = await req.json()
    actor = str(b.get("actor", "runtime"))
    if actor not in ("runtime", "planner", "executor", "llm", "memory", "scheduler", "subagent", "user"):
        actor = "runtime"
    rec = store.audit(actor, str(b.get("action", ""))[:100], task_id=str(b.get("task_id", "")),
                      resource=str(b.get("resource", ""))[:200], risk=str(b.get("risk", "")),
                      decision=str(b.get("decision", "")), result=str(b.get("result", ""))[:50],
                      detail=b.get("detail") or {})
    return {"seq": rec["seq"]}


@app.post("/internal/notify", dependencies=[Depends(runtime_auth)])
async def internal_notify(req: Request):
    b = await req.json()
    conn = store.connection("telegram")
    if not (conn["enabled"] and store.has_secret("cred_telegram_1")):
        return {"sent": False}
    try:
        await actions.telegram_send(store, str(b.get("text", "")))
        store.audit("sentinel", "notify.telegram", task_id=b.get("task_id", ""), decision=ALLOW, result="success")
        return {"sent": True}
    except ActionError as e:
        return {"sent": False, "error": str(e)}


@app.post("/internal/render_pdf", dependencies=[Depends(runtime_auth)])
async def internal_render_pdf(req: Request):
    """Print a workspace document (Markdown / text / HTML) to PDF on this machine — no online converters."""
    b = await req.json()
    body = {k: str(b.get(k) or "") for k in ("source", "markdown", "output", "title")}
    try:
        r = await actions.broker("POST", "/pdf", body, timeout=150)
    except ActionError as e:
        store.audit("sentinel", "pdf.render", task_id=str(b.get("task_id", "")), resource=body["source"] or "text",
                    result="error", detail={"error": str(e)[:200]})
        return {"error": str(e)}
    store.audit("sentinel", "pdf.render", task_id=str(b.get("task_id", "")), resource=r.get("path", ""), result="success",
                detail={"source": body["source"] or "(text)", "size": r.get("size")})
    return r


@app.post("/internal/market_data", dependencies=[Depends(runtime_auth)])
async def internal_market_data(req: Request):
    """Quotes and price history (Yahoo Finance public chart API, read-only, nothing about the user is sent)."""
    from app.sentinel import market
    b = await req.json()
    syms = [str(s) for s in (b.get("symbols") or []) if str(s).strip()][:8]
    if not syms:
        return {"error": "需要 symbols (give one or more tickers)"}
    try:
        r = await market.fetch(syms, str(b.get("range") or "1y"))
    except market.MarketError as e:
        return {"error": str(e)}
    store.audit("sentinel", "market.data", task_id=str(b.get("task_id", "")), resource=",".join(syms)[:200],
                result="success" if r["results"] else "error", detail={"range": b.get("range"), "errors": r["errors"][:5]})
    return r


@app.post("/internal/fundamentals", dependencies=[Depends(runtime_auth)])
async def internal_fundamentals(req: Request):
    """Valuations (P/E, market cap, dividend yield) and reported quarterly/annual financials — Yahoo Finance, read-only."""
    from app.sentinel import market
    b = await req.json()
    syms = [str(s) for s in (b.get("symbols") or []) if str(s).strip()][:6]
    if not syms:
        return {"error": "需要 symbols (give one or more tickers)"}
    r = await market.fundamentals(syms)
    store.audit("sentinel", "market.fundamentals", task_id=str(b.get("task_id", "")), resource=",".join(syms)[:200],
                result="success" if r["results"] else "error", detail={"errors": r["errors"][:5]})
    return r


@app.post("/internal/browser_release", dependencies=[Depends(runtime_auth)])
async def internal_browser_release(req: Request):
    """A task ended: the browser may recycle its page later (pages of running or waiting tasks are kept)."""
    b = await req.json()
    try:
        await actions.broker("POST", "/agent/release", {"task_id": str(b.get("task_id") or "")}, timeout=10)
    except actions.ActionError:
        pass
    return {"ok": True}


@app.post("/internal/render_png", dependencies=[Depends(runtime_auth)])
async def internal_render_png(req: Request):
    """Turn a chart the runtime drew (SVG) into a PNG in the workspace — rendered on this machine, offline."""
    b = await req.json()
    body = {"svg": str(b.get("svg") or ""), "output": str(b.get("output") or "")}
    try:
        r = await actions.broker("POST", "/png", body, timeout=90)
    except ActionError as e:
        store.audit("sentinel", "chart.render", task_id=str(b.get("task_id", "")), resource=body["output"],
                    result="error", detail={"error": str(e)[:200]})
        return {"error": str(e)}
    store.audit("sentinel", "chart.render", task_id=str(b.get("task_id", "")), resource=r.get("path", ""), result="success",
                detail={"size": r.get("size")})
    return r


@app.post("/internal/compose_image", dependencies=[Depends(runtime_auth)])
async def internal_compose_image(req: Request):
    """Put exact text on a workspace image (poster title, caption, logo wordmark) — rendered by the browser container on
    this machine (it has CJK fonts), offline. Image models get text wrong; this guarantees the letters."""
    b = await req.json()
    body = {k: b.get(k) for k in ("image", "text", "position", "size", "color", "band", "weight", "align", "font", "output", "padding")}
    try:
        r = await actions.broker("POST", "/compose", body, timeout=90)
    except ActionError as e:
        store.audit("sentinel", "image.compose", task_id=str(b.get("task_id", "")), resource=str(b.get("image") or ""),
                    result="error", detail={"error": str(e)[:200]})
        return {"error": str(e)}
    store.audit("sentinel", "image.compose", task_id=str(b.get("task_id", "")), resource=r.get("path", ""), result="success",
                detail={"size": r.get("size")})
    return r


TG_FILE_MAX = 50 * 1024 * 1024   # Telegram Bot API upload limit


@app.post("/internal/send_file", dependencies=[Depends(runtime_auth)])
async def internal_send_file(req: Request):
    """The agent sent a file to the chat. If that chat is the Telegram conversation, also deliver it there —
    only ever to the configured owner chat (the bot never talks to anyone else)."""
    b = await req.json()
    conv, path, name = str(b.get("conv_id", "")), str(b.get("path", "")), str(b.get("name", "")) or "file"
    if not (bot and bot.status.get("running") and conv and conv == (store.kv_get("tg_conv", "") or "")):
        return {"sent": False}
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.get(RUNTIME_URL + "/api/files/raw", params={"path": path, "download": 1})
        if r.status_code != 200:
            return {"sent": False, "error": f"读取文件失败 (HTTP {r.status_code})"}
        if len(r.content) > TG_FILE_MAX:
            return {"sent": False, "error": "文件超过 Telegram 的 50 MB 上限 (over Telegram's 50 MB limit)"}
        await bot.send_document(name, r.content, str(b.get("caption", ""))[:900], str(b.get("mime", "")))
    except Exception as e:
        return {"sent": False, "error": str(e)[:200]}
    store.audit("sentinel", "telegram.send_file", task_id=str(b.get("task_id", "")), resource=name, result="success",
                detail={"size": len(r.content), "path": path})
    return {"sent": True}


@app.post("/internal/expire_approvals", dependencies=[Depends(runtime_auth)])
async def internal_expire_approvals(req: Request):
    """A task ended without the user deciding (cancelled, or superseded by the next scheduled run):
    its pending approvals must not linger — mark them expired so they can no longer be approved."""
    b = await req.json()
    tid, reason = str(b.get("task_id", "")), str(b.get("reason", ""))[:300]
    if not tid:
        return {"expired": 0}
    n = 0
    for ap in store.approvals("pending", 500):
        if ap["task_id"] != tid or ap["id"] in _resolving:
            continue
        store.resolve_approval(ap["id"], "expired", ap.get("scope") or "ONCE", {"status": "expired", "reason": reason},
                               decided_by="system")
        store.audit("sentinel", "approval.expire", task_id=tid, resource=ap["tool"], risk=ap["risk"], decision=DENY,
                    result="expired", detail={"approval_id": ap["id"], "reason": reason})
        n += 1
    # a cancelled task can't use the browser any more: end a takeover of its page, or the browser view stays in
    # "you are in control" with nothing to hand back to (2026-10-05)
    try:
        bst = await actions.broker("GET", "/state", timeout=5)
        if bst.get("mode") == "user" and bst.get("takeover_task") == tid:
            await actions.broker("POST", "/user/release", {}, timeout=10)
            store.audit("sentinel", "browser.release", task_id=tid, result="success", detail={"reason": "task ended"})
    except Exception:
        pass
    return {"expired": n}


@app.get("/internal/ledger", dependencies=[Depends(runtime_auth)])
async def internal_ledger(limit: int = 30, task_id: str = ""):
    return {"orders": ledger.for_task(store, task_id) if task_id else ledger.entries(store, min(limit, 200))}


@app.post("/internal/ledger/confirm", dependencies=[Depends(runtime_auth)])
async def internal_ledger_confirm(req: Request):
    """The runtime reports how a purchase task ended: the order number from its confirmation page, or none."""
    b = await req.json()
    tot = b.get("total")
    out = ledger.confirm(store, str(b.get("task_id") or ""), str(b.get("order_number") or ""),
                         float(tot) if isinstance(tot, (int, float)) else None, b.get("evidence") or None)
    if out:
        store.audit("sentinel", "ledger.confirm", task_id=str(b.get("task_id") or ""), result="success",
                    detail={"orders": [{"id": o["id"], "order_number": o["order_number"], "status": o["status"]} for o in out]})
    return {"orders": out}


def _ledger_search(query: str) -> list[dict]:
    out = []
    for acc in mailboxes.ready_accounts(store):
        try:
            out += actions.gmail_client(store, acc["id"]).search(query, 10)
        except Exception:
            continue
    return out


@app.post("/internal/ledger/backfill", dependencies=[Depends(runtime_auth)])
async def internal_ledger_backfill():
    made = ledger.backfill(store)
    return {"created": made, "tasks": [ledger.get(store, i)["task_id"] for i in made]}


@app.post("/internal/ledger/reconcile", dependencies=[Depends(runtime_auth)])
async def internal_ledger_reconcile():
    res = await asyncio.to_thread(ledger.reconcile, store, _ledger_search)
    if res["changed"]:
        store.audit("sentinel", "ledger.reconcile", result="success", detail=res)
    return res


@app.get("/sentinel/api/grant_suggestions", dependencies=[Depends(ui_auth)])
async def ui_grant_suggestions():
    return {"suggestions": suggest.suggestions(store)}


@app.post("/sentinel/api/grant_suggestions", dependencies=[Depends(ui_auth)])
async def ui_grant_suggestion_decide(req: Request):
    b = await req.json()
    k = str(b.get("key") or "")
    if "|" not in k:
        raise HTTPException(400, "bad key")
    if b.get("accept"):
        days = b.get("days")
        gid = suggest.accept(store, k, float(days) if days else None)
        store.audit("user", "grant.from_suggestion", resource=k.split("|")[0], result="success",
                    detail={"key": k, "grant_id": gid, "days": days})
        return {"ok": True, "grant_id": gid}
    suggest.dismiss(store, k)
    return {"ok": True}


@app.get("/sentinel/api/ledger", dependencies=[Depends(ui_auth)])
async def ui_ledger(limit: int = 100):
    return {"orders": ledger.entries(store, min(limit, 300)), "labels": ledger.LABEL}


@app.post("/sentinel/api/ledger/reconcile", dependencies=[Depends(ui_auth)])
async def ui_ledger_reconcile():
    return await asyncio.to_thread(ledger.reconcile, store, _ledger_search)


@app.get("/internal/mail_check", dependencies=[Depends(runtime_auth)])
async def internal_mail_check():
    """Health check for the connected mailboxes (runtime health watch): sign in to each one and list the inbox."""
    out = []
    for acc in mailboxes.ready_accounts(store):
        try:
            g = actions.gmail_client(store, acc["id"])
            await asyncio.wait_for(asyncio.to_thread(g.test), timeout=40)
            out.append({"email": acc.get("email", ""), "ok": True})
        except Exception as e:
            out.append({"email": acc.get("email", ""), "ok": False, "error": f"{type(e).__name__}: {str(e)[:160]}"})
    return {"accounts": out}


@app.get("/internal/browser_state", dependencies=[Depends(runtime_auth)])
async def internal_browser_state():
    try:
        return await actions.broker("GET", "/state", timeout=10)
    except ActionError as e:
        return {"mode": "unknown", "error": str(e)}


async def _context_for(tool: str, args: dict, task_id: str) -> tuple[dict | None, dict | None]:
    """Ask the broker what a ref points to so the policy can judge the click/type."""
    if tool == "browser_save_media" and not args.get("ref"):
        st = await actions.broker("GET", "/state", timeout=10)
        url = next((x.get("url", "") for x in st.get("tasks") or [] if x.get("task_id") == task_id), st.get("url", ""))
        return None, {"url": url, "title": ""}
    if tool in ("browser_click", "browser_type", "browser_select", "browser_upload", "browser_fill_secret", "browser_save_media"):
        info = await actions.broker("POST", "/agent/describe", {"task_id": task_id, "ref": args.get("ref", "")}, timeout=20)
        return info, {"url": info.get("page_url", ""), "title": info.get("page_title", "")}
    if tool == "browser_click_at":
        info = await actions.broker("POST", "/agent/describe_at", {"task_id": task_id, "x": args.get("x", 0), "y": args.get("y", 0)},
                                    timeout=20)
        return info, {"url": info.get("page_url", ""), "title": info.get("page_title", "")}
    if tool == "browser_press":
        info = await actions.broker("POST", "/agent/focused", {"task_id": task_id}, timeout=20)
        st = await actions.broker("GET", "/state", timeout=10)
        return info, {"url": st.get("url", ""), "title": st.get("title", "")}
    return None, None


async def _summary(tool: str, args: dict, elem: dict | None, page: dict | None) -> dict:
    t = TOOLS[tool]
    s: dict = {"tool": tool, "connector": t["connector"], "fields": [], "editable": EDITABLE.get(tool, [])}
    if tool in ("gmail_send", "gmail_create_draft"):
        s["title"] = "发送邮件 Send email" if tool == "gmail_send" else "创建草稿 Create draft"
        s["fields"] = [["发件账号 From", _from_account(tool, args)], ["收件人 To", args.get("to", "")],
                       ["抄送 Cc", args.get("cc", "")], ["主题 Subject", args.get("subject", "")]]
        s["body"] = args.get("body", "")
    elif tool == "gmail_reply":
        s["title"] = "回复并发送邮件 Reply & send"
        try:
            g, raw = actions.client_for_id(store, str(args.get("message_id", "")))
            d = await asyncio.to_thread(g.reply_defaults, raw, bool(args.get("reply_all")))
            args.setdefault("to", d["to"])
            args.setdefault("cc", d["cc"])
            args.setdefault("subject", d["subject"])
        except Exception as e:
            s["warning"] = f"无法读取原邮件: {e}"
        s["fields"] = [["发件账号 From", _from_account(tool, args)], ["收件人 To", args.get("to", "")],
                       ["抄送 Cc", args.get("cc", "")], ["主题 Subject", args.get("subject", "")]]
        s["body"] = args.get("body", "")
    elif tool == "phone_call":
        cfg = phone.config(store)
        n, line, why = phone.check_call(store, str(args.get("to", "")), cfg)
        mins = max(1, min(int(args.get("max_minutes") or cfg["max_minutes"]), cfg["max_minutes"],
                          10 if line == "dialmcp" else phone.MAX_MINUTES_CAP))
        s["title"] = "打电话 Phone call"
        s["fields"] = [["拨打 To", n or str(args.get("to", ""))], ["来电显示 From", phone.caller_id(store, line, cfg) if line else ""],
                       ["线路 Line", {"dialmcp": "DialMCP（美国/加拿大 US/CA，会录音 recorded）", "telnyx": "Telnyx + OpenAI Realtime"}.get(line, "—")],
                       ["可以告诉对方 May share", args.get("may_share") or "（无 nothing）"],
                       ["语言 Language", args.get("language") or "跟随对方 match them"],
                       ["最长 Max", f"{mins} 分钟 min"],
                       ["今天已拨 Calls today", f"{phone.calls_today(store)} / {cfg['daily_limit']}"]]
        s["body"] = args.get("purpose", "")
        if why:
            s["warning"] = why
    elif tool == "gmail_forward":
        s["title"] = "转发邮件 Forward email"
        s["fields"] = [["发件账号 From", _from_account(tool, args)], ["转发给 To", args.get("to", "")],
                       ["原邮件 ID", args.get("message_id", "")]]
        s["body"] = args.get("note", "")
    elif tool == "gmail_unsubscribe":
        s["title"] = "退订邮件 Unsubscribe"
        ids = [str(x) for x in (args.get("message_ids") or [])][:30]
        try:
            targets = await asyncio.to_thread(actions.unsubscribe_targets, store, ids)
            s["items"] = [{"id": t["id"], "from": t.get("from", ""), "subject": t.get("subject", ""), "account": t.get("account", ""),
                           "date": t.get("date", ""), "method": t.get("method", ""), "error": t.get("error", "")} for t in targets]
        except Exception as e:
            s["warning"] = f"无法读取邮件信息: {e}"
            s["items"] = [{"id": i, "from": "", "subject": "", "method": ""} for i in ids]
        s["fields"] = [["邮件数 Emails", str(len(ids))], ["同时归档 Also archive", "是 Yes" if args.get("archive") else "否 No"]]
    elif tool == "purchase_confirm":
        s["title"] = "确认购买 Confirm purchase"
        cur = str(args.get("currency") or "")
        items = args.get("items") or []
        lines = []
        for it in items[:10]:
            try:
                lines.append(f"{it.get('name', '')} × {it.get('qty', 1)} — {cur} {float(it.get('price', 0)):.2f}")
            except (TypeError, ValueError, AttributeError):
                lines.append(str(it)[:120])
        card = "网站上已保存的卡 card saved on the site"
        if args.get("card_item_id"):
            it = vault.item(store, str(args.get("card_item_id")))
            card = vault.summary_text(it, "number") if it else str(args.get("card_item_id"))
        try:
            ship = f"{cur} {float(args.get('shipping') or 0):.2f}"
            total = f"{cur} {float(args.get('total')):.2f}"
        except (TypeError, ValueError):
            ship, total = str(args.get("shipping", "")), str(args.get("total", ""))
        s["fields"] = [["网站 Site", str(args.get("site", ""))], ["商品 Items", "\n".join(lines)], ["运费 Shipping", ship],
                       ["总价 Total", total], ["送货方式 Delivery", str(args.get("delivery", ""))], ["付款卡 Card", card],
                       ["批准后 After approval", "30 分钟内、仅这个网站：结账、填卡、下单不再逐个审批；页面总价超过上面的金额会再问你 "
                                                "(30 min, this site only; asks again if the page total is higher)"]]
        s["body"] = str(args.get("note", ""))
        s["screenshot"] = True
    elif tool.startswith("browser_"):
        verb = {"browser_click": "点击 Click", "browser_click_at": "按位置点击 Click at position", "browser_type": "输入 Type", "browser_select": "选择 Select",
                "browser_press": "按键 Press key", "browser_upload": "上传文件 Upload", "browser_navigate": "打开网页 Open page",
                "browser_fill_secret": "从保险箱填写 Fill from vault"}
        s["title"] = f"浏览器操作：{verb.get(tool, tool)}"
        s["fields"] = [["网站 Site", (page or {}).get("url") or args.get("url", "")], ["页面 Page", (page or {}).get("title", "")]]
        if elem:
            s["fields"].append(["元素 Element", f"{elem.get('tag', '')} 「{elem.get('name', '')}」"])
        if tool == "browser_click_at":
            s["fields"].append(["位置 Position", f"x={args.get('x')}, y={args.get('y')}"])
            if elem and elem.get("frames"):
                s["fields"].append(["所在框架 Inside iframe", " › ".join(elem["frames"])])
            if args.get("text"):
                s["body"] = args.get("text", "")
                if args.get("submit"):
                    s["fields"].append(["提交 Submit", "输入后按回车 Enter"])
        if tool == "browser_fill_secret":
            s["title"] = "从保险箱填写 Fill from vault"
            it = vault.item(store, str(args.get("item_id", "")))
            if it:
                s["fields"].append(["填写内容 Value", vault.summary_text(it, str(args.get("field", "")))])
            s["fields"].append(["授权 Approval", "仅这一次（每次使用都要批准）Once only"])
        if tool == "browser_type":
            s["body"] = args.get("text", "")
            if args.get("submit"):
                s["fields"].append(["提交 Submit", "输入后按回车 Enter"])
        if tool == "browser_select":
            s["fields"].append(["选项 Option", args.get("value", "")])
        if tool == "browser_press":
            s["fields"].append(["按键 Key", args.get("key", "")])
        if tool == "browser_upload":
            s["fields"].append(["文件 File", args.get("path", "")])
        s["screenshot"] = True
    elif tool == "slack_send_message":
        s["title"] = "发送 Slack 消息 Send Slack message"
        conf = store.connection("slack")["config"]
        s["fields"] = [["工作区 Workspace", conf.get("team", "")], ["频道 Channel", args.get("channel", "")],
                       ["身份 As", f"{'user' if conf.get('token_type') == 'user' else 'bot'} · {conf.get('user', '')}"]]
        if args.get("thread_ts"):
            s["fields"].append(["回复讨论串 Thread", args.get("thread_ts", "")])
        s["body"] = args.get("text", "")
    elif tool.startswith("notion_"):
        s["title"] = {"notion_create_page": "新建 Notion 页面 Create page", "notion_append": "追加到 Notion 页面 Append",
                      "notion_update_page": "修改 Notion 页面 Update page"}.get(tool, tool)
        if args.get("archived"):
            s["title"] = "归档（删除）Notion 页面 Archive page"
        s["fields"] = [["工作区 Workspace", store.connection("notion")["config"].get("workspace", "")],
                       ["页面 Page", args.get("parent_id") or args.get("page_id", "")]]
        if args.get("title"):
            s["fields"].append(["标题 Title", args["title"]])
        for k, v in (args.get("properties") or {}).items():
            s["fields"].append([f"属性 {k}", str(v)[:200]])
        s["body"] = args.get("content", "")
    elif tool.startswith("calendar_"):
        conf = store.connection("calendar")["config"]
        s["title"] = {"calendar_create_event": "新建日程 Create event", "calendar_update_event": "修改日程 Update event",
                      "calendar_delete_event": "删除日程 Delete event"}.get(tool, tool)
        s["fields"] = [["日历 Calendar", f"{conf.get('email', '')} ({args.get('calendar_id') or 'primary'})"]]
        if tool != "calendar_create_event":
            try:
                ev = await asyncio.to_thread(actions.calendar_event, store, str(args.get("event_id", "")), args.get("calendar_id"))
                s["fields"].append(["原日程 Event", f"{ev['title']} · {ev['start']} → {ev['end']}"])
                if ev.get("attendees"):
                    s["fields"].append(["参会人 Attendees", ", ".join(ev["attendees"][:10])])
            except Exception as e:
                s["warning"] = f"无法读取原日程: {e}"
        for label, k in (("标题 Title", "title"), ("开始 Start", "start"), ("结束 End", "end"), ("地点 Location", "location")):
            if args.get(k) or (tool == "calendar_create_event" and k in ("title", "start")):
                s["fields"].append([label, str(args.get(k, ""))])
        if args.get("all_day"):
            s["fields"].append(["全天 All day", "是 Yes"])
        if args.get("attendees"):
            from app.sentinel.gcal import attendees as _att
            s["fields"].append(["邀请 Invite (会发邮件 sends email)", ", ".join(_att(args.get("attendees")))])
        s["fields"].append(["时区 Time zone", args.get("time_zone") or conf.get("time_zone", "")])
        if tool != "calendar_delete_event":
            s["body"] = args.get("description", "")
    elif str(t["connector"]).startswith("mcp:"):
        srv, rec = mcp_hub.tool_info(store, tool)
        sname = srv["name"] if srv else t["connector"][4:]
        tname = (rec or {}).get("title") or (rec or {}).get("name") or tool
        s["title"] = f"MCP · {sname}：{tname}"
        s["fields"] = [["服务 Server", sname], ["工具 Tool", (rec or {}).get("name", tool)],
                       ["类型 Kind", {"read": "只读 read", "write": "写入 write", "destructive": "可能删除/覆盖 destructive"}.get((rec or {}).get("kind"), "")]]
        for k, v in list(args.items())[:12]:
            s["fields"].append([f"参数 {k}", truncate(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str), 300)])
        big = {k: v for k, v in args.items() if isinstance(v, str) and len(v) > 300}
        if big:
            s["body"] = "\n\n".join(f"【{k}】\n{v}" for k, v in big.items())
    else:
        s["title"] = tool
        s["fields"] = [[k, str(v)] for k, v in args.items()]
    if tool in ("gmail_send", "gmail_reply", "gmail_create_draft") and args.get("attachments"):
        s["fields"].append(["附件 Attachments", ", ".join(os.path.basename(str(x)) for x in args["attachments"])])
    return s


@app.post("/internal/act", dependencies=[Depends(runtime_auth)])
async def act(req: Request):
    b = await req.json()
    tool, args = str(b.get("tool", "")), dict(b.get("args") or {})
    task_id, call_id = str(b.get("task_id", "")), str(b.get("call_id", ""))
    if tool not in TOOLS:
        store.audit("sentinel", tool or "unknown", task_id=task_id, decision=DENY, result="denied",
                    detail={"reason": "unknown tool"})
        return {"status": "denied", "reason": f"未知工具 unknown tool {tool}"}
    t = TOOLS[tool]
    elem = page = None
    try:
        if t["connector"] == "browser" and tool not in ("browser_request_takeover", "browser_downloads"):
            elem, page = await _context_for(tool, args, task_id)
    except ActionError as e:
        store.audit("sentinel", tool, task_id=task_id, resource="browser", decision="ERROR", result=e.status,
                    detail={"args": _safe_args(tool, args), "error": str(e)})
        return {"status": e.status, "error": str(e)}

    if tool in ("browser_click", "browser_click_at") and page and store.active_purchase(task_id, guard.domain_of(page.get("url", ""))):
        try:   # a confirmed purchase: check the total the page shows before letting a pay click through
            pt = await actions.broker("POST", "/agent/page_text", {"task_id": task_id}, timeout=15)
            page = {**page, "text": str((pt or {}).get("text") or "")}
        except Exception:
            pass
    order_hits = None
    if tool in ("browser_click", "browser_click_at") and elem and guard.order_change_click(elem.get("name", "")):
        try:   # cancel / return: which order in the ledger is this page about?
            pt = await actions.broker("POST", "/agent/page_text", {"task_id": task_id}, timeout=15)
            txt = str((pt or {}).get("text") or "")
        except Exception:
            txt = ""
        order_hits = ledger.in_text(store, txt + " " + str((page or {}).get("url") or ""))
    d = decide(store, tool, args, task_id, elem=elem, page=page, gmail_ready=gmail_ready())
    detail = {"args": _safe_args(tool, args), "reason": d.reason, "destination": d.destination}
    if elem:
        detail["element"] = {k: elem.get(k) for k in ("tag", "name", "input_type")}
    if d.decision == DENY:
        store.audit("sentinel", tool, task_id=task_id, resource=t["connector"], risk=d.risk, decision=DENY,
                    result="denied", detail=detail)
        return {"status": "denied", "reason": d.reason}
    if b.get("dry_run") and (d.decision == ASK or dry_run_side_effect(tool, t)):
        # golden (test) run: stop where a real run would act or ask — nothing is sent, bought or written, no card
        store.audit("sentinel", tool, task_id=task_id, resource=t["connector"], risk=d.risk, decision=DENY,
                    result="dry_run", detail={**detail, "would": d.decision})
        what = "需要你批准" if d.decision == ASK else "会真正执行"
        return {"status": "denied", "dry_run": True, "reason": f"{TOOLS[tool].get('title') or tool}：{what}（{d.reason[:120]}）"}
    if d.decision == ASK and b.get("no_ask"):
        store.audit("sentinel", tool, task_id=task_id, resource=t["connector"], risk=d.risk, decision=DENY,
                    result="denied", detail={**detail, "why": "needs approval but caller is a sub-agent"})
        return {"status": "denied", "reason": "此操作需要用户审批，子 Agent 不能执行 (needs approval; sub-agents cannot request it)"}
    if d.decision == ASK:
        summary = await _summary(tool, args, elem, page)
        summary["reason"] = d.reason
        summary["destination"] = d.destination
        if order_hits is not None:
            _ledger_summary(summary, order_hits, elem)
        ap = store.create_approval(task_id, call_id, tool, args, summary, d.risk, d.reason)
        if summary.get("screenshot"):
            try:
                img = await actions.broker("GET", f"/screenshot?task_id={task_id}", timeout=20)
                if isinstance(img, (bytes, bytearray)):
                    with open(os.path.join(SHOTS, f"{ap['id']}.jpg"), "wb") as f:
                        f.write(img)
            except Exception:
                pass
        store.audit("sentinel", tool, task_id=task_id, resource=t["connector"], risk=d.risk, decision=ASK,
                    result="pending", detail={**detail, "approval_id": ap["id"]})
        if bot and bot.config():
            asyncio.create_task(_safe(bot.send_approval(ap)))
        else:
            asyncio.create_task(notify_phone(f"OMuse 需要你审批 Approval needed：{summary.get('title')}\n"
                                             f"{d.destination or ''}\n{d.reason}"))
        return {"status": "approval_required", "approval_id": ap["id"], "summary": summary, "reason": d.reason}
    # ALLOW
    return await _run(tool, args, task_id, d.risk, detail, decision=ALLOW)


DRY_RUN_CAPS = {"send", "write", "draft", "organize", "upload", "notify", "call"}
DRY_RUN_TOOLS = {"purchase_confirm", "browser_fill_secret", "browser_request_takeover"}


def dry_run_side_effect(tool: str, t: dict) -> bool:
    """A call a golden (test) run must not make even when policy would allow it."""
    if tool in DRY_RUN_TOOLS:
        return True
    if tool in ("phone_call_status", "phone_hangup"):
        return False
    if str(t.get("connector", "")).startswith("mcp:"):
        return t.get("capability") != "read"
    return t.get("capability") in DRY_RUN_CAPS


@app.post("/internal/user_request", dependencies=[Depends(runtime_auth)])
async def internal_user_request(req: Request):
    """Tasks the runtime starts itself (golden runs) record the request text the way the front door does for chats."""
    b = await req.json()
    if b.get("task_id") and isinstance(b.get("text"), str):
        store.set_user_request(str(b["task_id"]), b["text"][:4000])
    return {"ok": True}


def _ledger_summary(summary: dict, hits: list[dict], elem: dict | None) -> None:
    """Cancel / return approvals name the ledger order they act on (or warn that the page's order is not in it)."""
    summary["ledger_click"] = str((elem or {}).get("name") or "")[:80]
    summary["ledger"] = [{k: h.get(k) for k in ("id", "merchant", "order_number", "total", "currency", "status_label",
                                                 "created_at")} for h in hits[:3]]
    fields = summary.setdefault("fields", [])
    if hits:
        for h in hits[:3]:
            fields.append(["账本订单 Ledger order", f"{h['merchant']} · {h['order_number']} · {h['currency']} {h['total']:.2f} · "
                                                    f"{time.strftime('%Y-%m-%d', time.localtime(h['created_at']))} · {h['status_label']}"])
    else:
        summary["warning"] = ((summary.get("warning") or "") + " 这个页面上的订单号不在 OMuse 的交易账本里：可能不是 OMuse 替你下的单，"
                              "请核对订单号再批准 (the order on this page is not in OMuse's ledger — check it)").strip()


def _ledger_after(tool: str, args: dict, task_id: str, detail: dict, result) -> None:
    """Keep the ledger in step with what was just done."""
    try:
        if tool == "purchase_confirm":
            card = ""
            if args.get("card_item_id"):
                it = vault.item(store, str(args.get("card_item_id")))
                card = vault.summary_text(it, "number") if it else ""
            ledger.add(store, task_id, str((result or {}).get("site") or guard.domain_of(
                           "https://" + str(args.get("site", "")).removeprefix("https://").removeprefix("http://"))),
                       float(args.get("total") or 0), str(args.get("currency") or ""), args.get("items") or [], card,
                       str(args.get("delivery") or ""), str((result or {}).get("purchase_id") or ""),
                       str(detail.get("approval_id") or ""))
        elif tool in ("browser_click", "browser_click_at") and detail.get("approval_id"):
            ap = store.approval(str(detail["approval_id"]))
            hits = ((ap or {}).get("summary") or {}).get("ledger") or []
            name = str(((ap or {}).get("summary") or {}).get("ledger_click") or "")
            st = "return_requested" if re.search(r"return|refund|退货|退款|返品", name, re.I) else "cancel_requested"
            for h in hits:
                ledger.set_status(store, h["id"], st, "user", f"用户批准了「{name or '取消/退货'}」 approval {detail['approval_id']}",
                                  {"kind": "approval", "id": detail["approval_id"]})
    except Exception as e:
        store.audit("sentinel", "ledger.update_failed", task_id=task_id, result="error", detail={"error": repr(e)[:300]})


async def _run(tool: str, args: dict, task_id: str, risk: str, detail: dict, decision: str) -> dict:
    t = TOOLS[tool]
    started = time.time()
    try:
        result = await actions.execute(store, tool, args, task_id)
        _ledger_after(tool, args, task_id, detail, result)
        ms = int((time.time() - started) * 1000)
        store.audit("sentinel", tool, task_id=task_id, resource=t["connector"], risk=risk, decision=decision,
                    result="success", detail={**detail, "ms": ms,
                                              "result_preview": truncate(str(result), 600)})
        return {"status": "ok", "result": result}
    except ActionError as e:
        store.audit("sentinel", tool, task_id=task_id, resource=t["connector"], risk=risk, decision=decision,
                    result=e.status, detail={**detail, "error": str(e)})
        if e.status == "waiting_user":
            if bot and bot.config():
                asyncio.create_task(_safe(bot.send_takeover(str(args.get("reason", "")))))
            else:
                asyncio.create_task(notify_phone(f"OMuse 请求你接管浏览器 Takeover requested：{args.get('reason', '')}"))
        return {"status": e.status, "error": str(e)}
    except Exception as e:  # unexpected
        store.audit("sentinel", tool, task_id=task_id, resource=t["connector"], risk=risk, decision=decision,
                    result="error", detail={**detail, "error": repr(e)[:500]})
        return {"status": "error", "error": f"内部错误 internal error: {str(e)[:300]}"}


# ================================================================== user API: approvals
@app.get("/sentinel/api/approvals", dependencies=[Depends(ui_auth)])
async def list_approvals(status: str | None = None, limit: int = 50):
    return {"approvals": store.approvals(status, limit)}


@app.get("/sentinel/api/approvals/{aid}/screenshot", dependencies=[Depends(ui_auth)])
async def approval_shot(aid: str):
    p = os.path.join(SHOTS, f"{os.path.basename(aid)}.jpg")
    if not os.path.exists(p):
        raise HTTPException(404)
    return FileResponse(p, media_type="image/jpeg")


@app.post("/sentinel/api/approvals/{aid}/resolve", dependencies=[Depends(ui_auth)])
async def resolve(aid: str, req: Request):
    b = await req.json()
    return await resolve_core(aid, b, via="web")


async def resolve_core(aid: str, b: dict, via: str = "web") -> dict:
    """Approve/deny a pending approval. Used by the web UI and the Telegram bot."""
    if aid in _resolving:
        raise HTTPException(409, "这个审批正在处理中 (being resolved)")
    _resolving.add(aid)
    try:
        return await _resolve(aid, b, via)
    finally:
        _resolving.discard(aid)


async def _resolve(aid: str, b: dict, via: str) -> dict:
    ap = store.approval(aid)
    if not ap:
        raise HTTPException(404, "approval not found")
    if ap["status"] != "pending":
        raise HTTPException(409, f"already {ap['status']}")
    decision = b.get("decision")
    scope = str(b.get("scope", "ONCE")).upper()
    if scope not in ("ONCE", "TASK", "SESSION", "TIME_BOUND", "PERMANENT"):
        scope = "ONCE"
    tool, args, task_id = ap["tool"], dict(ap["args"]), ap["task_id"]
    if tool in PER_USE_TOOLS or "spends money" in str(ap.get("reason") or "") or "changes an order" in str(ap.get("reason") or ""):
        scope = "ONCE"     # payments are approved one by one: no 'always allow' for them
    if decision != "approve":
        store.resolve_approval(aid, "denied", scope, {"status": "denied"})
        store.audit("user", "approval.deny", task_id=task_id, resource=tool, risk=ap["risk"], decision=DENY,
                    result="denied", detail={"approval_id": aid, "note": b.get("note", ""), "via": via})
        asyncio.create_task(notify_runtime("/internal/approval_resolved", {
            "approval_id": aid, "task_id": task_id, "call_id": ap["call_id"], "decision": "denied",
            "result": {"status": "denied", "reason": "用户拒绝了此操作 (user denied)" + (f"：{b['note']}" if b.get("note") else "")}}))
        return {"ok": True, "status": "denied"}

    edited = b.get("args") or {}
    for k in EDITABLE.get(tool, []):
        if k in edited and isinstance(edited[k], str):
            args[k] = edited[k]
        elif k == "message_ids" and isinstance(edited.get(k), list):
            keep = {str(x) for x in edited[k]}
            args[k] = [x for x in (args.get(k) or []) if str(x) in keep]  # user may only narrow the list
            if not args[k]:
                store.resolve_approval(aid, "denied", scope, {"status": "denied"})
                store.audit("user", "approval.deny", task_id=task_id, resource=tool, risk=ap["risk"], decision=DENY,
                            result="denied", detail={"approval_id": aid, "note": "no items selected"})
                asyncio.create_task(notify_runtime("/internal/approval_resolved", {
                    "approval_id": aid, "task_id": task_id, "call_id": ap["call_id"], "decision": "denied",
                    "result": {"status": "denied", "reason": "用户取消勾选了所有邮件，没有退订任何一封 (user deselected all)"}}))
                return {"ok": True, "status": "denied"}
    # re-check hard rules (connector may have been disabled meanwhile); approval overrides ASK only
    elem = page = None
    if tool not in TOOLS:
        store.resolve_approval(aid, "denied", scope, {"status": "denied", "reason": "tool no longer available"}, args)
        asyncio.create_task(notify_runtime("/internal/approval_resolved", {
            "approval_id": aid, "task_id": task_id, "call_id": ap["call_id"], "decision": "denied",
            "result": {"status": "denied", "reason": "这个工具已被移除或停用 (tool no longer available)"}}))
        return {"ok": False, "status": "denied", "reason": "tool no longer available"}
    if TOOLS[tool]["connector"] == "browser":
        try:
            elem, page = await _context_for(tool, args, task_id)
        except ActionError:
            pass
    d = decide(store, tool, args, task_id, elem=elem, page=page, gmail_ready=gmail_ready())
    if d.decision == DENY:
        store.resolve_approval(aid, "denied", scope, {"status": "denied", "reason": d.reason}, args)
        asyncio.create_task(notify_runtime("/internal/approval_resolved", {
            "approval_id": aid, "task_id": task_id, "call_id": ap["call_id"], "decision": "denied",
            "result": {"status": "denied", "reason": d.reason}}))
        return {"ok": False, "status": "denied", "reason": d.reason}
    if scope != "ONCE":
        ttl = SCOPE_TTL.get(scope)
        if scope == "TIME_BOUND":
            ttl = max(0.25, min(float(b.get("ttl_hours", 1)), 24 * 30)) * 3600
        store.add_grant(tool, scope, task_id if scope == "TASK" else None, {"destination": d.destination}, ttl,
                        note=ap["summary"].get("title", ""))
    store.audit("user", "approval.approve", task_id=task_id, resource=tool, risk=ap["risk"], decision=ALLOW,
                result="approved", detail={"approval_id": aid, "scope": scope, "edited": sorted(edited.keys()), "via": via})
    result = await _run(tool, args, task_id, ap["risk"], {"args": _safe_args(tool, args), "approval_id": aid}, decision="APPROVED")
    store.resolve_approval(aid, "approved", scope, result, args)
    if scope == "ONCE":
        try:
            sg = suggest.just_reached(store, store.approval(aid))
            if sg:
                msg = (f"🔁 你已经第 {sg['count']} 次批准「{sg['title']}」" + (f"（{sg['destination']}）" if sg["destination"] else "")
                       + "。要不要以后自动允许？到「可信度 Trust」页可以开启（随时可撤销）。")
                if bot and bot.config():
                    asyncio.create_task(_safe(actions.telegram_send(store, msg)))
                asyncio.create_task(notify_runtime("/internal/notify_user", {"title": "🔁 可以少批一次 Fewer approvals", "body": msg}))
        except Exception:
            pass
    asyncio.create_task(notify_runtime("/internal/approval_resolved", {
        "approval_id": aid, "task_id": task_id, "call_id": ap["call_id"], "decision": "approved", "result": result}))
    return {"ok": True, "status": "approved", "result": result}


# ================================================================== vault (values never leave Sentinel)
@app.get("/internal/vault", dependencies=[Depends(runtime_auth)])
async def internal_vault():
    return {"items": [{k: it[k] for k in ("id", "label", "kind", "masked", "fields", "domains")} for it in vault.list_items(store)]}


@app.get("/sentinel/api/vault", dependencies=[Depends(ui_auth)])
async def vault_list():
    return {"items": vault.list_items(store), "kinds": vault.KINDS, "field_labels": vault.FIELD_LABELS}


def _vault_save(b: dict, iid: str | None):
    try:
        it = vault.save_item(store, b, iid)
    except KeyError:
        raise HTTPException(404, "not found")
    except ValueError as e:
        raise HTTPException(400, str(e))
    store.audit("user", "vault.update" if iid else "vault.add", resource=it["id"],
                detail={"label": it["label"], "kind": it["kind"], "fields": it["fields"], "domains": it["domains"]})
    return {"item": it}


@app.post("/sentinel/api/vault", dependencies=[Depends(ui_auth)])
async def vault_add(req: Request):
    return _vault_save(await req.json(), None)


@app.put("/sentinel/api/vault/{iid}", dependencies=[Depends(ui_auth)])
async def vault_update(iid: str, req: Request):
    return _vault_save(await req.json(), iid)


@app.delete("/sentinel/api/vault/{iid}", dependencies=[Depends(ui_auth)])
async def vault_delete(iid: str):
    it = vault.item(store, iid)
    if not vault.delete_item(store, iid):
        raise HTTPException(404, "not found")
    store.audit("user", "vault.delete", resource=iid, detail={"label": it["label"]})
    return {"ok": True}


# ================================================================== user API: grants
@app.get("/sentinel/api/grants", dependencies=[Depends(ui_auth)])
async def grants():
    return {"grants": store.active_grants()}


@app.delete("/sentinel/api/grants/{gid}", dependencies=[Depends(ui_auth)])
async def revoke(gid: str):
    store.revoke_grant(gid)
    store.audit("user", "grant.revoke", resource=gid, decision="REVOKE", result="success")
    return {"ok": True}


# ================================================================== user API: connections & credentials
def _conn_view(name: str) -> dict:
    c = store.connection(name)
    c["has_credential"] = store.has_secret(f"cred_{name}_1")
    c["credential_handle"] = f"cred_{name}_1" if c["has_credential"] else ""
    if name == "gmail":
        c["accounts"] = [{**{k: a[k] for k in ("id", "email", "display_name", "ready", "provider", "auth")},
                          "provider_label": mailproviders.label(a["provider"])} for a in mailboxes.accounts(store)]
        c["providers"] = mailproviders.public_presets()
        c["default"] = mailboxes.default_id(store)
        c["has_credential"] = bool(mailboxes.ready_accounts(store))
    if name == "calendar":
        from app.sentinel import gcal
        sec = store.get_secret("cred_calendar_1") or {}
        c["mode"] = "ical" if sec.get("ical_url") else ("google" if sec.get("managed") else ("google_own" if sec else ""))
        m = gcal.managed(store)
        c["managed_available"] = m is not None
        c["managed_source"] = m["source"] if m else ""
        c["relay_url"] = (m or {}).get("relay") or gcal.DEFAULT_RELAY
    if name == "phone":
        c["dialmcp"] = {"connected": dialmcp.ready(store), "account": dialmcp.account(store), "url": dialmcp.url(store)}
        c["telnyx_ready"] = phone.telnyx_ready(store)
        c["ready"] = phone.ready(store)
    return c


@app.get("/sentinel/api/connections", dependencies=[Depends(ui_auth)])
async def connections():
    return {"connections": [_conn_view(n) for n in CONNECTORS],
            "tools": {k: {"connector": v["connector"], "capability": v["capability"], "risk": v["risk"]} for k, v in TOOLS.items()}}


@app.put("/sentinel/api/connections/{name}", dependencies=[Depends(ui_auth)])
async def save_conn(name: str, req: Request):
    if name not in CONNECTORS:
        raise HTTPException(404)
    b = await req.json()
    cfg = b.get("config")
    if cfg is not None:
        cfg = {k: v for k, v in cfg.items() if k not in ("app_password", "bot_token", "password", "token", "workspace", "bot_id",
                                                          "team", "user", "user_id", "token_type")}
        if name == "calendar":
            cfg = {k: v for k, v in cfg.items() if k == "time_zone"}
        if name == "phone":
            cfg = _phone_cfg(cfg)
        if name == "browser":
            for k in ("blocked_domains", "allowed_domains"):
                if k in cfg and isinstance(cfg[k], str):
                    cfg[k] = [x.strip().lower() for x in cfg[k].replace("\n", ",").split(",") if x.strip()]
    c = store.save_connection(name, cfg, b.get("permissions"), b.get("enabled"))
    store.audit("user", "connection.update", resource=name, result="success",
                detail={"permissions": c["permissions"], "enabled": c["enabled"]})
    return _conn_view(name)


# ------------------------------------------------------------------ phone (Telnyx + OpenAI Realtime)
def _phone_cfg(b: dict) -> dict:
    out = {}
    for k in ("from_number", "connection_id", "owner_name", "voice", "model"):
        if k in b and b[k] is not None:
            out[k] = str(b[k]).strip()[:200]
    if b.get("provider") in ("auto", "telnyx", "dialmcp"):
        out["provider"] = b["provider"]
    if "from_number" in out:
        out["from_number"] = phone.normalize(out["from_number"])
    if b.get("public_url") is not None:
        u = str(b["public_url"]).strip().rstrip("/")
        if u and not phone.public_ok(u):
            raise HTTPException(400, "公开地址必须以 https:// 开头 (public URL must start with https://)")
        out["public_url"] = u.split("/voice")[0]
    if b.get("allowed_prefixes") is not None:
        v = b["allowed_prefixes"]
        v = v if isinstance(v, list) else str(v).replace("\n", ",").split(",")
        out["allowed_prefixes"] = [("+" + x.strip().lstrip("+")) for x in v if x.strip().lstrip("+").isdigit()][:20]
    for k, lo, hi in (("max_minutes", 1, phone.MAX_MINUTES_CAP), ("daily_limit", 1, 100)):
        if b.get(k) not in (None, ""):
            try:
                out[k] = max(lo, min(int(b[k]), hi))
            except (TypeError, ValueError):
                raise HTTPException(400, f"{k} 必须是数字 (must be a number)")
    return out


@app.post("/sentinel/api/connections/phone/credential", dependencies=[Depends(ui_auth)])
async def phone_cred(req: Request):
    b = await req.json()
    old = store.get_secret("cred_phone_1") or {}
    sec = dict(old)
    for k in ("telnyx_api_key", "openai_api_key", "telnyx_public_key"):
        v = str(b.get(k) or "").strip()
        if v:
            sec[k] = v
    if not (sec.get("telnyx_api_key") and sec.get("openai_api_key")):
        raise HTTPException(400, "需要 Telnyx API Key 和 OpenAI API Key (both keys are required)")
    store.put_secret("phone", sec)
    store.save_connection("phone", _phone_cfg(b), permissions={"call": True}, enabled=True)
    checks = await phone.test_setup(store)
    store.audit("user", "credential.phone.set", resource="phone", result="success", detail={"checks": checks})
    return {"ok": True, "checks": checks, "ready": phone.ready(store), "connection": _conn_view("phone")}


@app.post("/sentinel/api/connections/phone/test", dependencies=[Depends(ui_auth)])
async def phone_test():
    return {"checks": await phone.test_setup(store), "ready": phone.ready(store)}


@app.get("/sentinel/api/phone/calls", dependencies=[Depends(ui_auth)])
async def phone_calls(limit: int = 20):
    return {"calls": phone.list_calls(store, max(1, min(limit, 100)))}


@app.post("/sentinel/api/phone/test_call", dependencies=[Depends(ui_auth)])
async def phone_test_call(req: Request):
    """A short test call you start yourself from the Connections page (you clicked it, so no approval card)."""
    b = await req.json()
    lang = str(b.get("language") or "").strip()
    try:
        r = await phone.start_call(store, {"to": b.get("to", ""), "max_minutes": 2, "language": lang,
                                           "purpose": "This is a short test call of OMuse's phone feature to its owner. Greet them, say "
                                                      "you are OMuse testing the phone line, ask them to say a sentence, repeat back "
                                                      "what you heard, then say goodbye and end the call with outcome done."}, "")
    except phone.PhoneError as e:
        raise HTTPException(400, str(e))
    store.audit("user", "phone.test_call", resource=r["to"], result="success", detail={"call_id": r["call_id"]})
    return r


# ------------------------------------------------------------------ OAuth 2.1 sign-in for MCP servers (DialMCP, MCP hub)
OAUTH_CALLBACK = "/sentinel/api/oauth/callback"


def _oauth_redirect(req: Request, b: dict) -> str:
    host = req.headers.get("x-forwarded-host") or req.headers.get("host", "")
    try:
        return mcp_oauth.check_redirect(str(b.get("redirect_uri", "")), host, OAUTH_CALLBACK)
    except mcp_oauth.OAuthError as e:
        raise HTTPException(400, str(e))


@app.post("/sentinel/api/connections/phone/dialmcp/start", dependencies=[Depends(ui_auth)])
async def dialmcp_start(req: Request):
    b = await req.json()
    redirect = _oauth_redirect(req, b)
    try:
        r = await mcp_oauth.begin(dialmcp.url(store), redirect, "phone")
    except (mcp_oauth.OAuthError, Exception) as e:
        store.audit("user", "credential.dialmcp.start", resource="phone", result="failed", detail={"error": str(e)[:300]})
        raise HTTPException(400, f"无法开始 DialMCP 登录 (cannot start sign-in): {e}")
    store.audit("user", "credential.dialmcp.start", resource="phone", result="success")
    return {"auth_url": r["auth_url"]}


@app.delete("/sentinel/api/connections/phone/dialmcp", dependencies=[Depends(ui_auth)])
async def dialmcp_disconnect():
    store.delete_secret(dialmcp.HANDLE)
    await dialmcp._drop()
    store.audit("user", "credential.dialmcp.delete", resource="phone", result="success")
    return _conn_view("phone")


@app.post("/sentinel/api/mcp/oauth/start", dependencies=[Depends(ui_auth)])
async def mcp_oauth_start(req: Request):
    b = await req.json()
    redirect = _oauth_redirect(req, b)
    name = str(b.get("name", "")).strip()[:40]
    if not name:
        raise HTTPException(400, "请给这个服务器起个名字 (name required)")
    try:
        url = mcp_hub.check_server_url(str(b.get("url", "")))
        r = await mcp_oauth.begin(url, redirect, "mcp", {"name": name, "url": url,
                                                         "data_class": str(b.get("data_class", "CONFIDENTIAL"))})
    except Exception as e:
        raise HTTPException(400, f"无法开始 OAuth 登录 (cannot start sign-in): {e}")
    return {"auth_url": r["auth_url"]}


def _oauth_page(ok: bool, msg: str) -> HTMLResponse:
    import html as _h
    color = "#1a7f37" if ok else "#c62828"
    body = (f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>OMuse</title><body style='font-family:system-ui;padding:32px;max-width:560px;margin:auto'>"
            f"<h2 style='color:{color}'>{'✅' if ok else '⚠️'} {_h.escape(msg)}</h2>"
            f"<p>{'可以关闭这个页面，回到 OMuse。You can close this tab and return to OMuse.' if ok else '请回到 OMuse 重试。Go back to OMuse and try again.'}</p>"
            f"<p><a href='../../../#connections'>OMuse →</a></p>"
            f"<script>try{{window.opener&&window.opener.postMessage({{omuseOAuth:{'true' if ok else 'false'}}},location.origin)}}catch(e){{}}"
            f"{'setTimeout(()=>window.close(),1500)' if ok else ''}</script></body>")
    return HTMLResponse(body, status_code=200 if ok else 400)


@app.get(OAUTH_CALLBACK)
async def oauth_callback(state: str = "", code: str = "", error: str = "", error_description: str = ""):
    """The browser comes back here from the provider's login page. Protected by the single-use `state`."""
    try:
        flow, rec = await mcp_oauth.complete(state, code, f"{error} {error_description}".strip())
    except mcp_oauth.OAuthError as e:
        store.audit("user", "credential.oauth.callback", resource="oauth", result="failed", detail={"error": str(e)[:300]})
        return _oauth_page(False, str(e))
    if flow["purpose"] == "phone":
        mcp_oauth.save(store, dialmcp.HANDLE, "phone", rec)
        await dialmcp._drop()
        try:
            acct = await dialmcp.whoami(store)
        except Exception as e:
            acct = {}
            store.audit("user", "credential.dialmcp.whoami", resource="phone", result="failed", detail={"error": str(e)[:300]})
        sec = store.get_secret(dialmcp.HANDLE) or {}
        store.put_secret("phone", {**sec, "account": acct}, handle=dialmcp.HANDLE)
        store.save_connection("phone", {"dialmcp_url": flow["server_url"]}, permissions={"call": True}, enabled=True)
        store.audit("user", "credential.dialmcp.set", resource="phone", result="success", detail={"phone": acct.get("phone", "")})
        return _oauth_page(True, f"DialMCP 已连接 connected {acct.get('phone', '')}".strip())
    if flow["purpose"] == "mcp":
        x = flow["extra"]
        try:
            srv = await mcp_hub.add_server(store, name=x["name"], url=x["url"], data_class=x.get("data_class", "CONFIDENTIAL"),
                                           oauth=rec)
        except mcp_hub.HubError as e:
            store.audit("user", "mcp.add", resource=x["url"][:200], result="failed", detail={"error": str(e)[:300], "auth": "oauth"})
            return _oauth_page(False, str(e))
        store.audit("user", "mcp.add", resource=srv["id"], result="success",
                    detail={"url": srv["url"], "auth": "oauth", "tools": [t["name"] for t in srv["tools"]]})
        return _oauth_page(True, f"MCP「{srv['name']}」已连接 connected")
    return _oauth_page(False, "unknown sign-in")


def _mail_form(b: dict) -> tuple[str, str, str, dict]:
    email_addr = str(b.get("email", "")).strip()
    if not re.fullmatch(r"[^@\s<>,;]+@[^@\s<>,;]+\.[A-Za-z0-9-]{2,}", email_addr):
        raise HTTPException(400, "请填写正确的邮箱地址 (valid email address required)")
    provider = str(b.get("provider") or "").strip() or mailproviders.guess_provider(email_addr) or "custom"
    if provider not in mailproviders.PROVIDERS:
        raise HTTPException(400, f"unknown provider {provider}")
    try:
        servers = mailproviders.server_settings(provider, email_addr, b)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return email_addr, provider, str(b.get("display_name", "")).strip()[:120], servers


async def _mail_connect(email_addr: str, provider: str, dname: str, servers: dict, secret: dict) -> dict:
    """Test the mailbox with the given secret, then store it. Nothing is saved when the test fails."""
    from app.sentinel.gmail import GmailError
    acc = {"id": "test", "email": email_addr, "display_name": dname, "provider": provider, **servers}
    g = actions.make_client(acc, secret, store)
    if secret.get("oauth"):  # a fresh access token was just issued; use it for the test instead of refreshing
        tok = secret["oauth"].pop("_access_token", "")
        if tok:
            g.token_fn = lambda: tok
    try:
        info = await asyncio.to_thread(g.test)
    except GmailError as e:
        store.audit("user", "credential.gmail.set", resource="gmail", result="failed",
                    detail={"error": str(e)[:300], "provider": provider})
        raise HTTPException(400, str(e))
    saved = mailboxes.save_account(store, email_addr, secret.get("app_password", ""), dname, provider, servers,
                                   oauth=secret.get("oauth"))
    actions._MS_TOKENS.pop(saved["id"], None)
    store.audit("user", "credential.gmail.set", resource="gmail", result="success",
                detail={"email": email_addr, "account": saved["id"], "provider": provider})
    return {"ok": True, "test": info, "account": saved["id"], "connection": _conn_view("gmail")}


@app.post("/sentinel/api/connections/gmail/credential", dependencies=[Depends(ui_auth)])
async def gmail_cred(req: Request):
    """Connect a mailbox with an app password / authorization code (every provider except Outlook)."""
    b = await req.json()
    email_addr, provider, dname, servers = _mail_form(b)
    if mailproviders.PROVIDERS[provider]["auth"] == "oauth":
        raise HTTPException(400, "Outlook 需要用微软账号登录授权 (use Sign in with Microsoft)")
    pw = str(b.get("app_password", "")).strip()
    if provider in ("gmail", "yahoo", "aol", "icloud"):
        pw = pw.replace(" ", "")
    if provider == "gmail" and len(pw) < 12:
        raise HTTPException(400, "请填写邮箱地址和 16 位应用专用密码 (App Password)")
    if not pw and servers.get("smtp_security") != "none":
        raise HTTPException(400, "请填写密码 / 授权码 (password required)")
    return await _mail_connect(email_addr, provider, dname, servers, {"app_password": pw})


# Outlook / Microsoft 365: OAuth 2.0 device code flow with the user's own app registration (client ID)
_MS_FLOWS: dict[str, dict] = {}


@app.post("/sentinel/api/connections/gmail/oauth/start", dependencies=[Depends(ui_auth)])
async def gmail_oauth_start(req: Request):
    b = await req.json()
    email_addr, provider, dname, servers = _mail_form({**b, "provider": "outlook"})
    client_id = str(b.get("client_id", "")).strip()
    tenant = mailproviders.ms_tenant(email_addr)
    try:
        d = await asyncio.to_thread(mailproviders.ms_device_start, client_id, tenant)
    except mailproviders.OAuthError as e:
        raise HTTPException(400, str(e))
    for k in [k for k, v in _MS_FLOWS.items() if v["expires_at"] < time.time()]:
        _MS_FLOWS.pop(k, None)
    flow = secrets.token_urlsafe(12)
    _MS_FLOWS[flow] = {**d, "client_id": client_id, "tenant": tenant, "email": email_addr, "display_name": dname,
                       "servers": servers, "next_poll": 0.0}
    store.audit("user", "credential.gmail.oauth_start", resource="gmail", result="success", detail={"email": email_addr})
    return {"flow": flow, "user_code": d["user_code"], "verification_uri": d["verification_uri"],
            "expires_in": int(d["expires_at"] - time.time()), "interval": d["interval"]}


@app.get("/sentinel/api/connections/gmail/oauth/{flow}", dependencies=[Depends(ui_auth)])
async def gmail_oauth_poll(flow: str):
    f = _MS_FLOWS.get(flow)
    if not f:
        raise HTTPException(404, "登录流程不存在或已结束，请重新开始 (flow not found)")
    if f["expires_at"] < time.time():
        _MS_FLOWS.pop(flow, None)
        return {"status": "expired", "error": "登录码已过期，请重新开始 (code expired)"}
    if time.time() < f["next_poll"]:
        return {"status": "pending"}
    f["next_poll"] = time.time() + f["interval"]
    try:
        tok = await asyncio.to_thread(mailproviders.ms_device_poll, f["client_id"], f["tenant"], f["device_code"])
    except mailproviders.OAuthError as e:
        _MS_FLOWS.pop(flow, None)
        return {"status": "error", "error": str(e)}
    if tok is None:
        return {"status": "pending"}
    _MS_FLOWS.pop(flow, None)
    if not tok.get("refresh_token"):
        return {"status": "error", "error": "微软没有返回 refresh token：请确认权限里包含 offline_access (no refresh token)"}
    secret = {"oauth": {"client_id": f["client_id"], "tenant": f["tenant"], "refresh_token": tok["refresh_token"],
                        "_access_token": tok.get("access_token", "")}}
    try:
        res = await _mail_connect(f["email"], "outlook", f["display_name"], f["servers"], secret)
    except HTTPException as e:
        return {"status": "error", "error": e.detail}
    return {"status": "done", **res}


@app.post("/sentinel/api/connections/gmail/test", dependencies=[Depends(ui_auth)])
async def gmail_test(req: Request):
    try:
        b = await req.json()
    except Exception:
        b = {}
    try:
        g = actions.gmail_client(store, b.get("account"))
        return {"ok": True, "account": g.email, "test": await asyncio.to_thread(g.test)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.delete("/sentinel/api/connections/gmail/accounts/{aid}", dependencies=[Depends(ui_auth)])
async def gmail_remove(aid: str):
    acc = mailboxes.find(store, aid)
    mailboxes.remove_account(store, aid)
    store.audit("user", "credential.gmail.delete", resource="gmail", result="success",
                detail={"account": aid, "email": acc["email"] if acc else ""})
    return _conn_view("gmail")


@app.post("/sentinel/api/connections/gmail/default", dependencies=[Depends(ui_auth)])
async def gmail_default(req: Request):
    b = await req.json()
    try:
        mailboxes.set_default(store, str(b.get("account", "")))
    except KeyError:
        raise HTTPException(404, "account not found")
    store.audit("user", "connection.gmail.default", resource="gmail", result="success", detail={"account": b.get("account")})
    return _conn_view("gmail")


@app.post("/sentinel/api/connections/telegram/credential", dependencies=[Depends(ui_auth)])
async def telegram_cred(req: Request):
    b = await req.json()
    tok, chat = str(b.get("bot_token", "")).strip(), str(b.get("chat_id", "")).strip()
    tok = tok or (store.get_secret("cred_telegram_1") or {}).get("bot_token", "")
    if not tok or not chat:
        raise HTTPException(400, "需要 bot token 和 chat id")
    if not re.fullmatch(r"-?\d{3,20}", chat):
        raise HTTPException(400, "chat id 应该是一串数字（可点「检测 Chat ID」自动获取）")
    old = (store.get_secret("cred_telegram_1") or {}).get("bot_token", "")
    store.put_secret("telegram", {"bot_token": tok})
    store.save_connection("telegram", {"chat_id": chat}, permissions={"notify": True, "control": True}, enabled=True)
    if old != tok:  # new bot: forget the old update offset / cached username
        store.kv_set("tg_offset", 0)
        if bot:
            bot.status["username"] = ""
    try:
        await actions.telegram_send(store, "✅ OMuse 已连接 Telegram。直接给我发消息就能布置任务，发 /help 查看用法。\n"
                                           "Connected — message me to give OMuse a task, /help for commands.")
    except ActionError as e:
        store.audit("user", "credential.telegram.set", resource="telegram", result="failed", detail={"error": str(e)})
        raise HTTPException(400, str(e))
    store.audit("user", "credential.telegram.set", resource="telegram", result="success")
    return {"ok": True, "connection": _conn_view("telegram")}


@app.get("/sentinel/api/telegram/status", dependencies=[Depends(ui_auth)])
async def telegram_status():
    st = dict(bot.status) if bot else {}
    st["configured"] = bool(bot and bot.config())
    st["tracking"] = len(bot.tracked) if bot else 0
    return st


@app.post("/sentinel/api/connections/telegram/detect", dependencies=[Depends(ui_auth)])
async def telegram_detect(req: Request):
    """Find the chat id: the user sends /start to the bot, then we read who wrote to it."""
    b = await req.json()
    tok = str(b.get("bot_token", "")).strip() or (store.get_secret("cred_telegram_1") or {}).get("bot_token", "")
    if not tok:
        raise HTTPException(400, "请先填写 bot token")
    chats = {}
    saved = (store.get_secret("cred_telegram_1") or {}).get("bot_token", "")
    if bot and bot.status.get("running") and tok == saved:
        # our own poll loop is consuming the updates (a second getUpdates would conflict / see nothing):
        # use the private chats it saw and rejected because the configured chat id didn't match
        for x in sorted(store.kv_get("tg_seen_chats", []) or [], key=lambda x: x.get("ts", 0)):
            chats[str(x["chat_id"])] = x.get("name", "")
        return {"chats": [{"chat_id": k, "name": v} for k, v in chats.items()]}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{os.environ.get('TELEGRAM_API', 'https://api.telegram.org')}/bot{tok}/getUpdates", params={"timeout": 0})
    data = r.json() if r.content else {}
    if not data.get("ok"):
        raise HTTPException(400, f"Telegram: {data.get('description') or r.status_code}")
    for up in data.get("result") or []:
        ch = ((up.get("message") or {}).get("chat")) or {}
        if ch.get("type") == "private":
            chats[str(ch["id"])] = " ".join(x for x in (ch.get("first_name"), ch.get("last_name")) if x) or ch.get("username", "")
    return {"chats": [{"chat_id": k, "name": v} for k, v in chats.items()]}


# ------------------------------------------------------------------ Notion / Slack
@app.post("/sentinel/api/connections/notion/credential", dependencies=[Depends(ui_auth)])
async def notion_cred(req: Request):
    from app.sentinel.notion import Notion, NotionError
    b = await req.json()
    token = str(b.get("token", "")).strip()
    if not re.fullmatch(r"(secret_|ntn_)[A-Za-z0-9]{20,80}", token):
        raise HTTPException(400, "请粘贴 Notion 集成令牌（以 ntn_ 或 secret_ 开头）(integration token)")
    n = Notion(token)
    try:
        me = await asyncio.to_thread(n.me)
        found = await asyncio.to_thread(n.search, "", "", 5)
    except NotionError as e:
        store.audit("user", "credential.notion.set", resource="notion", result="failed", detail={"error": str(e)[:300]})
        raise HTTPException(400, str(e))
    finally:
        n.close()
    ws = (me.get("bot") or {}).get("workspace_name") or ""
    store.put_secret("notion", {"token": token})
    store.save_connection("notion", {"workspace": ws, "bot_id": me.get("id", "")}, enabled=True)
    store.audit("user", "credential.notion.set", resource="notion", result="success", detail={"workspace": ws})
    return {"ok": True, "workspace": ws, "bot": me.get("name", ""), "visible": [f["title"] for f in found]}


# ------------------------------------------------------------------ Google Calendar (OAuth, the user's own Google Cloud client)
CAL_CALLBACK = "/sentinel/api/connections/calendar/callback"


def _req_origin(req: Request) -> str:
    host = (req.headers.get("x-forwarded-host") or req.headers.get("host", "")).split(",")[0].strip()
    proto = (req.headers.get("x-forwarded-proto") or req.url.scheme or "https").split(",")[0].strip()
    return f"{proto}://{host}"


@app.post("/sentinel/api/connections/calendar/start", dependencies=[Depends(ui_auth)])
async def calendar_start(req: Request):
    """Step 1: save the OAuth client (vault) and return Google's consent URL."""
    from app.sentinel import gcal
    b = await req.json()
    cid = str(b.get("client_id", "")).strip()
    secret = str(b.get("client_secret", "")).strip()
    old = store.get_secret("cred_calendar_client") or {}
    if not secret and old.get("client_id") == cid:
        secret = old.get("client_secret", "")
    if not re.fullmatch(r"[0-9]+-[A-Za-z0-9_]+\.apps\.googleusercontent\.com", cid):
        raise HTTPException(400, "请粘贴 OAuth 客户端 ID（形如 1234-abc.apps.googleusercontent.com）(Client ID)")
    if not re.fullmatch(r"[A-Za-z0-9_\-]{10,100}", secret):
        raise HTTPException(400, "请粘贴客户端密钥 Client secret（GOCSPX- 开头）")
    origin = _req_origin(req)
    given = str(b.get("origin", "")).strip().rstrip("/")
    if re.fullmatch(r"https?://[^/\s]+", given) and given.split("://", 1)[1] == origin.split("://", 1)[1]:
        origin = given          # the address the user's browser really uses (scheme as seen behind the proxy)
    redirect = origin + CAL_CALLBACK
    state = secrets.token_urlsafe(24)
    store.put_secret("calendar", {"client_id": cid, "client_secret": secret}, handle="cred_calendar_client")
    store.kv_set("calendar_oauth", {"state": state, "ts": time.time(), "redirect": redirect})
    store.audit("user", "credential.calendar.start", resource="calendar", result="success", detail={"client_id": cid[:24]})
    return {"auth_url": gcal.auth_url(cid, redirect, state), "redirect_uri": redirect}


@app.post("/sentinel/api/connections/calendar/google/start", dependencies=[Depends(ui_auth)])
async def calendar_google_start(req: Request):
    """One-click: OMuse's own Google client. Google -> fixed relay page -> this box's callback (state names it)."""
    import base64
    import hashlib
    import json as _json
    from app.sentinel import gcal
    m = gcal.managed(store)
    if not m:
        raise HTTPException(400, "这个版本还没有内置 OMuse 的 Google 登录，请用下面的「自己的 Google Cloud 客户端」或 iCal 地址 (not available in this build)")
    b = await req.json()
    origin = _req_origin(req)
    given = str(b.get("origin", "")).strip().rstrip("/")
    if re.fullmatch(r"https?://[^/\s]+", given) and given.split("://", 1)[1] == origin.split("://", 1)[1]:
        origin = given
    back = origin + CAL_CALLBACK
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = base64.urlsafe_b64encode(_json.dumps({"r": back, "n": secrets.token_urlsafe(18)}, separators=(",", ":")).encode()).rstrip(b"=").decode()
    store.kv_set("calendar_oauth", {"state": state, "ts": time.time(), "redirect": m["relay"], "mode": "managed", "verifier": verifier})
    store.audit("user", "credential.calendar.start", resource="calendar", result="success", detail={"mode": "managed"})
    return {"auth_url": gcal.auth_url(m["client_id"], m["relay"], state, challenge)}


@app.post("/sentinel/api/connections/calendar/google/client", dependencies=[Depends(ui_auth)])
async def calendar_google_client(req: Request):
    """Save the user's own Google OAuth client on this box for one-click sign-in through the relay page."""
    from app.sentinel import gcal
    b = await req.json()
    cid = str(b.get("client_id", "")).strip()
    secret = str(b.get("client_secret", "")).strip()
    old = store.get_secret(gcal.BOX_CLIENT) or store.get_secret("cred_calendar_client") or {}
    if not secret and old.get("client_id") == cid:
        secret = old.get("client_secret", "")
    if not re.fullmatch(r"[0-9]+-[A-Za-z0-9_]+\.apps\.googleusercontent\.com", cid):
        raise HTTPException(400, "请粘贴 OAuth 客户端 ID（形如 1234-abc.apps.googleusercontent.com）(Client ID)")
    if not re.fullmatch(r"[A-Za-z0-9_\-]{10,100}", secret):
        raise HTTPException(400, "请粘贴客户端密钥 Client secret（GOCSPX- 开头）")
    store.put_secret("calendar", {"client_id": cid, "client_secret": secret, "relay": gcal.DEFAULT_RELAY}, handle=gcal.BOX_CLIENT)
    store.audit("user", "credential.calendar.box_client", resource="calendar", result="success", detail={"client_id": cid[:24]})
    return {"ok": True, "relay": gcal.DEFAULT_RELAY, "connection": _conn_view("calendar")}


@app.delete("/sentinel/api/connections/calendar/google/client", dependencies=[Depends(ui_auth)])
async def calendar_google_client_delete():
    from app.sentinel import gcal
    store.delete_secret(gcal.BOX_CLIENT)
    store.audit("user", "credential.calendar.box_client_delete", resource="calendar", result="success")
    return {"ok": True, "connection": _conn_view("calendar")}


@app.post("/sentinel/api/connections/calendar/ical", dependencies=[Depends(ui_auth)])
async def calendar_ical(req: Request):
    """30-second read-only connection: the calendar's private iCal (ICS) address. The URL is the secret -> vault."""
    from app.sentinel import ical
    from app.sentinel.gcal import GCalError
    b = await req.json()
    try:
        url = ical.normalize_url(str(b.get("url", "")))
        tz_hint = str(b.get("time_zone") or "").strip()
        feed = ical.ICalFeed(url, tz_hint or "UTC")
        info = await asyncio.to_thread(lambda: (ical.fetch(url, force=True), feed.info())[1])
    except GCalError as e:
        raise HTTPException(400, str(e))
    tz = info["time_zone"] or tz_hint or "UTC"
    store.delete_secret("cred_calendar_access")
    store.delete_secret("cred_calendar_client")
    store.put_secret("calendar", {"ical_url": url})
    store.save_connection("calendar", {"email": ical.label(url), "time_zone": tz, "client_id": "", "mode": "ical",
                                       "calendar_name": info["name"]}, enabled=True)
    store.audit("user", "credential.calendar.set", resource="calendar", result="success",
                detail={"mode": "ical", "host": url.split("/")[2], "events": info["events"]})
    return {"ok": True, "name": info["name"], "time_zone": tz, "events": info["events"], "connection": _conn_view("calendar")}


def _cal_page(ok: bool, msg: str) -> Response:
    from html import escape
    color = "#1F6F5C" if ok else "#B42318"
    body = (f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'><title>OMuse</title>"
            f"<body style='font-family:system-ui;padding:40px;max-width:560px;margin:auto'><h2 style='color:{color}'>"
            f"{'✓' if ok else '✗'} Google Calendar</h2><p>{escape(msg)}</p><p><a href='../../../../#connections'>"
            f"返回 OMuse 连接页 Back to Connections</a></p>"
            + ("<script>setTimeout(()=>location.href='../../../../#connections',1500)</script>" if ok else "") + "</body>")
    return Response(body, media_type="text/html", headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@app.get(CAL_CALLBACK)
async def calendar_callback(req: Request, code: str = "", state: str = "", error: str = ""):
    """Step 2: Google redirects back here; swap the one-time code for a refresh token (kept in the vault)."""
    from app.sentinel import gcal
    pend = store.kv_get("calendar_oauth", {}) or {}
    if error:
        if error == "access_denied":
            # Google's most common cause: the OMuse OAuth app is still in "Testing" publishing status, so only Google
            # accounts on the developer's test-user list can authorize (2026-10-05 colleague on a non-listed account).
            return _cal_page(False, (
                "Google 拒绝了授权 (access_denied)。最常见的原因：OMuse 的 Google 应用还是「测试 Testing」发布状态，"
                "只有被加入测试用户名单的 Google 账号才能连接。请让管理员在 Google Cloud Console →「OAuth 同意屏幕」里"
                "把应用发布为「正式版 In production」，或把你的 Google 账号加入「测试用户 Test users」；"
                "如果你是在同意页点了「取消」，重新点一次「连接 Google 日历」即可。"
                " Google denied authorization. Most often OMuse's Google app is still in 'Testing' mode, so only accounts on "
                "the developer's test-user list can connect — ask the admin to publish the OAuth consent screen to Production, "
                "or add your Google account under Test users. If you clicked Cancel, just start the connect flow again."))
        return _cal_page(False, f"Google 返回错误 (error): {error}")
    if not state or not pend.get("state") or not secrets.compare_digest(state, pend["state"]) or time.time() - pend.get("ts", 0) > 900:
        return _cal_page(False, "授权链接已失效或不匹配，请回到连接页重新点「连接 Google 日历」(state mismatch / expired)")
    store.kv_set("calendar_oauth", {})
    managed = pend.get("mode") == "managed"
    if managed:
        m = gcal.managed(store)
        if not m:
            return _cal_page(False, "这个版本没有内置 OMuse 的 Google 登录 (managed client missing)")
        cl = {"client_id": m["client_id"], "client_secret": "" if m["broker"] else m["client_secret"]}
        turl = gcal.token_url(m)
    else:
        cl = store.get_secret("cred_calendar_client") or {}
        turl = ""
    try:
        tok = await asyncio.to_thread(gcal.exchange_code, cl.get("client_id", ""), cl.get("client_secret", ""), code, pend["redirect"],
                                      pend.get("verifier", ""), turl)
        g = gcal.GCal(cl["client_id"], cl["client_secret"], tok["refresh_token"], access_token=tok["access_token"],
                      expires_at=time.time() + int(tok.get("expires_in") or 3600), token_url=turl)
        try:
            who = await asyncio.to_thread(g.userinfo)
            tz = await asyncio.to_thread(g.settings_tz)
            await asyncio.to_thread(g.list_events, None, None, "", "primary", 1)
        finally:
            g.close()
    except gcal.GCalError as e:
        store.audit("user", "credential.calendar.set", resource="calendar", result="failed", detail={"error": str(e)[:300]})
        return _cal_page(False, str(e))
    if managed:   # the secret is OMuse's (built in or kept by the broker): store only what is ours
        store.put_secret("calendar", {"client_id": cl["client_id"], "managed": True, "refresh_token": tok["refresh_token"]})
        store.delete_secret("cred_calendar_client")
    else:
        store.put_secret("calendar", {"client_id": cl["client_id"], "client_secret": cl["client_secret"],
                                      "refresh_token": tok["refresh_token"]})
    store.delete_secret("cred_calendar_access")
    store.save_connection("calendar", {"email": who.get("email", ""), "time_zone": tz, "client_id": cl["client_id"],
                                       "mode": "google" if managed else "google_own", "calendar_name": ""}, enabled=True)
    store.audit("user", "credential.calendar.set", resource="calendar", result="success", detail={"email": who.get("email", ""), "tz": tz})
    return _cal_page(True, f"已连接 {who.get('email', '')}（时区 {tz}）。Connected.")


@app.post("/sentinel/api/connections/calendar/test", dependencies=[Depends(ui_auth)])
async def calendar_test():
    try:
        r = await asyncio.to_thread(actions.calendar_call, store, "calendar_list_events", {}, "")
    except actions.ActionError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "upcoming": len(r.get("content", {}).get("events", []))}


@app.post("/sentinel/api/connections/slack/credential", dependencies=[Depends(ui_auth)])
async def slack_cred(req: Request):
    from app.sentinel.slack import Slack, SlackError
    b = await req.json()
    token = str(b.get("token", "")).strip()
    if not re.fullmatch(r"xox[bp]-[A-Za-z0-9-]{10,200}", token):
        raise HTTPException(400, "请粘贴 Slack 令牌：机器人令牌 xoxb-… 或用户令牌 xoxp-… (bot or user token)")
    sl = Slack(token)
    try:
        info = await asyncio.to_thread(sl.auth_test)
        chans = await asyncio.to_thread(sl.channels, 50)
    except SlackError as e:
        store.audit("user", "credential.slack.set", resource="slack", result="failed", detail={"error": str(e)[:300]})
        raise HTTPException(400, str(e))
    finally:
        sl.close()
    store.put_secret("slack", {"token": token})
    store.save_connection("slack", {k: info.get(k, "") for k in ("team", "user", "user_id", "bot_id", "token_type")}, enabled=True)
    store.audit("user", "credential.slack.set", resource="slack", result="success", detail={"team": info.get("team"), "type": info["token_type"]})
    return {"ok": True, **info, "channels": len(chans), "member_of": [c["name"] for c in chans if c["is_member"]][:20]}


# ------------------------------------------------------------------ triggers (runtime polls these)
@app.get("/internal/watch/sources", dependencies=[Depends(runtime_auth)])
async def watch_sources():
    return {"sources": watchers.SOURCES}


@app.post("/internal/watch", dependencies=[Depends(runtime_auth)])
async def watch(req: Request):
    b = await req.json()
    src = str(b.get("source", ""))
    info = watchers.SOURCES.get(src)
    if not info:
        return {"error": f"unknown source {src}", "events": [], "cursor": b.get("cursor")}
    conn = store.connection(info["connector"])
    perm = "browse" if info["connector"] == "browser" else "read"
    if not conn["enabled"] or not conn["permissions"].get(perm, False):
        return {"error": f"{info['connector']} 未启用或读取权限已关闭 (connector disabled / read permission off)",
                "events": [], "cursor": b.get("cursor")}
    try:
        if src == "web.page":
            res = await watchers.poll_web(store, dict(b.get("params") or {}), b.get("cursor"))
        else:
            res = await asyncio.to_thread(watchers.poll, store, src, dict(b.get("params") or {}), b.get("cursor"))
    except watchers.WatchError as e:
        return {"error": str(e), "events": [], "cursor": b.get("cursor")}
    if res["events"]:
        store.audit("sentinel", "trigger.events", resource=src, result="success",
                    detail={"count": len(res["events"]), "injection": res["injection"]})
    return res


@app.post("/internal/taint", dependencies=[Depends(runtime_auth)])
async def taint(req: Request):
    """Runtime tells Sentinel that a task starts with external (trigger) data in its context."""
    b = await req.json()
    lvl = str(b.get("taint", "CONFIDENTIAL"))
    ctx = store.update_task_ctx(str(b.get("task_id", "")), taint=lvl if lvl in guard.LEVELS else "CONFIDENTIAL",
                                injection=[str(x)[:40] for x in (b.get("injection") or [])][:10] or None)
    return {"ok": True, "ctx": ctx}


# ------------------------------------------------------------------ MCP servers
def _mcp_view(srv: dict) -> dict:
    v = {k: srv.get(k) for k in ("id", "name", "url", "transport", "enabled", "data_class", "auth", "header_name",
                                 "server_info", "protocol", "instructions", "last_sync", "last_error")}
    v["has_credential"] = store.has_secret(mcp_hub.handle(srv["id"]))
    v["tools"] = [{**{k: t.get(k) for k in ("name", "title", "description", "kind", "guessed", "mode", "status", "flags",
                                             "annotations", "previous_description")},
                   "llm_name": mcp_hub.tool_name(srv["id"], t["name"])} for t in srv.get("tools") or []]
    return v


def _mcp_err(e: Exception):
    raise HTTPException(400, str(e))


@app.get("/sentinel/api/mcp/servers", dependencies=[Depends(ui_auth)])
async def mcp_list():
    return {"servers": [_mcp_view(x) for x in mcp_hub.servers(store)]}


@app.post("/sentinel/api/mcp/servers", dependencies=[Depends(ui_auth)])
async def mcp_add(req: Request):
    b = await req.json()
    try:
        srv = await mcp_hub.add_server(store, name=str(b.get("name", "")), url=str(b.get("url", "")),
                                       auth_type=str(b.get("auth_type", "none")), token=str(b.get("token", "")),
                                       header_name=str(b.get("header_name", "")),
                                       data_class=str(b.get("data_class", "CONFIDENTIAL")))
    except mcp_hub.HubError as e:
        store.audit("user", "mcp.add", resource=str(b.get("url", ""))[:200], result="failed", detail={"error": str(e)[:300]})
        _mcp_err(e)
    store.audit("user", "mcp.add", resource=srv["id"], result="success",
                detail={"url": srv["url"], "transport": srv["transport"], "tools": [t["name"] for t in srv["tools"]],
                        "flagged": [t["name"] for t in srv["tools"] if t["flags"]]})
    return _mcp_view(srv)


@app.post("/sentinel/api/mcp/servers/{sid}/refresh", dependencies=[Depends(ui_auth)])
async def mcp_refresh(sid: str):
    try:
        r = await mcp_hub.refresh(store, sid)
    except mcp_hub.HubError as e:
        _mcp_err(e)
    store.audit("user", "mcp.refresh", resource=sid, result="success", detail={"diff": r["diff"]})
    return {**_mcp_view(r["server"]), "diff": r["diff"]}


@app.post("/sentinel/api/mcp/servers/{sid}/test", dependencies=[Depends(ui_auth)])
async def mcp_test(sid: str):
    try:
        return await mcp_hub.test_server(store, sid)
    except mcp_hub.HubError as e:
        _mcp_err(e)


@app.put("/sentinel/api/mcp/servers/{sid}", dependencies=[Depends(ui_auth)])
async def mcp_update(sid: str, req: Request):
    b = await req.json()
    try:
        if b.get("token") is not None or b.get("auth_type") is not None:
            srv = mcp_hub.server(store, sid) or {}
            at = str(b.get("auth_type", srv.get("auth", "none")))
            headers = mcp_hub.build_headers(at, str(b.get("token", "")), str(b.get("header_name", srv.get("header_name", ""))))
            if headers:
                store.put_secret("mcp", {"headers": headers}, handle=mcp_hub.handle(sid))
            elif at == "none":
                store.delete_secret(mcp_hub.handle(sid))
            mcp_hub._update(store, sid, lambda x: {**x, "auth": at if headers or at == "none" else x.get("auth"),
                                                   "header_name": str(b.get("header_name", x.get("header_name", "")))})
            await mcp_hub._drop(sid)
        srv = mcp_hub.set_server(store, sid, enabled=b.get("enabled"), data_class=b.get("data_class"), name=b.get("name"))
    except mcp_hub.HubError as e:
        _mcp_err(e)
    store.audit("user", "mcp.update", resource=sid, result="success",
                detail={k: b[k] for k in ("enabled", "data_class", "name", "auth_type") if k in b})
    return _mcp_view(srv)


@app.put("/sentinel/api/mcp/servers/{sid}/tools/{tname}", dependencies=[Depends(ui_auth)])
async def mcp_tool(sid: str, tname: str, req: Request):
    b = await req.json()
    try:
        srv = mcp_hub.set_tool(store, sid, tname, mode=b.get("mode"), accept=bool(b.get("accept")))
    except mcp_hub.HubError as e:
        _mcp_err(e)
    store.audit("user", "mcp.tool", resource=f"{sid}/{tname}", result="success",
                detail={k: b[k] for k in ("mode", "accept") if k in b})
    return _mcp_view(srv)


@app.delete("/sentinel/api/mcp/servers/{sid}", dependencies=[Depends(ui_auth)])
async def mcp_delete(sid: str):
    await mcp_hub.remove_server(store, sid)
    store.audit("user", "mcp.remove", resource=sid, result="success")
    return {"ok": True}


@app.delete("/sentinel/api/connections/{name}/credential", dependencies=[Depends(ui_auth)])
async def delete_cred(name: str):
    if name == "gmail":
        for a in mailboxes.accounts(store):
            mailboxes.remove_account(store, a["id"])
    store.delete_secret(f"cred_{name}_1")
    if name == "calendar":
        store.delete_secret("cred_calendar_access")
        store.delete_secret("cred_calendar_client")
    if name in ("notion", "slack", "calendar", "phone"):
        store.save_connection(name, enabled=False)
    store.audit("user", f"credential.{name}.delete", resource=name, result="success")
    return {"ok": True}


# ================================================================== user API: audit
@app.get("/sentinel/api/audit", dependencies=[Depends(ui_auth)])
async def audit_list(task_id: str | None = None, limit: int = 200, before: int | None = None, actor: str | None = None):
    return {"events": store.audit_list(task_id, min(limit, 1000), before, actor)}


@app.get("/sentinel/api/audit/verify", dependencies=[Depends(ui_auth)])
async def audit_verify():
    return store.audit_verify()


# ================================================================== user API: browser view & takeover
@app.get("/sentinel/api/browser/state", dependencies=[Depends(ui_auth)])
async def b_state():
    try:
        return await actions.broker("GET", "/state", timeout=10)
    except ActionError as e:
        return {"mode": "offline", "error": str(e)}


@app.get("/sentinel/api/browser/screenshot", dependencies=[Depends(ui_auth)])
async def b_shot(task_id: str | None = None):
    try:
        img = await actions.broker("GET", "/screenshot" + (f"?task_id={task_id}" if task_id else ""), timeout=15)
    except ActionError:
        return Response(status_code=204)
    if not isinstance(img, (bytes, bytearray)):
        return Response(status_code=204)
    return Response(img, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.post("/sentinel/api/browser/takeover", dependencies=[Depends(ui_auth)])
async def b_takeover(req: Request):
    b = await req.json()
    st = await actions.broker("POST", "/user/takeover", {"task_id": b.get("task_id")}, timeout=200)
    store.audit("user", "browser.takeover", task_id=st.get("takeover_task", ""), resource=st.get("url", ""), result="success")
    return st


@app.post("/sentinel/api/browser/release", dependencies=[Depends(ui_auth)])
async def b_release():
    r = await actions.broker("POST", "/user/release", {}, timeout=20)
    rel = r.get("released") or {}
    store.audit("user", "browser.release", task_id=rel.get("task_id") or "", result="success")
    await notify_runtime("/internal/takeover_ended", {"task_id": rel.get("task_id") or "",
                                                      "requested_task": (rel.get("requested") or {}).get("task_id", "")})
    return r


@app.post("/sentinel/api/browser/view", dependencies=[Depends(ui_auth)])
async def b_view(req: Request):
    return await actions.broker("POST", "/user/view", await req.json(), timeout=10)


@app.post("/sentinel/api/browser/input", dependencies=[Depends(ui_auth)])
async def b_input(req: Request):
    b = await req.json()
    r = await actions.broker("POST", "/user/input", b, timeout=60)
    # never log what the user typed during takeover (may be a password)
    if b.get("type") in ("navigate",):
        store.audit("user", "browser.user_navigate", resource=guard.domain_of(str(b.get("url", ""))), result="success")
    return r


# ================================================================== front door
@app.get("/sentinel/api/health")
async def health():
    return {"ok": True, "version": VERSION}


# ------------------------------------------------------------------ login password (standalone installs)
@app.get("/sentinel/api/password", dependencies=[Depends(ui_auth)])
async def password_status():
    """Whether this install has its own login (Docker: OMUSE_PASSWORD) and whether it still runs on the default."""
    if not passwd.enabled():
        return {"enabled": False}
    return {"enabled": True, "default": passwd.is_default(), "user": passwd.user(), "min_length": passwd.MIN_LEN}


@app.post("/sentinel/api/password", dependencies=[Depends(ui_auth)])
async def password_change(req: Request):
    if not passwd.enabled():
        raise HTTPException(404, "this install has no login of its own")
    b = await req.json()
    current, new = str(b.get("current") or ""), str(b.get("new") or "")
    if not passwd.verify(passwd.user(), current):
        store.audit("user", "password.change", resource="login", result="denied", detail={"reason": "current password wrong"})
        await asyncio.sleep(1.0)
        raise HTTPException(403, "当前密码不对 (current password is wrong)")
    try:
        passwd.set_password(new)
    except passwd.PasswordError as e:
        raise HTTPException(400, str(e))
    store.audit("user", "password.change", resource="login", result="success")
    return {"ok": True}


# ------------------------------------------------------------------ subscription (hosted installs)
@app.get("/sentinel/api/subscription", dependencies=[Depends(ui_auth)])
async def subscription():
    """Whether Settings shows "Manage subscription", plus the subscription's state when Stripe answers."""
    if not billing.config():
        return {"enabled": False}
    try:
        return {"enabled": True, **(await billing.status())}
    except billing.BillingError as e:
        return {"enabled": True, "error": str(e)}


@app.post("/sentinel/api/subscription/portal", dependencies=[Depends(ui_auth)])
async def subscription_portal(req: Request):
    if not billing.config():
        raise HTTPException(404, "subscription management is not configured")
    host = (req.headers.get("x-forwarded-host") or req.headers.get("host", "")).split(",")[0].strip()
    proto = (req.headers.get("x-forwarded-proto") or req.url.scheme or "https").split(",")[0].strip()
    try:
        url = await billing.portal_url(f"{proto}://{host}/#settings")
    except billing.BillingError as e:
        store.audit("user", "subscription.portal", resource="stripe", result="failed", detail={"error": str(e)[:300]})
        raise HTTPException(502, str(e))
    store.audit("user", "subscription.portal", resource="stripe", result="success")
    return {"url": url}


HOP = {"host", "content-length", "connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade",
       "proxy-authorization", "proxy-authenticate", "x-persona-runtime"}


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(path: str, request: Request):
    if request.method not in ("GET", "HEAD") and request.headers.get("x-persona-ui") != "1":
        raise HTTPException(403, "UI header required")
    url = f"{RUNTIME_URL}/api/{path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP}
    body = await request.body()
    rq = proxy_client.build_request(request.method, url, params=request.query_params, headers=headers, content=body)
    try:
        try:
            r = await proxy_client.send(rq, stream=True)
        except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadError) as e:
            # a pooled connection closed under us (or the runtime is restarting): one retry for reads and uploads-free calls
            if request.method not in ("GET", "HEAD"):
                raise
            print(f"[proxy] retry {request.method} /api/{path}: {type(e).__name__}", flush=True)
            await asyncio.sleep(0.3)
            rq = proxy_client.build_request(request.method, url, params=request.query_params, headers=headers, content=body)
            r = await proxy_client.send(rq, stream=True)
    except httpx.HTTPError as e:
        print(f"[proxy] 503 {request.method} /api/{path}: {type(e).__name__}: {str(e)[:120]}", flush=True)
        return JSONResponse({"detail": "Agent Runtime 暂不可用 (runtime unavailable)"}, status_code=503)
    resp_headers = {k: v for k, v in r.headers.items() if k.lower() not in HOP and k.lower() != "content-encoding"}
    if path == "chat" and request.method == "POST" and r.status_code == 200:
        # remember the user's own words for the task they start (policy uses them for buttons the user named)
        data = await r.aread()
        await r.aclose()
        try:
            tid = json.loads(data or b"{}").get("task_id")
            msg = json.loads(body or b"{}").get("message")
            if tid and isinstance(msg, str):
                store.set_user_request(tid, msg)
        except Exception:
            pass
        resp_headers.pop("content-length", None)
        return Response(data, status_code=r.status_code, headers=resp_headers)

    async def gen():
        try:
            async for chunk in r.aiter_raw():
                yield chunk
        finally:
            await r.aclose()
    return StreamingResponse(gen(), status_code=r.status_code, headers=resp_headers)


def _asset_ver() -> str:
    """Version tag for cache-busting: changes whenever app.js/app.css change (e.g. after a hot patch)."""
    m = 0.0
    for f in ("app.js", "app.css", "i18n.js"):
        try:
            m = max(m, os.path.getmtime(os.path.join(WEB_DIR, f)))
        except OSError:
            pass
    return f"{VERSION}.{int(m)}"


@app.get("/")
async def index(request: Request):
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip()
    if host and not host.startswith(("127.", "localhost", "0.0.0.0")):
        proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "https").split(",")[0].strip()
        base = f"{proto}://{host}"
        if store.kv_get("public_base") != base:
            store.kv_set("public_base", base)
    with open(os.path.join(WEB_DIR, "index.html"), encoding="utf-8") as fh:
        html = fh.read()
    v = _asset_ver()
    for f in ("app.js", "app.css", "i18n.js"):
        html = html.replace(f'static/{f}"', f'static/{f}?v={v}"')
    return Response(html, media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-cache"})


@app.middleware("http")
async def _static_revalidate(request: Request, call_next):
    resp = await call_next(request)
    if request.url.path.startswith("/static/"):
        resp.headers["Cache-Control"] = "no-cache"  # always revalidate (cheap 304 via ETag)
    return resp


if os.path.isdir(WEB_DIR):
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.exception_handler(HTTPException)
async def http_exc(req, exc: HTTPException):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.exception_handler(ActionError)
async def action_exc(req, exc: ActionError):
    code = 423 if exc.status == "paused" else 403 if ("拦截" in str(exc) or "禁止" in str(exc) or "blocked" in str(exc)) else 400
    return JSONResponse({"detail": str(exc)}, status_code=code)
