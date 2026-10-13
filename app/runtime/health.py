"""Health watch: notice when OMuse cannot work and tell the user, instead of failing every task silently.

2026-10-05: the Olares router lost the chat model for a while; OMuse fell back to a text-to-speech model and every task
failed with HTTP 422 for a day before anyone noticed. Now:

* every CHECK_EVERY seconds the model router, the browser and Sentinel are checked;
* a component that fails two checks in a row is "down": one alert (in-app + Telegram), then at most one reminder every
  REMIND_AFTER seconds, and one "back to normal" message when it recovers;
* FAILED tasks are also grouped by cause (model / browser / mail / other): 3 with the same cause within an hour raise
  an alert even when the periodic checks look fine (a mailbox whose sign-in expired, a model that answers /models but
  not chats).
"""
from __future__ import annotations

import asyncio
import time

import httpx

CHECK_EVERY = 120
DOWN_AFTER = 2            # consecutive failed checks
LEDGER_EVERY = 6 * 3600   # merchants' emails are matched to ledger orders every 6 hours
MAIL_EVERY = 2            # mailboxes are checked every other round (≤ 8 min to an alert)
REMIND_AFTER = 6 * 3600
STREAK = 3                # failed tasks with the same cause …
STREAK_WINDOW = 3600      # … within this many seconds

LABELS = {"mail": ("邮箱", "mailbox"), "model": ("模型服务", "model service"), "browser": ("浏览器", "browser"), "sentinel": ("安全网关 Sentinel", "Sentinel"),
          "tasks": ("任务执行", "task runs")}
CAUSES = {"model": "模型", "browser": "浏览器", "mail": "邮箱", "sentinel": "Sentinel", "timeout": "超时",
          "step_limit": "步数用完", "gave_up": "来源反复失败", "other": "其他"}


def failure_cause(error: str) -> str:
    """Which part of OMuse a task failure points at."""
    e = str(error or "")
    low = e.lower()
    if "llmerror" in low or "模型" in e or "model api" in low or "model unavailable" in low or "chat/completions" in low:
        return "model"
    if "浏览器" in e or "browser" in low or "playwright" in low or "chromium" in low:
        return "browser"
    if any(k in low for k in ("gmail", "imap", "invalid_grant", "oauth", "mailbox")) or "邮箱" in e:
        return "mail"
    if "sentinel" in low:
        return "sentinel"
    if "用时上限" in e or "time limit" in low or "超时" in e or "timeout" in low:
        return "timeout"
    if "步数上限" in e or "step limit" in low:
        return "step_limit"
    if "反复失败" in e or "kept failing" in low or "stopped retrying" in low:
        return "gave_up"
    return "other"


def model_check(models: list[dict], want: str) -> tuple[bool, str]:
    """The configured chat model is listed, can chat and is loaded."""
    ids = [str(m.get("id") or "") for m in models]
    m = next((x for x in models if x.get("id") == want), None)
    if not m:
        return False, f"模型 {want} 不在模型服务的列表里（可能已卸载或正在加载）；当前可用：{', '.join(ids[:5]) or '无'}"
    mode = str(m.get("mode") or "chat").lower()
    if mode != "chat":
        return False, f"模型 {want} 不是聊天模型（mode={mode}）"
    ready = str(m.get("readiness") or "ready").lower()
    if ready not in ("ready", "running", "loaded"):
        return False, f"模型 {want} 还没就绪（{ready}）"
    return True, f"{want} 正常"


