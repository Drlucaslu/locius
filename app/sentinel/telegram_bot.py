"""Two-way Telegram control, run inside Sentinel.

* Long polling (getUpdates) — works behind NAT, no public URL / webhook needed.
* Only the owner's chat (the configured chat_id) is served; everything else is ignored and audited.
* Text messages become tasks in a "Telegram" conversation; progress is edited in place, the result is sent
  when the task finishes. Commands: /new /tasks /stop /status /help.
* Approvals are pushed with inline ✅ / ❌ buttons and resolved through the same code path as the web UI
  (every decision is audited with via=telegram).
* The bot token never leaves Sentinel (vault); the agent/LLM never sees it.
"""
from __future__ import annotations

import asyncio
import html
import os
import re
import time

import httpx

TG_API = os.environ.get("TELEGRAM_API", "https://api.telegram.org")
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED"}
STATUS_ZH = {"CREATED": "已创建", "PLANNING": "规划中", "RUNNING": "执行中", "WAITING_APPROVAL": "等待审批",
             "WAITING_EXTERNAL": "等待你接管浏览器", "PAUSED": "已暂停", "COMPLETED": "已完成", "FAILED": "失败",
             "CANCELLED": "已取消"}
MARK = {"pending": "○", "running": "▸", "done": "✓", "failed": "✕", "skipped": "–"}
HELP = ("🤖 <b>OMuse on Telegram</b>\n"
        "直接发消息 = 给 OMuse 布置任务（和网页里的对话一样）。\n\n"
        "/new — 开始新对话 new conversation\n"
        "/tasks — 最近的任务 recent tasks\n"
        "/stop — 停止当前任务 stop the running task\n"
        "/status — 待审批 / 浏览器状态 pending approvals & browser\n"
        "/help — 帮助\n\n"
        "需要审批的操作会带 ✅ 批准 / ❌ 拒绝 按钮；需要你登录或输入验证码时，我会发网页链接给你接管浏览器。")


def md_to_tg(text: str, limit: int = 3900) -> list[str]:
    """Very small Markdown -> Telegram-HTML converter (bold, code, links, headings, tables as <pre>)."""
    text = (text or "").strip() or "（空）"
    out, in_code, table = [], False, []

    def flush_table():
        if table:
            rows = [r for r in table if not re.fullmatch(r"\|?[\s:\-|]+\|?", r)]
            out.append("<pre>" + html.escape("\n".join(" | ".join(c.strip() for c in r.strip().strip("|").split("|")) for r in rows)) + "</pre>")
            table.clear()

    for line in text.splitlines():
        if line.strip().startswith("```"):
            flush_table()
            out.append("</pre>" if in_code else "<pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        if line.strip().startswith("|") and line.count("|") >= 2:
            table.append(line)
            continue
        flush_table()
        esc = html.escape(line)
        m = re.match(r"^\s{0,3}#{1,6}\s+(.*)$", esc)
        if m:
            esc = f"<b>{m.group(1)}</b>"
        esc = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc)
        esc = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", esc)
        esc = re.sub(r"`([^`]+)`", r"<code>\1</code>", esc)
        esc = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", lambda mm: f'<a href="{mm.group(2)}">{mm.group(1)}</a>', esc)
        esc = re.sub(r"^(\s*)[-*]\s+", r"\1• ", esc)
        out.append(esc)
    flush_table()
    if in_code:
        out.append("</pre>")
    body = "\n".join(out)
    # split on line boundaries, keeping <pre> blocks balanced
    chunks, cur = [], ""
    for ln in body.split("\n"):
        if len(cur) + len(ln) + 1 > limit and cur:
            if cur.count("<pre>") > cur.count("</pre>"):
                cur += "</pre>"
                ln = "<pre>" + ln
            chunks.append(cur)
            cur = ""
        cur += ("\n" if cur else "") + ln
    if cur:
        chunks.append(cur)
    return chunks


class TelegramBot:
    def __init__(self, store, runtime_url: str, resolver, audit_actor: str = "telegram"):
        self.store = store
        self.runtime_url = runtime_url
        self.resolver = resolver              # async (approval_id, body, via) -> dict
        self.actor = audit_actor
        self.tracked: dict[str, dict] = {}    # task_id -> {"msg_id": int, "last": str}
        self.task: asyncio.Task | None = None
        self.tracker: asyncio.Task | None = None
        self.client: httpx.AsyncClient | None = None
        self.status = {"running": False, "last_error": "", "last_ok": 0.0, "username": ""}
        self._rejected_log = 0.0

    # ------------------------------------------------------------ config
    def config(self) -> tuple[str, str] | None:
        conn = self.store.connection("telegram")
        sec = self.store.get_secret("cred_telegram_1")
        chat = str(conn["config"].get("chat_id", "")).strip()
        if not conn["enabled"] or not sec or not chat or not conn["permissions"].get("control", True):
            return None
        return sec["bot_token"], chat

    def public_url(self, frag: str = "") -> str:
        base = self.store.kv_get("public_base", "")
        return f"{base}/#{frag}" if base else ""

    # ------------------------------------------------------------ lifecycle
    def start(self):
        if self.task is None or self.task.done():
            self.client = httpx.AsyncClient(timeout=httpx.Timeout(40.0, connect=10.0))
            self.task = asyncio.create_task(self._poll_loop())
            self.tracker = asyncio.create_task(self._track_loop())

    async def stop(self):
        for t in (self.task, self.tracker):
            if t:
                t.cancel()
        if self.client:
            await self.client.aclose()

    # ------------------------------------------------------------ Telegram API
    async def api(self, method: str, token: str, **params):
        r = await self.client.post(f"{TG_API}/bot{token}/{method}", json=params)
        data = r.json() if r.content else {}
        if not data.get("ok"):
            raise RuntimeError(f"telegram {method}: {data.get('description') or r.status_code}")
        return data.get("result")

    async def send(self, text: str, *, markup: dict | None = None, html_mode: bool = True) -> int | None:
        cfg = self.config()
        if not cfg:
            return None
        token, chat = cfg
        msg_id = None
        parts = md_to_tg(text) if not html_mode else [text[:4000]]
        for i, part in enumerate(parts):
            params = {"chat_id": chat, "text": part, "parse_mode": "HTML", "disable_web_page_preview": True}
            if markup and i == len(parts) - 1:
                params["reply_markup"] = markup
            try:
                res = await self.api("sendMessage", token, **params)
            except RuntimeError:
                params.pop("parse_mode")
                params["text"] = re.sub(r"<[^>]+>", "", part)
                res = await self.api("sendMessage", token, **params)
            msg_id = res.get("message_id")
        return msg_id

    async def send_document(self, name: str, data: bytes, caption: str = "", mime: str = "") -> int | None:
        """Photos go as photos (shown inline, ≤10 MB), MP4 videos as videos, everything else as a document."""
        cfg = self.config()
        if not cfg or not self.client:
            raise RuntimeError("Telegram 未连接 (not connected)")
        token, chat = cfg
        params = {"chat_id": chat}
        if caption:
            params["caption"] = caption[:1000]
        method, field = "sendDocument", "document"
        if mime in ("image/jpeg", "image/png", "image/webp") and len(data) <= 10 * 1024 * 1024:
            method, field = "sendPhoto", "photo"
        elif mime == "video/mp4":
            method, field = "sendVideo", "video"
        r = await self.client.post(f"{TG_API}/bot{token}/{method}", data=params, files={field: (name, data)},
                                   timeout=httpx.Timeout(120.0, connect=10.0))
        res = r.json() if r.content else {}
        if not res.get("ok") and method != "sendDocument":      # e.g. a photo Telegram can't process: send it as a file
            r = await self.client.post(f"{TG_API}/bot{token}/sendDocument", data=params, files={"document": (name, data)},
                                       timeout=httpx.Timeout(120.0, connect=10.0))
            res = r.json() if r.content else {}
        if not res.get("ok"):
            raise RuntimeError(f"telegram {method}: {res.get('description') or r.status_code}")
        return (res.get("result") or {}).get("message_id")

    async def edit(self, msg_id: int, text: str, markup: dict | None = None):
        cfg = self.config()
        if not cfg or not msg_id:
            return
        token, chat = cfg
        params = {"chat_id": chat, "message_id": msg_id, "text": text[:4000], "parse_mode": "HTML",
                  "disable_web_page_preview": True}
        if markup is not None:
            params["reply_markup"] = markup
        try:
            await self.api("editMessageText", token, **params)
        except RuntimeError as e:
            if "not modified" not in str(e):
                raise

    # ------------------------------------------------------------ runtime API
    async def rt(self, method: str, path: str, body: dict | None = None):
        r = await self.client.request(method, self.runtime_url + path, json=body, headers={"X-Persona-UI": "1"},
                                      timeout=30)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------ polling
    async def _poll_loop(self):
        backoff = 2
        while True:
            cfg = self.config()
            if not cfg:
                self.status["running"] = False
                await asyncio.sleep(5)
                continue
            token, chat = cfg
            try:
                if not self.status.get("username"):
                    me = await self.api("getMe", token)
                    self.status["username"] = me.get("username", "")
                    await self.api("deleteWebhook", token)
                offset = self.store.kv_get("tg_offset", 0)
                ups = await self.api("getUpdates", token, offset=offset, timeout=25,
                                     allowed_updates=["message", "callback_query"])
                self.status.update(running=True, last_error="", last_ok=time.time())
                backoff = 2
                for up in ups or []:
                    self.store.kv_set("tg_offset", up["update_id"] + 1)
                    try:
                        await self.handle(up, chat)
                    except Exception as e:  # never let one bad update kill the loop
                        self.store.audit(self.actor, "telegram.error", result="error", detail={"error": str(e)[:300]})
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.status.update(running=False, last_error=str(e)[:300])
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def handle(self, up: dict, chat: str):
        if "callback_query" in up:
            cq = up["callback_query"]
            frm = str((cq.get("message") or {}).get("chat", {}).get("id", ""))
            if frm != chat:
                return self._reject(frm)
            return await self.on_callback(cq)
        msg = up.get("message") or {}
        frm = str(msg.get("chat", {}).get("id", ""))
        if frm != chat:
            ch = msg.get("chat") or {}
            if ch.get("type") != "private":
                return self._reject(frm)
            return self._reject(frm, " ".join(x for x in (ch.get("first_name"), ch.get("last_name")) if x) or ch.get("username", ""))
        text = (msg.get("text") or "").strip()
        if not text:
            await self.send("暂时只支持文字消息 (text only for now) 🙏")
            return
        cmd = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""
        if cmd in ("/start", "/help"):
            await self.send(HELP)
        elif cmd == "/new":
            self.store.kv_set("tg_conv", "")
            await self.send("🆕 已开始新对话 New conversation. 直接发消息布置任务吧。")
        elif cmd == "/tasks":
            await self.cmd_tasks()
        elif cmd == "/stop":
            await self.cmd_stop()
        elif cmd == "/status":
            await self.cmd_status()
        elif cmd:
            await self.send("未知命令 unknown command。发送 /help 查看用法。")
        else:
            await self.new_task(text)

    def _reject(self, frm: str, name: str | None = None):
        if name is not None:
            # a private chat (latest 5): while this loop is polling, getUpdates-based "detect chat id" sees nothing,
            # so the Connections page reads these instead
            seen = [x for x in (self.store.kv_get("tg_seen_chats", []) or []) if x.get("chat_id") != frm]
            self.store.kv_set("tg_seen_chats", (seen + [{"chat_id": frm, "name": name[:60], "ts": time.time()}])[-5:])
        if time.time() - self._rejected_log > 60:   # rate-limited audit of strangers poking the bot
            self._rejected_log = time.time()
            self.store.audit(self.actor, "telegram.rejected", result="denied", detail={"from_chat": frm})

    # ------------------------------------------------------------ commands
    async def new_task(self, text: str):
        conv = self.store.kv_get("tg_conv", "") or None
        r = await self.rt("POST", "/api/chat", {"message": text, "conversation_id": conv})
        self.store.kv_set("tg_conv", r["conversation_id"])
        self.store.audit("user", "telegram.task", task_id=r["task_id"], result="success", detail={"chars": len(text)})
        mid = await self.send("🤖 收到，开始处理… <i>Working on it</i>")
        self.tracked[r["task_id"]] = {"msg_id": mid, "last": ""}

    async def cmd_tasks(self):
        ts = (await self.rt("GET", "/api/tasks?limit=8"))["tasks"]
        if not ts:
            await self.send("还没有任务。")
            return
        lines = [f"{'⏳' if t['status'] not in TERMINAL else '✅' if t['status'] == 'COMPLETED' else '⚠️'} "
                 f"<b>{STATUS_ZH.get(t['status'], t['status'])}</b> · {html.escape(t['goal'][:60])}" for t in ts]
        link = self.public_url("tasks")
        await self.send("📋 <b>最近任务 Recent tasks</b>\n" + "\n".join(lines) + (f'\n\n<a href="{link}">在网页中查看</a>' if link else ""))

    async def cmd_stop(self):
        conv = self.store.kv_get("tg_conv", "")
        ts = (await self.rt("GET", "/api/tasks?limit=30"))["tasks"]
        active = [t for t in ts if t["status"] not in TERMINAL and (not conv or t.get("conv_id") == conv)]
        if not active:
            await self.send("当前没有正在执行的任务。")
            return
        for t in active:
            await self.rt("POST", f"/api/tasks/{t['id']}/cancel", {})
        await self.send(f"⏹ 已停止 {len(active)} 个任务 stopped.")

    async def cmd_status(self):
        pend = self.store.approvals("pending", 20)
        lines = [f"🛡 待审批 Pending approvals: <b>{len(pend)}</b>"]
        for a in pend[:5]:
            lines.append(f"  • {html.escape((a['summary'] or {}).get('title') or a['tool'])}")
        await self.send("\n".join(lines))
        for a in pend[:5]:
            await self.send_approval(a)

    # ------------------------------------------------------------ progress tracking
    def _progress_text(self, t: dict) -> str:
        st = STATUS_ZH.get(t["status"], t["status"])
        plan = t.get("plan") or {}
        lines = [f"🤖 <b>{st}</b> · {html.escape((plan.get('objective') or t['goal'])[:120])}"]
        for s in (plan.get("steps") or [])[:8]:
            lines.append(f"{MARK.get(s.get('status', 'pending'), '○')} {html.escape(str(s.get('description', ''))[:90])}")
        if t["status"] == "WAITING_APPROVAL":
            lines.append("\n🛡 需要你批准，见下一条消息 ⬇️")
        return "\n".join(lines)

    async def _track_loop(self):
        while True:
            await asyncio.sleep(3)
            for tid, tr in list(self.tracked.items()):
                try:
                    t = await self.rt("GET", f"/api/tasks/{tid}")
                except Exception:
                    continue
                txt = self._progress_text(t)
                if txt != tr["last"] and tr.get("msg_id"):
                    try:
                        await self.edit(tr["msg_id"], txt)
                        tr["last"] = txt
                    except Exception:
                        pass
                if t["status"] in TERMINAL:
                    self.tracked.pop(tid, None)
                    await self.send_result(t)

    async def send_result(self, t: dict):
        head = {"COMPLETED": "✅ 完成 Done", "FAILED": "⚠️ 失败 Failed", "CANCELLED": "⏹ 已取消 Cancelled"}.get(t["status"], "")
        body = t.get("result") or t.get("error") or ""
        cfg = self.config()
        if not cfg:
            return
        await self.send(f"<b>{head}</b>")
        for part in md_to_tg(body):
            await self.send(part)

    # ------------------------------------------------------------ approvals & takeover
    async def send_approval(self, ap: dict):
        s = ap.get("summary") or {}
        lines = [f"🛡 <b>需要你批准 Approval needed</b>", f"<b>{html.escape(s.get('title') or ap['tool'])}</b>"
                 f" · 风险 {html.escape(ap.get('risk', ''))}"]
        if ap.get("reason"):
            lines.append(f"<i>{html.escape(ap['reason'][:300])}</i>")
        for k, v in (s.get("fields") or [])[:6]:
            if v:
                lines.append(f"{html.escape(str(k))}: <code>{html.escape(str(v)[:200])}</code>")
        if s.get("items"):
            for it in s["items"][:15]:
                frm = re.sub(r"<[^>]*>", "", it.get("from") or "").replace('"', "").strip()
                lines.append(f"• {html.escape(frm[:40])} — {html.escape((it.get('subject') or '')[:50])}")
            if len(s["items"]) > 15:
                lines.append(f"… 共 {len(s['items'])} 封")
        if s.get("body"):
            lines.append("<pre>" + html.escape(str(s["body"])[:1500]) + "</pre>")
        link = self.public_url("chat")
        rows = [[{"text": "✅ 批准 Approve", "callback_data": f"ap:{ap['id']}:y"},
                 {"text": "❌ 拒绝 Deny", "callback_data": f"ap:{ap['id']}:n"}]]
        if link:
            rows.append([{"text": "🌐 在网页中查看/修改", "url": link}])
        await self.send("\n".join(lines), markup={"inline_keyboard": rows})

    async def send_takeover(self, reason: str, task_id: str = ""):
        """The button opens that task's browser tab (not just the Browser page): with several tasks the right one shows."""
        link = self.public_url(f"browser/{task_id}" if task_id else "browser")
        rows = [[{"text": "🖐 打开浏览器接管 Take over", "url": link}]] if link else None
        await self.send(f"🙋 <b>需要你接管浏览器</b>\n{html.escape(reason[:300])}\n\n"
                        + (f"{html.escape(link)}\n\n" if link else "") + "完成后在网页里点「交还给 Agent」。",
                        markup={"inline_keyboard": rows} if rows else None)

    async def on_callback(self, cq: dict):
        cfg = self.config()
        if not cfg:
            return
        token, _ = cfg
        data = cq.get("data") or ""
        m = re.fullmatch(r"ap:([\w\-]+):([yn])", data)
        if not m:
            await self.api("answerCallbackQuery", token, callback_query_id=cq["id"])
            return
        aid, yes = m.group(1), m.group(2) == "y"
        msg = cq.get("message") or {}
        try:
            r = await self.resolver(aid, {"decision": "approve" if yes else "deny", "scope": "ONCE"}, "telegram")
            if not yes:
                outcome = "❌ 已拒绝 Denied"
            elif r.get("status") == "approved" and (r.get("result") or {}).get("status") == "ok":
                outcome = "✅ 已批准并执行 Approved & executed"
            elif r.get("status") == "approved":
                res = r.get("result") or {}
                outcome = f"⚠️ 已批准，但执行结果：{html.escape(str(res.get('error') or res.get('status'))[:200])}"
            else:
                outcome = f"⚠️ {html.escape(str(r.get('reason') or r.get('status')))}"
        except Exception as e:   # already resolved elsewhere, etc.
            outcome = f"ℹ️ {html.escape(str(getattr(e, 'detail', e))[:200])}"
        await self.api("answerCallbackQuery", token, callback_query_id=cq["id"], text=re.sub(r"<[^>]+>", "", outcome)[:190])
        old = msg.get("text") or ""
        try:
            await self.edit(msg.get("message_id"), html.escape(old[:3500]) + f"\n\n<b>{outcome}</b>", markup={"inline_keyboard": []})
        except Exception:
            pass