class Health:
    def __init__(self, rt):
        self.rt = rt
        self.state: dict[str, dict] = {}      # component -> {ok, detail, fails, since, alerted_at}
        self._task: asyncio.Task | None = None
        self.recent: list[dict] = []          # alerts sent (newest last, max 50)

    # ------------------------------------------------------------ checks
    async def check_model(self) -> tuple[bool, str]:
        from app.runtime.llm import auth_headers
        s = self.rt.store.settings()
        base = str(s.get("model_base_url") or "").rstrip("/")
        if not base:
            return False, "没有配置模型服务地址"
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.get(f"{base}/models", headers=auth_headers(s))
            if r.status_code >= 400:
                return False, f"模型服务返回 HTTP {r.status_code}"
            models = [m for m in (r.json().get("data") or []) if isinstance(m, dict)]
        except Exception as e:
            return False, f"连不上模型服务：{type(e).__name__}"
        if not models:   # a plain OpenAI-compatible server may not list models: don't call that an outage
            return True, "模型服务在线（未列出模型）"
        return model_check(models, s.get("model_name") or "")

    async def check_browser(self) -> tuple[bool, str]:
        try:
            st = await self.rt.sentinel("GET", "/internal/browser_state", timeout=15)
        except Exception as e:
            return False, f"连不上安全网关 Sentinel：{type(e).__name__}"
        if st.get("mode") in ("unknown", "offline") or st.get("error"):
            return False, f"浏览器服务不可用：{str(st.get('error') or '')[:120]}"
        return True, "浏览器正常"

    async def check_mail(self) -> tuple[bool, str] | None:
        """None = no mailbox connected (nothing to watch)."""
        try:
            r = await self.rt.sentinel("GET", "/internal/mail_check", timeout=90)
        except Exception as e:
            if "Connect" in type(e).__name__:
                return None          # Sentinel itself is down: the sentinel check reports that
            return False, f"邮箱检查没有完成：{type(e).__name__}"
        accs = r.get("accounts") or []
        if not accs:
            return None
        bad = [a for a in accs if not a.get("ok")]
        if bad:
            return False, "；".join(f"{a.get('email')} 连不上（{str(a.get('error') or '')[:100]}）" for a in bad[:3])
        return True, f"{len(accs)} 个邮箱正常"

    async def run_checks(self) -> dict:
        out = {}
        out["model"] = await self.check_model()
        self._round = getattr(self, "_round", 0) + 1
        if MAIL_EVERY <= 1 or self._round % MAIL_EVERY == 1:   # IMAP sign-ins are slower: every other round
            m = await self.check_mail()
            if m is not None:
                out["mail"] = m
        b_ok, b_detail = await self.check_browser()
        if not b_ok and "Sentinel" in b_detail:
            out["sentinel"] = (False, b_detail)
        else:
            out["sentinel"] = (True, "Sentinel 正常")
            out["browser"] = (b_ok, b_detail)
        return out

    # ------------------------------------------------------------ state + alerts
    async def observe(self, comp: str, ok: bool, detail: str, *, immediate: bool = False):
        now = time.time()
        st = self.state.setdefault(comp, {"ok": True, "detail": "", "fails": 0, "since": now, "alerted_at": 0.0, "down": False})
        st["detail"] = detail
        st["checked_at"] = now
        if ok:
            st["fails"] = 0
            if st["down"]:
                st["down"] = False
                st["since"] = now
                if st["alerted_at"]:
                    await self.alert(comp, f"已恢复正常：{detail}", recovered=True)
                st["alerted_at"] = 0.0
            st["ok"] = True
            return
        st["fails"] += 1
        st["ok"] = False
        if not st["down"] and (immediate or st["fails"] >= DOWN_AFTER):
            st["down"] = True
            st["since"] = now
        if st["down"] and now - st["alerted_at"] >= REMIND_AFTER:
            st["alerted_at"] = now
            await self.alert(comp, detail)

    async def alert(self, comp: str, detail: str, recovered: bool = False):
        en = self.rt.store.settings().get("language") == "en"
        zh_name, en_name = LABELS.get(comp, (comp, comp))
        if recovered:
            title = f"✅ {en_name} is back" if en else f"✅ {zh_name}已恢复"
        else:
            title = f"🚨 OMuse: {en_name} problem" if en else f"🚨 OMuse：{zh_name}出问题了"
        body = detail + ("" if recovered else ("\nNew tasks may fail until this is fixed." if en else "\n修好之前，新任务可能会失败。"))
        self.recent.append({"ts": time.time(), "component": comp, "title": title, "body": body, "recovered": recovered})
        del self.recent[:-50]
        try:
            n = self.rt.store.notify(title, body, level="info" if recovered else "warning")
            await self.rt.publish({"kind": "notification", "notification": n})
        except Exception:
            pass
        try:
            await self.rt.sentinel("POST", "/internal/notify", {"task_id": "", "text": f"{title}\n{body}"}, timeout=20)
        except Exception:
            pass


    async def on_task_finished(self, t: dict):
        """FAILED tasks grouped by cause: STREAK of the same cause within STREAK_WINDOW = an alert on "tasks"; the next
        task that completes clears it (the periodic checks can look fine while every chat fails)."""
        if not t or t.get("source") == "golden":
            return
        if t.get("status") == "COMPLETED":
            if self.state.get("tasks", {}).get("down"):
                await self.observe("tasks", True, "任务又能正常完成了")
            return
        if t.get("status") != "FAILED":
            return
        cause = failure_cause(t.get("error") or "")
        since = time.time() - STREAK_WINDOW
        rows = [r for r in self.rt.store.tasks("FAILED", 30) if (r.get("finished_at") or r.get("updated_at") or 0) >= since
                and r.get("source") != "golden"]
        same = [r for r in rows if failure_cause(r.get("error") or "") == cause]
        if len(same) >= STREAK:
            err = str(t.get("error") or "")[:200]
            await self.observe("tasks", False, f"最近 1 小时有 {len(same)} 个任务因{CAUSES.get(cause, cause)}问题失败：{err}",
                               immediate=True)

    def status(self) -> dict:
        return {"components": {k: {kk: v.get(kk) for kk in ("ok", "down", "detail", "since", "checked_at")}
                               for k, v in self.state.items()},
                "alerts": self.recent[-10:]}

    # ------------------------------------------------------------ loop
    def start(self):
        if not self._task:
            self._task = asyncio.create_task(self._loop())

    async def _loop(self):
        await asyncio.sleep(20)
        while True:
            try:
                res = await self.run_checks()
                for comp, (ok, detail) in res.items():
                    await self.observe(comp, ok, detail)
            except Exception as e:
                print(f"[health] check failed: {e!r}", flush=True)
            try:
                if time.time() - getattr(self, "_ledger_at", 0) >= LEDGER_EVERY:
                    self._ledger_at = time.time()
                    await self.reconcile_ledger()
            except Exception as e:
                print(f"[health] ledger reconcile failed: {e!r}", flush=True)
            await asyncio.sleep(CHECK_EVERY)

    async def reconcile_ledger(self) -> dict:
        """Merchants' emails move ledger orders along (shipped → delivered, cancelled, refunded); tell the user."""
        res = await self.rt.sentinel("POST", "/internal/ledger/reconcile", {}, timeout=300)
        labels = {"shipped": "已发货 shipped", "delivered": "已送达 delivered", "cancelled": "已取消 cancelled",
                  "refunded": "已退款 refunded", "placed": "已下单 placed"}
        for c in res.get("changed") or []:
            text = f"订单 {c['order_number']}：{labels.get(c['to'], c['to'])}（来自商家邮件）"
            try:
                n = self.rt.store.notify("🧾 " + text, "交易账本已更新 Ledger updated", level="info")
                await self.rt.publish({"kind": "notification", "notification": n})
                await self.rt.sentinel("POST", "/internal/notify", {"task_id": "", "text": "🧾 " + text}, timeout=20)
            except Exception:
                pass
        return res
