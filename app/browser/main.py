"""Browser Broker: a restricted API over a persistent Chromium (Playwright).

The agent never gets raw CDP or JS execution. It can only navigate, read an
accessibility-style snapshot and act on element refs. Sentinel is the only caller
(shared BROWSER_TOKEN). The user can take over at any time; while the user has
control, every agent call is rejected with 423.
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import time
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from playwright.async_api import async_playwright

from app.common.util import token_ok
from app.sentinel.guard import check_url, host_is_private

TOKEN = os.environ.get("BROWSER_TOKEN", "")
PROFILE_DIR = os.environ.get("BROWSER_PROFILE", "/bprofile")
WORKSPACE = os.path.realpath(os.environ.get("WORKSPACE", "/workspace"))
# Default: a real (headed) Chromium on a virtual display (Xvfb). Headless browsers are flagged by Google & co.
# ("This browser may not be secure"), which breaks "Sign in with Google" during a user takeover.
HEADLESS_ENV = os.environ.get("BROWSER_HEADLESS", "")          # "1" force headless, "0" force headed, "" auto
VIEWPORT = {"width": 1280, "height": 800}
# Be a polite client, not a hammering one: a minimum gap between requests to the same site, with a little jitter, and a
# longer cool-off after that site returns a block / 429. This lowers rate-triggered blocks; it is NOT fingerprint evasion.
PACE_GAP = float(os.environ.get("BROWSER_PACE_GAP", "1.3"))     # min seconds between hits to one registered domain
PACE_JITTER = 0.6                                               # up to this much extra, random
PACE_MAX_WAIT = 8.0                                             # never pace-wait longer than this on one request
PACE_BLOCK_HOLD = 45.0                                          # after a block / 429 on a site, hold further hits this long
# Lazy Chromium: it is NOT launched at startup (that held ~2 GB even on an idle install, which OOM-crashed small
# boxes). It starts on the first real web action and is shut down again after this many idle seconds (0 disables the
# idle shutdown but keeps the lazy start). PDF/chart rendering use a separate small headless Chromium, unaffected.
IDLE_SHUTDOWN = float(os.environ.get("BROWSER_IDLE_SHUTDOWN", "600"))   # close the browser after 10 min idle
UA_ENV = os.environ.get("BROWSER_UA", "")
UA_HEADLESS = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")
BLOCKED_EXT = {".exe", ".msi", ".dmg", ".pkg", ".app", ".bat", ".cmd", ".com", ".scr", ".sh", ".ps1", ".vbs", ".jar",
               ".apk", ".deb", ".rpm", ".iso", ".dll", ".so"}
MAX_DOWNLOAD = 200 * 1024 * 1024
SNAPSHOT_JS = open(os.path.join(os.path.dirname(__file__), "snapshot.js"), encoding="utf-8").read()
FEED_JS = open(os.path.join(os.path.dirname(__file__), "feed.js"), encoding="utf-8").read()
BLOCK_JS = open(os.path.join(os.path.dirname(__file__), "block.js"), encoding="utf-8").read()
FIND_JS = open(os.path.join(os.path.dirname(__file__), "find.js"), encoding="utf-8").read()
MARKS_JS = open(os.path.join(os.path.dirname(__file__), "marks.js"), encoding="utf-8").read()
GRID_JS = open(os.path.join(os.path.dirname(__file__), "grid.js"), encoding="utf-8").read()
AT_JS = open(os.path.join(os.path.dirname(__file__), "at.js"), encoding="utf-8").read()


def format_feed(feed: dict, url: str) -> str:
    items = feed.get("items") or []
    out = [f"📰 RSS/Atom feed「{feed.get('feed') or url}」— {len(items)} 条 items (newest first as published). "
           "这就是完整内容，不需要重复打开 This is the whole feed; no need to open it again."]
    for i, it in enumerate(items, 1):
        out.append(f"{i}. {it.get('title') or '(no title)'}" + (f"  [{it['date']}]" if it.get("date") else ""))
        if it.get("link"):
            out.append(f"   {it['link']}")
        if it.get("summary"):
            out.append(f"   {it['summary']}")
    return "\n".join(out)


_LOADING = re.compile(r"^\s*(?:\[e\d+\]\s*)?(?:\w+\s+\")?(?:Loading(?:\.{1,3}|…)?|加载中(?:\.{1,3}|…)?|正在加载(?:\.{1,3}|…)?)\"?\s*$", re.M | re.I)

_CC_SLD2 = {"com", "co", "net", "org", "gov", "edu", "ac"}


def reg_domain(url: str) -> str:
    """The registered domain used for pacing — decathlon.sg, amazon.com.sg → one key per site."""
    try:
        host = (urlparse(url if "://" in (url or "") else "https://" + (url or "")).hostname or "").lower().strip(".")
    except Exception:
        return ""
    parts = [p for p in host.split(".") if p]
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in _CC_SLD2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host

def _display_alive(disp: str) -> bool:
    """True when an X server socket exists for DISPLAY (":99" -> /tmp/.X11-unix/X99); a stale DISPLAY must not pick headed mode."""
    n = str(disp or "").split(".")[0].lstrip(":")
    return bool(n) and (os.path.exists(f"/tmp/.X11-unix/X{n}") or not n.isdigit())


class Broker:
    def __init__(self):
        self.pw = None
        self.ctx = None
        self.pages: dict[str, object] = {}       # task_id -> page
        self.frame_maps: dict[str, dict] = {}    # task_id -> {prefix: frame}
        self.nav_status: dict[str, int] = {}     # task_id -> HTTP status of the last navigation
        self.view_task: str = ""
        self.mode = "agent"                      # agent | user
        self.takeover_reason = ""
        self.takeover_task = ""
        self.requests: dict[str, dict] = {}      # task_id -> {"task_id","reason","ts"}: tasks that asked the user for help
        self.downloads: list[dict] = []
        self.lock = asyncio.Lock()               # only for things that touch every task (start-up)
        self.task_locks: dict[str, asyncio.Lock] = {}   # one per task: tasks no longer wait for each other's page loads
        self.input_lock = asyncio.Lock()
        self.view_pinned_until = 0.0             # the user picked a task to watch: agents don't move the view meanwhile
        self.finished: dict[str, float] = {}     # task_id -> when the task ended (its page may be recycled)
        self.temp_pages: set = set()             # short-lived pages of browser_search / browser_read (not a task's page)
        self.last_used: dict[str, float] = {}
        self.domain_at: dict[str, float] = {}     # registered domain -> when it was last requested (pacing)
        self.domain_hold: dict[str, float] = {}   # registered domain -> don't hit before this time (block / 429 cool-off)
        self.parent: dict = {}                    # popup page -> opener page (e.g. "Sign in with Google" windows)
        self.xvfb = None
        self.headless = True
        self.started = False                     # is the persistent Chromium (self.ctx) currently up?
        self.last_activity = 0.0                 # last real web action, for the idle-shutdown reaper

    async def ensure_pw(self):
        """Start just the Playwright driver (a lightweight node process). Needed by PDF/chart rendering, which launch
        their own small headless Chromium, and by ensure_ctx(). Cheap compared with the persistent browser."""
        if self.pw is not None:
            return
        async with self.lock:
            if self.pw is not None:
                return
            if HEADLESS_ENV == "1":
                self.headless = True
            elif HEADLESS_ENV == "0" or (os.environ.get("DISPLAY") and _display_alive(os.environ["DISPLAY"])):
                self.headless = False
            else:
                self.headless = not self._start_xvfb()   # must happen before the Playwright driver starts (env)
            self.pw = await async_playwright().start()

    async def ensure_ctx(self):
        """Start the persistent Chromium (self.ctx) on demand — the heavy, ~2 GB part. Idempotent and safe to call on
        every web action; if the browser is already up it returns at once. Launching here (not at startup) is what lets
        an idle install sit at near-zero memory instead of OOM-crashing small boxes."""
        if self.started and self.ctx is not None:
            return
        await self.ensure_pw()
        async with self.lock:
            if self.started and self.ctx is not None:
                return
            os.makedirs(PROFILE_DIR, exist_ok=True)
            for lock in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
                try:
                    os.remove(os.path.join(PROFILE_DIR, lock))
                except FileNotFoundError:
                    pass
            kw = {"env": dict(os.environ)}
            ua = UA_ENV or (UA_HEADLESS if self.headless else "")
            if ua:
                kw["user_agent"] = ua
            self.ctx = await self.pw.chromium.launch_persistent_context(
                PROFILE_DIR, headless=self.headless, viewport=VIEWPORT, accept_downloads=True, locale="en-US",
                ignore_default_args=["--enable-automation"],
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled",
                      "--window-size=1280,900", "--no-first-run", "--no-default-browser-check", "--password-store=basic"],
                **kw,
            )
            print(f"[browser] chromium started headless={self.headless} display={os.environ.get('DISPLAY', '')}", flush=True)
            await self.ctx.route("**/*", self._egress_filter)
            self.ctx.on("page", self._on_page)
            for p in self.ctx.pages:
                self._on_page(p)
            self.started = True
            self.last_activity = time.time()

    # backwards-compatible alias (tests / any external caller): start == bring the persistent browser up
    async def start(self):
        await self.ensure_ctx()

    def touch(self):
        """Mark a real web action, so the idle-shutdown reaper doesn't close the browser while it's in use."""
        self.last_activity = time.time()

    def _idle_ok(self) -> bool:
        """True when it is safe to shut the persistent browser down: agent mode, nobody taking over or waiting, the
        user isn't watching a pinned view, no task page is still live, and we've been idle past the threshold."""
        if not self.started or IDLE_SHUTDOWN <= 0:
            return False
        if self.mode == "user" or self.takeover_task or self.requests:
            return False
        now = time.time()
        if now < self.view_pinned_until:
            return False
        for k, p in self.pages.items():
            try:
                if k not in self.finished and not p.is_closed():
                    return False
            except Exception:
                pass
        return (now - self.last_activity) > IDLE_SHUTDOWN

    async def teardown(self):
        """Release the persistent Chromium (and the driver / Xvfb) so an idle install drops back to near-zero memory.
        The next web action calls ensure_ctx() and brings it back. Guarded by the same lock as startup."""
        async with self.lock:
            if not self._idle_ok():   # a task grabbed the browser between the reaper's check and this lock
                return
            ctx, self.ctx, self.started = self.ctx, None, False
            self.pages.clear(); self.frame_maps.clear(); self.last_used.clear()
            self.finished.clear(); self.temp_pages.clear(); self.parent.clear(); self.nav_status.clear()
            self.view_task = ""
            if ctx is not None:
                try:
                    await ctx.close()
                except Exception:
                    pass
            pb = _pdf.get("browser")
            if pb is not None:
                try:
                    await pb.close()
                except Exception:
                    pass
                _pdf["browser"] = None
            pw, self.pw = self.pw, None
            if pw is not None:
                try:
                    await pw.stop()
                except Exception:
                    pass
            if self.xvfb is not None:
                try:
                    self.xvfb.terminate()
                except Exception:
                    pass
                self.xvfb = None
                # the DISPLAY we exported for our own Xvfb must go with it: left behind, the next ensure_pw() would
                # pick "headed" mode with no X server and every Chromium launch would fail (0.2.74 regression)
                if os.environ.get("DISPLAY") == self._own_display:
                    os.environ.pop("DISPLAY", None)
            print("[browser] chromium shut down (idle)", flush=True)

    _own_display: str = ""

    def _start_xvfb(self) -> bool:
        if not shutil.which("Xvfb"):
            return False
        disp = os.environ.get("BROWSER_DISPLAY", ":99")
        n = disp.lstrip(":")
        for f in (f"/tmp/.X{n}-lock", f"/tmp/.X11-unix/X{n}"):
            try:
                os.remove(f)
            except OSError:
                pass
        try:
            self.xvfb = subprocess.Popen(["Xvfb", disp, "-screen", "0", "1280x900x24", "-nolisten", "tcp", "-ac"],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            return False
        for _ in range(50):
            if os.path.exists(f"/tmp/.X11-unix/X{n}"):
                os.environ["DISPLAY"] = disp
                self._own_display = disp
                return True
            if self.xvfb.poll() is not None:
                return False
            time.sleep(0.1)
        return False

    async def stop(self):
        try:
            if self.ctx is not None:
                await self.ctx.close()
        finally:
            if self.pw is not None:
                await self.pw.stop()
            if self.xvfb:
                self.xvfb.terminate()

    # ------------------------------------------------------------ guards
    async def _egress_filter(self, route):
        url = route.request.url
        try:
            p = urlparse(url)
            if p.scheme in ("http", "https", "ws", "wss") and host_is_private(p.hostname or ""):
                return await route.abort("blockedbyclient")
        except Exception:
            return await route.abort("blockedbyclient")
        return await route.continue_()

    def _on_page(self, page):
        page.on("download", lambda d: asyncio.ensure_future(self._on_download(d)))
        page.on("popup", lambda pop, parent=page: self._on_popup(parent, pop))

    def _on_popup(self, parent, pop):
        """A window opened by a task's page (e.g. "Sign in with Google") becomes that task's current page, so the
        agent and the user's live view follow it; when it closes, the task goes back to the page that opened it."""
        for tid, p in list(self.pages.items()):
            if p is parent:
                self.parent[pop] = parent
                self.pages[tid] = pop
                pop.on("close", lambda _=None, tid=tid, pop=pop: self._on_popup_closed(tid, pop))
                break

    def _on_popup_closed(self, tid, pop):
        parent = self.parent.pop(pop, None)
        while parent is not None and parent.is_closed():
            parent = self.parent.pop(parent, None)
        if self.pages.get(tid) is pop and parent is not None:
            self.pages[tid] = parent

    async def _on_download(self, d):
        name = re.sub(r"[^\w.\-() 一-鿿]", "_", d.suggested_filename or "download")[:120]
        base = os.path.join(WORKSPACE, "downloads")
        quarantine = os.path.join(base, ".quarantine")
        os.makedirs(quarantine, exist_ok=True)
        tmp = os.path.join(quarantine, f"{int(time.time())}_{name}")
        rec = {"name": name, "url": d.url, "ts": time.time(), "status": "downloading"}
        self.downloads.append(rec)
        try:
            await d.save_as(tmp)
            size = os.path.getsize(tmp)
            ext = os.path.splitext(name)[1].lower()
            rec["size"] = size
            if ext in BLOCKED_EXT or size > MAX_DOWNLOAD:
                rec["status"] = "blocked"
                rec["reason"] = "可执行文件或文件过大，已隔离 (executable or too large; kept in quarantine)"
                rec["path"] = os.path.relpath(tmp, WORKSPACE)
            else:
                dest = os.path.join(base, name)
                if os.path.exists(dest):
                    stem, e = os.path.splitext(name)
                    dest = os.path.join(base, f"{stem}_{int(time.time())}{e}")
                shutil.move(tmp, dest)
                rec["status"] = "ok"
                rec["path"] = os.path.relpath(dest, WORKSPACE)
        except Exception as e:
            rec["status"] = "failed"
            rec["reason"] = str(e)[:200]

    def task_lock(self, task_id: str) -> asyncio.Lock:
        return self.task_locks.setdefault(task_id or "default", asyncio.Lock())

    def check_agent(self, task_id: str = ""):
        # a takeover pauses only the task whose page the user is driving; other tasks keep working on their own pages
        if self.mode == "user" and (task_id or "default") == (self.takeover_task or "default"):
            raise HTTPException(423, "用户正在接管浏览器，Agent 已暂停 (user takeover in progress)")

    def _follow(self, task_id: str):
        """Move the live view to this task unless the user is watching (or driving) another task, or the task being
        shown is still busy — two tasks running at once no longer make the view flip back and forth."""
        cur = self.view_task
        if cur == task_id:
            return
        if self.mode == "user" or time.time() < self.view_pinned_until:
            return
        p = self.pages.get(cur)
        busy = (p is not None and not p.is_closed() and cur not in self.finished
                and time.time() - self.last_used.get(cur, 0) < 20)
        if not busy:
            self.view_task = task_id

    # ------------------------------------------------------------ pages
    async def page_for(self, task_id: str, create=True):
        task_id = task_id or "default"
        if create:
            await self.ensure_ctx()
        elif not self.started:
            return None
        self.touch()
        p = self.pages.get(task_id)
        if p is not None and not p.is_closed():
            self.last_used[task_id] = time.time()
            self.finished.pop(task_id, None)
            self._follow(task_id)
            return p
        if not create:
            return None
        await self._recycle()
        blank = [pg for pg in self.ctx.pages if pg.url in ("about:blank", "") and pg not in self.pages.values()
                 and pg not in self.temp_pages]
        p = blank[0] if blank else await self.ctx.new_page()
        self.pages[task_id] = p
        self.last_used[task_id] = time.time()
        self.finished.pop(task_id, None)
        self._follow(task_id)
        return p

    async def _recycle(self, keep: int = 8):
        """Close pages of finished tasks after 10 minutes, and when there are too many pages close the least recently
        used finished ones first. Pages of running tasks, of the task being taken over and of tasks waiting for the user
        are never closed here."""
        now = time.time()
        protected = {self.takeover_task, self.view_task} | set(self.requests)
        def closable(k):
            return k not in protected
        old = [k for k, t in self.finished.items() if now - t > 600 and closable(k)]
        if len(self.pages) >= keep:
            done = sorted((k for k in self.pages if k in self.finished and closable(k)), key=lambda k: self.last_used.get(k, 0))
            idle = sorted((k for k in self.pages if k not in self.finished and closable(k)
                           and now - self.last_used.get(k, 0) > 1800), key=lambda k: self.last_used.get(k, 0))
            old += (done + idle)[: len(self.pages) - keep + 1]
        for k in dict.fromkeys(old):
            pg = self.pages.pop(k, None)
            self.finished.pop(k, None)
            self.frame_maps.pop(k, None)
            self.task_locks.pop(k, None)
            if pg is not None:
                try:
                    await pg.close()
                except Exception:
                    pass

    def open_requests(self) -> list[dict]:
        """Takeover requests still waiting, newest first (requests older than 6 h are dropped)."""
        now = time.time()
        for k in [k for k, v in self.requests.items() if now - v.get("ts", 0) > 6 * 3600]:
            self.requests.pop(k, None)
        return sorted(self.requests.values(), key=lambda r: -r.get("ts", 0))

    @property
    def requested(self) -> dict | None:
        reqs = self.open_requests()
        return reqs[0] if reqs else None

    def view_page(self):
        p = self.pages.get(self.view_task)
        if p is not None and not p.is_closed():
            return p
        for tid, pg in self.pages.items():
            if not pg.is_closed():
                self.view_task = tid
                return pg
        return self.ctx.pages[0] if self.ctx and self.ctx.pages else None

    async def settle(self, page, ms=700):
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass
        await asyncio.sleep(ms / 1000)

    def pace_wait(self, url: str, now: float | None = None) -> float:
        """How long to wait before hitting this site, so we don't hammer it (pure function, for testing)."""
        import random
        dom = reg_domain(url)
        if not dom:
            return 0.0
        now = now if now is not None else time.time()
        hold = self.domain_hold.get(dom, 0.0)
        if hold > now:
            return min(hold - now, PACE_MAX_WAIT)
        last = self.domain_at.get(dom, 0.0)
        gap = PACE_GAP + random.random() * PACE_JITTER
        return max(0.0, min(last + gap - now, PACE_MAX_WAIT))

    async def pace(self, url: str):
        w = self.pace_wait(url)
        if w > 0:
            await asyncio.sleep(w)
        dom = reg_domain(url)
        if dom:
            self.domain_at[dom] = time.time()

    def note_block(self, url: str):
        """A site returned a bot wall / 429: cool off before hitting it again this session."""
        dom = reg_domain(url)
        if dom:
            self.domain_hold[dom] = time.time() + PACE_BLOCK_HOLD

    async def snapshot(self, task_id: str, max_chars=12000, near: bool = False) -> dict:
        """The page as text. A list still showing "Loading..." gets up to ~8 s more (2026-10-06 golden G04: decathlon.sg's
        search results were still loading, the agent re-opened the URL five times and gave up)."""
        snap = await self._snapshot_once(task_id, max_chars, near)
        for _ in range(2):
            if snap.get("feed") or not _LOADING.search(snap.get("snapshot") or ""):
                break
            page = await self.page_for(task_id)
            try:
                await page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass
            await asyncio.sleep(1.0)
            snap = await self._snapshot_once(task_id, max_chars, near)
        return snap

    async def _snapshot_once(self, task_id: str, max_chars=12000, near: bool = False) -> dict:
        page = await self.page_for(task_id)
        await self.settle(page, 200)
        try:
            feed = await page.main_frame.evaluate(FEED_JS)
        except Exception:
            feed = None
        if feed and feed.get("items"):
            tabs = len([p for p in self.ctx.pages if not p.is_closed()])
            title = feed.get("feed") or ""
            return {"url": page.url, "title": title, "snapshot": format_feed(feed, page.url), "truncated": False,
                    "tabs": tabs, "feed": True}
        fmap = {}
        parts = []
        # Payment forms put every card field in its own iframe, after many tracker / captcha frames (2026-10-05 decathlon.sg:
        # Adyen's expiry and CVC boxes were frames 8 and 9, so only the number box was listed and all three card values
        # were typed into it). Read up to 24 frames; empty ones add nothing to the snapshot.
        frames = [f for f in page.frames if not f.is_detached()]
        iframe_parts = []
        for i, fr in enumerate(frames[:24]):
            prefix = "" if i == 0 else f"f{i}"
            fmap[prefix] = fr
            try:
                txt = await fr.evaluate(SNAPSHOT_JS, {"prefix": prefix, "near": bool(near and i == 0)})
            except Exception as e:
                txt = f"(无法读取 frame: {str(e)[:80]})" if i == 0 else ""
            if i == 0:
                parts.append(txt)
            elif txt and txt.strip():
                iframe_parts.append(f"--- iframe {prefix}: {fr.url[:100]} ---\n{txt[:1500]}")
        self.frame_maps[task_id or "default"] = fmap
        title = ""
        try:
            title = await page.title()
        except Exception:
            pass
        max_chars = max(2000, min(int(max_chars or 12000), 40000))
        # iframes (card fields, chat widgets) come after the page and must not be cut off by a long page
        frames_txt = "\n".join(iframe_parts)[:max(1500, max_chars // 3)]
        main = "\n".join(parts)
        room = max(1000, max_chars - len(frames_txt))
        truncated = len(main) > room
        if truncated:
            main = main[:room] + ("\n…[快照已截断 snapshot truncated — browser_find(\"text\") locates anything on the page; "
                                  "browser_scroll shows the part around the new position; browser_look lets you see the page]")
        body = main + ("\n" + frames_txt if frames_txt else "")
        tabs = len([p for p in self.ctx.pages if not p.is_closed()])
        if near:
            body = "(showing the part of the page around the current scroll position)\n" + body
        return {"url": page.url, "title": title, "snapshot": body, "truncated": truncated, "tabs": tabs}

    async def find(self, task_id: str, query: str) -> dict:
        """Locate elements by text anywhere on the page (all frames); refs stay valid for click/type."""
        snap = await self.snapshot(task_id, 2000)          # assigns fresh refs in every frame
        matches = []
        for prefix, fr in (self.frame_maps.get(task_id or "default") or {}).items():
            try:
                found = await fr.evaluate(FIND_JS, query)
            except Exception:
                found = []
            matches += found
        matches.sort(key=lambda m: -m.get("score", 0))
        matches = matches[:25]
        lines = [f"browser_find \"{query}\": {len(matches)} match(es) on {snap['url']}"]
        for m in matches:
            ctx = m.get("context") or ""
            lines.append(f"[{m['ref']}] {m['role']} \"{m['name']}\" ({m['where']})" + (f"\n    context: {ctx}" if ctx and ctx != m['name'] else ""))
        if not matches:
            lines.append("(nothing found — try other words, browser_scroll to load more, or browser_look to see the page)")
        return {"url": snap["url"], "title": snap["title"], "snapshot": "\n".join(lines), "tabs": snap["tabs"], "matches": len(matches)}

    async def look(self, task_id: str) -> dict:
        """Screenshot of the viewport with every visible element labelled by its ref (set-of-marks) for a vision model."""
        page = await self.page_for(task_id)
        await self.snapshot(task_id, 2000)                 # fresh refs
        marks, text = [], ""
        # label the page and every iframe (chat widgets like Zendesk/Intercom live in iframes; their refs look like f1e3)
        frames = [fr for fr in (self.frame_maps.get(task_id or "default") or {}).values() if not fr.is_detached()] or [page.main_frame]
        try:
            for fr in frames:
                try:
                    got = await fr.evaluate(MARKS_JS, "draw")
                except Exception:
                    continue
                marks += got.get("marks") or []
                if got.get("text"):
                    text += ("\n" if text else "") + got["text"]
            img = await page.screenshot(type="jpeg", quality=70, timeout=10000)
        finally:
            for fr in frames:
                try:
                    await fr.evaluate(MARKS_JS, "clear")
                except Exception:
                    pass
        text = text[:3000]
        title = ""
        try:
            title = await page.title()
        except Exception:
            pass
        lines = [f"[{m['ref']}] {m['role']} \"{m['name']}\"" for m in marks]
        import base64 as _b64
        return {"url": page.url, "title": title, "image_b64": _b64.b64encode(img).decode(), "image_type": "image/jpeg",
                "marks": marks, "snapshot": "Labelled elements visible on screen:\n" + "\n".join(lines)
                + ("\n\nText visible on screen:\n" + text if text else ""),
                "viewport": VIEWPORT, "tabs": len([p for p in self.ctx.pages if not p.is_closed()])}

    async def grid(self, task_id: str, region=None, cols=0, rows=0, labels="letters", mark=None) -> dict:
        """Screenshot for visual targeting: a labelled grid over the viewport (or a zoomed region), and/or a red marker."""
        page = await self.page_for(task_id)
        vw, vh = VIEWPORT["width"], VIEWPORT["height"]
        try:
            vw, vh = await page.evaluate("[window.innerWidth, window.innerHeight]")
        except Exception:
            pass
        if region:
            x, y, w, h = (float(v) for v in region)
            x, y = max(0.0, min(x, vw - 20)), max(0.0, min(y, vh - 20))
            region = [x, y, max(20.0, min(w, vw - x)), max(20.0, min(h, vh - y))]
        opts = {"mode": "draw", "region": region, "cols": int(cols or 0), "rows": int(rows or 0), "labels": labels,
                "mark": [float(mark[0]), float(mark[1])] if mark else None}
        try:
            await page.main_frame.evaluate(GRID_JS, opts)
            shot = {"type": "jpeg", "quality": 75, "timeout": 10000}
            if region:
                shot["clip"] = {"x": region[0], "y": region[1], "width": region[2], "height": region[3]}
            img = await page.screenshot(**shot)
        finally:
            try:
                await page.main_frame.evaluate(GRID_JS, {"mode": "clear"})
            except Exception:
                pass
        import base64 as _b64
        out = {"url": page.url, "title": await page.title(), "image_b64": _b64.b64encode(img).decode(), "image_type": "image/jpeg",
               "region": region or [0, 0, vw, vh], "cols": opts["cols"], "rows": opts["rows"], "labels": labels,
               "viewport": {"width": vw, "height": vh}, "tabs": len([p for p in self.ctx.pages if not p.is_closed()]),
               "snapshot": ""}
        if mark:
            out["at"] = await self.at(task_id, mark[0], mark[1])
        return out

    async def at(self, task_id: str, x: float, y: float) -> dict:
        """The element under a viewport point, looking into iframes (also cross-origin) and open shadow roots."""
        page = await self.page_for(task_id)
        frame, fx, fy, frames = page.main_frame, float(x), float(y), []
        for _ in range(4):
            try:
                info = await frame.evaluate(AT_JS, [fx, fy])
            except Exception as e:
                return {"tag": "", "name": "", "error": str(e)[:120], "frames": frames}
            if not info:
                return {"tag": "", "name": "", "frames": frames}
            if not info.get("iframe"):
                info["frames"] = frames
                info["page_url"], info["page_title"] = page.url, await page.title()
                return info
            bx, by = info["box"][0], info["box"][1]
            child = None
            for fr in frame.child_frames:
                try:
                    el = await fr.frame_element()
                    bb = await el.bounding_box()
                except Exception:
                    continue
                if bb and abs(bb["x"] - bx) < 3 and abs(bb["y"] - by) < 3 or (bb and bb["x"] <= fx <= bb["x"] + bb["width"]
                                                                               and bb["y"] <= fy <= bb["y"] + bb["height"]):
                    child = fr
                    break
            if child is None:
                return {"tag": "iframe", "name": info.get("src", ""), "frames": frames}
            frames.append(child.url.split("?")[0][:160])
            frame, fx, fy = child, fx - bx, fy - by
        return {"tag": "", "name": "", "frames": frames}

    MEDIA_MAX = 50 * 1024 * 1024
    MEDIA_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp", "image/avif": ".avif",
                   "image/bmp": ".bmp", "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov",
                   "audio/mpeg": ".mp3", "audio/mp4": ".m4a", "audio/ogg": ".ogg", "audio/wav": ".wav", "audio/x-wav": ".wav"}

    async def save_media(self, task_id: str, page, ref: str = "", url: str = "", name: str = "") -> dict:
        """Save an image / video / audio from the page into workspace/media/<YYYY-MM>/ (the agent then send_files it).
        By element ref (img, video, picture, element with a background image) or by its URL. Falls back to a screenshot of
        the element when the file itself can't be fetched (e.g. blob: images)."""
        import base64 as _b64
        loc = None
        if ref:
            loc = self.locate(task_id, ref)
            try:
                found = await loc.evaluate("""el => {
                    const pick = e => {
                      if (!e) return '';
                      if (e.tagName === 'IMG') return e.currentSrc || e.src || '';
                      if (e.tagName === 'VIDEO' || e.tagName === 'AUDIO') {
                        const s = e.currentSrc || e.src || (e.querySelector('source[src]') || {}).src || '';
                        return s || (e.poster || '');
                      }
                      if (e.tagName === 'SOURCE') return e.src || '';
                      const bg = getComputedStyle(e).backgroundImage || '';
                      const m = bg.match(/url\(["']?(.*?)["']?\)/);
                      return m ? new URL(m[1], location.href).href : '';
                    };
                    let u = pick(el);
                    if (!u) { const inner = el.querySelector('img,video,audio,picture img'); u = pick(inner); }
                    return {url: u, tag: el.tagName.toLowerCase(), alt: (el.alt || el.title || el.getAttribute('aria-label') || '').slice(0, 80)};
                }""", timeout=5000)
            except Exception as e:
                raise HTTPException(409, f"找不到元素 {ref}，请重新获取快照 (element not found): {str(e)[:100]}")
            url = url or found.get("url") or ""
            name = name or found.get("alt") or ""
        url = (url or "").strip()
        data, mime, how = b"", "", "download"
        if url.startswith("data:"):
            m = re.match(r"data:([\w/+.-]+)(;base64)?,(.*)", url, re.S)
            if m and m.group(2):
                data, mime = _b64.b64decode(m.group(3)[: self.MEDIA_MAX * 2]), m.group(1).lower()
        elif url.startswith(("http://", "https://")):
            ok, why = check_url(url)
            if not ok:
                raise HTTPException(403, why)
            try:
                resp = await page.context.request.get(url, timeout=45000, max_redirects=5,
                                                      headers={"Referer": page.url, "Accept": "image/*,video/*,audio/*,*/*;q=0.5"})
                mime = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
                if int(resp.headers.get("content-length") or 0) > self.MEDIA_MAX:
                    raise HTTPException(413, "文件超过 50 MB (file over 50 MB)")
                if resp.ok:
                    data = await resp.body()
                await resp.dispose()
            except HTTPException:
                raise
            except Exception:
                data = b""
        if data and mime not in self.MEDIA_TYPES:
            data = b""                                    # html, svg, scripts… are never saved as media
        if not data and loc is not None:
            try:                                          # last resort: what the user sees
                data, mime, how = await loc.screenshot(type="png", timeout=10000), "image/png", "screenshot"
            except Exception:
                data = b""
        if not data:
            raise HTTPException(422, "无法保存这个图片/视频（可能是流媒体或受保护内容）(could not save this media — it may be "
                                     "streamed or protected; try another element or a screenshot)")
        if len(data) > self.MEDIA_MAX:
            raise HTTPException(413, "文件超过 50 MB (file over 50 MB)")
        stem = re.sub(r"[^\w\-() 一-鿿]+", "_", name or os.path.splitext(os.path.basename(urlparse(url).path or ""))[0] or "media")
        stem = stem.strip("_ ")[:60] or "media"
        folder = os.path.join(WORKSPACE, "media", time.strftime("%Y-%m"))
        os.makedirs(folder, exist_ok=True)
        ext = self.MEDIA_TYPES[mime]
        dest, n = os.path.join(folder, stem + ext), 1
        while os.path.exists(dest):
            n += 1
            dest = os.path.join(folder, f"{stem}_{n}{ext}")
        with open(dest, "wb") as f:
            f.write(data)
        return {"path": os.path.relpath(dest, WORKSPACE), "mime": mime, "size": len(data), "method": how,
                "source": url[:300] if not url.startswith("data:") else "data: URL"}

    def locate(self, task_id: str, ref: str):
        ref = str(ref).strip().strip("[]")
        m = re.fullmatch(r"(f\d+)?e\d+", ref)
        if not m:
            raise HTTPException(400, f"无效的 ref: {ref}（请使用快照中的 [e12] 之类的 ref）")
        prefix = m.group(1) or ""
        fmap = self.frame_maps.get(task_id or "default") or {}
        fr = fmap.get(prefix)
        if fr is None or fr.is_detached():
            raise HTTPException(409, "页面已变化，请先调用 browser_snapshot 获取新的 ref (stale ref, take a new snapshot)")
        return fr.locator(f'[data-persona-ref="{ref}"]').first

    async def describe(self, task_id: str, ref: str) -> dict:
        loc = self.locate(task_id, ref)
        try:
            info = await loc.evaluate("""el => ({
                tag: el.tagName.toLowerCase(),
                role: el.getAttribute('role') || '',
                name: (el.getAttribute('aria-label') || (el.labels && el.labels[0] && el.labels[0].innerText) || el.innerText || (['submit','button','reset'].includes((el.type||'').toLowerCase()) ? el.value : '') || el.getAttribute('placeholder') || el.getAttribute('name') || el.getAttribute('title') || '').trim().slice(0,200),
                editable: !!el.isContentEditable,
                autocomplete: (el.getAttribute('autocomplete') || '').toLowerCase().slice(0,40),
                input_type: (el.type || '').toLowerCase(),
                is_password: (el.type || '').toLowerCase() === 'password' || (el.getAttribute('autocomplete')||'').includes('password'),
                in_form: !!el.closest('form'),
                // a site search box whose label is a rotating promo text (2026-10-04 FairPrice: "1 for $21.30 - ...")
                searchy: (el.type || '').toLowerCase() === 'search' || /search|query|keyword|^q$/i.test((el.getAttribute('name') || '') + ' ' + (el.id || '')) ||
                         (el.getAttribute('enterkeyhint') || '') === 'search' || !!(el.closest('form') && (el.closest('form').getAttribute('role') === 'search' ||
                         /search|query/i.test(el.closest('form').getAttribute('action') || ''))) || !!el.closest('[role=search]'),
                href: el.getAttribute('href') || ''
            })""", timeout=5000)
        except Exception as e:
            raise HTTPException(409, f"找不到元素 {ref}，请重新获取快照 (element not found): {str(e)[:100]}")
        page = await self.page_for(task_id)
        info["page_url"] = page.url
        try:
            info["page_title"] = await page.title()
        except Exception:
            info["page_title"] = ""
        return info

    async def focused(self, task_id: str) -> dict:
        page = await self.page_for(task_id)
        try:
            return await page.evaluate("""() => { const el = document.activeElement; if (!el || el === document.body) return {};
                return {tag: el.tagName.toLowerCase(), role: el.getAttribute('role')||'', name: (el.getAttribute('aria-label')||el.getAttribute('placeholder')||el.name||'').slice(0,200),
                        input_type: (el.type||'').toLowerCase(), in_form: !!el.closest('form')}; }""")
        except Exception:
            return {}


broker = Broker()


async def _idle_reaper():
    """Shut the persistent Chromium down after it has been idle, so an unused install doesn't hold ~2 GB."""
    while True:
        try:
            await asyncio.sleep(60)
            if broker._idle_ok():
                await broker.teardown()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[browser] idle reaper error: {str(e)[:150]}", flush=True)


@asynccontextmanager
async def lifespan(app):
    # Chromium is NOT launched here anymore — it starts lazily on the first web action (ensure_ctx). The browser
    # service itself stays up and /health answers immediately, so the pod is Ready even before/without a browser.
    reaper = asyncio.create_task(_idle_reaper()) if IDLE_SHUTDOWN > 0 else None
    try:
        yield
    finally:
        if reaper is not None:
            reaper.cancel()
            try:
                await reaper
            except (asyncio.CancelledError, Exception):
                pass
        await broker.stop()


app = FastAPI(lifespan=lifespan, title="OMuse Browser Broker")


def auth(x_browser_token: str | None = Header(default=None)):
    if not token_ok(x_browser_token, TOKEN):
        raise HTTPException(401, "unauthorized")


@app.get("/health")
async def health():
    return {"ok": True, "mode": broker.mode, "headless": broker.headless, "started": broker.started}


# ================================================================== local PDF export
# A separate headless Chromium (not the user's browser profile), JavaScript off and every network request blocked:
# documents are printed on this machine and nothing in them can reach the internet while rendering.
PDF_MAX_SRC = 5_000_000
_pdf = {"browser": None, "lock": asyncio.Lock()}


def _ws(rel: str) -> str:
    p = os.path.realpath(os.path.join(WORKSPACE, str(rel or "").strip().lstrip("/")))
    if not p.startswith(WORKSPACE + os.sep) or os.sep + ".quarantine" in p:
        raise HTTPException(400, "路径必须在工作区内 (path must be inside the workspace)")
    return p


def _img_data(base_dir: str):
    import base64
    import mimetypes

    def resolve(src: str) -> str | None:
        if re.match(r"^[a-z]+:", src, re.I):
            return None   # remote images are not fetched (no network while printing)
        try:
            p = os.path.realpath(os.path.join(base_dir, src))
            if not p.startswith(WORKSPACE + os.sep) or not os.path.isfile(p) or os.path.getsize(p) > 10_000_000:
                return None
            mt = mimetypes.guess_type(p)[0] or ""
            if mt not in ("image/png", "image/jpeg", "image/gif", "image/webp"):
                return None
            with open(p, "rb") as f:
                return f"data:{mt};base64," + base64.b64encode(f.read()).decode()
        except OSError:
            return None
    return resolve


async def _print_pdf(doc: str) -> bytes:
    await broker.ensure_pw()
    broker.touch()
    async with _pdf["lock"]:
        b = _pdf["browser"]
        if b is None or not b.is_connected():
            b = _pdf["browser"] = await broker.pw.chromium.launch(headless=True)
        ctx = await b.new_context(java_script_enabled=False, locale="zh-CN")
        try:
            async def block(route):
                if route.request.url.startswith("data:"):
                    await route.continue_()
                else:
                    await route.abort()
            await ctx.route("**/*", block)
            page = await ctx.new_page()
            await page.set_content(doc, wait_until="load", timeout=30000)
            footer = ('<div style="width:100%;font-size:8px;color:#9ca3af;text-align:center;font-family:sans-serif">'
                      '<span class="pageNumber"></span> / <span class="totalPages"></span></div>')
            return await page.pdf(format="A4", print_background=True, prefer_css_page_size=True, display_header_footer=True,
                                  header_template="<div></div>", footer_template=footer,
                                  margin={"top": "18mm", "bottom": "20mm", "left": "16mm", "right": "16mm"})
        finally:
            await ctx.close()


@app.post("/pdf", dependencies=[Depends(auth)])
async def make_pdf(req: Request):
    from app.common.mdhtml import md_to_html, page as html_page
    b = await req.json()
    src_rel, title = str(b.get("source") or ""), str(b.get("title") or "")
    base = WORKSPACE
    if src_rel:
        sp = _ws(src_rel)
        if not os.path.isfile(sp):
            raise HTTPException(404, f"文件不存在 file not found: {src_rel}")
        if os.path.getsize(sp) > PDF_MAX_SRC:
            raise HTTPException(400, "源文件太大 (source over 5 MB)")
        with open(sp, encoding="utf-8", errors="replace") as f:
            text = f.read()
        base = os.path.dirname(sp)
        ext = os.path.splitext(sp)[1].lower()
    else:
        text, ext = str(b.get("markdown") or ""), ".md"
        if not text.strip():
            raise HTTPException(400, "没有内容 (nothing to print)")
    if not title:
        m = re.search(r"^#\s+(.+)$", text, re.M)
        title = m.group(1).strip() if m else (os.path.splitext(os.path.basename(src_rel))[0] if src_rel else "Document")
    if ext in (".html", ".htm"):
        doc = text   # printed with JavaScript off and no network, so scripts / trackers in it do nothing
    elif ext in (".md", ".markdown", ".txt", ""):
        body = md_to_html(text, _img_data(base)) if ext != ".txt" else f"<pre>{__import__('html').escape(text)}</pre>"
        doc = html_page(title, body)
    else:
        raise HTTPException(400, f"不支持的格式 unsupported source type: {ext}（支持 .md .txt .html）")
    out_rel = str(b.get("output") or "")
    if not out_rel:
        out_rel = (os.path.splitext(src_rel)[0] if src_rel else "reports/" + re.sub(r"[^\w\-\u4e00-\u9fff]+", "_", title)[:60]) + ".pdf"
    if not out_rel.lower().endswith(".pdf"):
        out_rel += ".pdf"
    op = _ws(out_rel)
    data = await _print_pdf(doc)
    os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, "wb") as f:
        f.write(data)
    return {"path": os.path.relpath(op, WORKSPACE), "size": len(data), "title": title}


@app.post("/png", dependencies=[Depends(auth)])
async def make_png(req: Request):
    """Render an SVG (a chart made by the runtime) to a PNG in the workspace: JavaScript off, no network,
    so the system CJK fonts are used and nothing in the SVG can reach out."""
    b = await req.json()
    svg = str(b.get("svg") or "")
    if not svg.lstrip().startswith("<svg") or len(svg) > 3_000_000:
        raise HTTPException(400, "需要 SVG (svg required, max 3 MB)")
    out_rel = str(b.get("output") or "charts/chart.png")
    if not out_rel.lower().endswith(".png"):
        out_rel += ".png"
    op = _ws(out_rel)
    await broker.ensure_pw()
    broker.touch()
    async with _pdf["lock"]:
        br = _pdf["browser"]
        if br is None or not br.is_connected():
            br = _pdf["browser"] = await broker.pw.chromium.launch(headless=True)
        ctx = await br.new_context(java_script_enabled=False, device_scale_factor=2, locale="zh-CN")
        try:
            async def block(route):
                if route.request.url.startswith("data:"):
                    await route.continue_()
                else:
                    await route.abort()
            await ctx.route("**/*", block)
            page = await ctx.new_page()
            await page.set_content(f"<!doctype html><html><body style='margin:0;background:#fff'>{svg}</body></html>",
                                   wait_until="load", timeout=30000)
            data = await page.locator("svg").first.screenshot(type="png", timeout=30000)
        finally:
            await ctx.close()
    os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, "wb") as f:
        f.write(data)
    return {"path": os.path.relpath(op, WORKSPACE), "size": len(data)}


# ================================================================== compose: exact text on an image (Round 8)
def _css_color(s: str, default: str) -> str:
    s = str(s or "").strip()
    return s if re.fullmatch(r"#[0-9a-fA-F]{3,8}|[a-zA-Z]{3,20}|rgba?\([0-9., %]+\)", s) else default


def _image_size(path: str) -> tuple[int, int]:
    """(width, height) from the file header of a PNG / JPEG / GIF / WebP — no imaging library needed."""
    import struct
    with open(path, "rb") as f:
        head = f.read(32)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", head[16:24])
            return int(w), int(h)
        if head[:6] in (b"GIF87a", b"GIF89a"):
            w, h = struct.unpack("<HH", head[6:10])
            return int(w), int(h)
        if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
            tag = head[12:16]
            f.seek(12)
            chunk = f.read(30)
            if tag == b"VP8X":
                w = 1 + int.from_bytes(chunk[12:15], "little"); h = 1 + int.from_bytes(chunk[15:18], "little")
                return w, h
            if tag == b"VP8L":
                b0, b1, b2, b3 = chunk[9:13]
                return 1 + (((b1 & 0x3F) << 8) | b0), 1 + (((b3 & 0xF) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
            if tag == b"VP8 ":
                w, h = struct.unpack("<HH", chunk[14:18])
                return int(w & 0x3FFF), int(h & 0x3FFF)
        if head[:2] == b"\xff\xd8":
            f.seek(2)
            while True:
                marker = f.read(2)
                if len(marker) < 2 or marker[0] != 0xFF:
                    break
                m = marker[1]
                if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
                    continue
                (ln,) = struct.unpack(">H", f.read(2))
                if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    data = f.read(5)
                    h, w = struct.unpack(">HH", data[1:5])
                    return int(w), int(h)
                f.seek(ln - 2, 1)
    try:
        from PIL import Image as _Img
        with _Img.open(path) as im:
            return im.size
    except ImportError:
        raise ValueError("unsupported image format (png/jpeg/gif/webp only)")



@app.post("/compose", dependencies=[Depends(auth)])
async def compose_image(req: Request):
    """Overlay exact text on a workspace image and save a PNG: JavaScript off, no network, the image is loaded from the
    workspace file, the text is laid out by the browser's own (CJK-capable) fonts, then the composed element is
    screenshotted at 1:1. Image models misspell text; this guarantees the letters a poster / caption / wordmark needs."""
    import html as _html
    b = await req.json()
    src = _ws(str(b.get("image") or ""))
    if not os.path.isfile(src):
        raise HTTPException(404, "图片不存在 image not found")
    text = str(b.get("text") or "").strip()
    if not text or len(text) > 400:
        raise HTTPException(400, "需要 1-400 字的文字 text required (1-400 chars)")
    pos = str(b.get("position") or "bottom").lower()
    if pos not in ("top", "bottom", "center", "top-left", "top-right", "bottom-left", "bottom-right"):
        pos = "bottom"
    try:
        size = int(b.get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    if size:
        size = max(12, min(size, 400))   # a given size is clamped; 0 = auto-size below
    color = _css_color(b.get("color"), "#ffffff")
    band = _css_color(b.get("band"), "") if b.get("band") not in (None, "", False) else ""
    if b.get("band") is True:
        band = "rgba(0,0,0,0.45)"
    weight = str(b.get("weight") or "700")
    if weight not in ("300", "400", "500", "600", "700", "800", "900"):
        weight = "700"
    align = str(b.get("align") or ("center" if pos in ("top", "bottom", "center") else ("left" if "left" in pos else "right"))).lower()
    if align not in ("left", "center", "right"):
        align = "center"
    font = str(b.get("font") or "").strip()[:80]
    try:
        pad = max(0, min(int(b.get("padding") or 24), 200))
    except (TypeError, ValueError):
        pad = 24
    out_rel = str(b.get("output") or "")
    if not out_rel:
        stem, _ = os.path.splitext(os.path.relpath(src, WORKSPACE))
        out_rel = stem + "_text.png"
    if not out_rel.lower().endswith(".png"):
        out_rel += ".png"
    op = _ws(out_rel)
    # size the text to the picture when not given: ~1/12 of the shorter side, smaller for long text
    try:
        w, h = _image_size(src)   # header parse, no Pillow (the playwright image does not ship it)
    except Exception as e:
        raise HTTPException(400, f"无法读取图片 cannot read image: {str(e)[:100]}")
    if not size:
        size = max(14, int(min(w, h) / 12 * (1.0 if len(text) <= 16 else 0.75 if len(text) <= 40 else 0.55)))
    v = "top" if pos.startswith("top") else "bottom" if pos.startswith("bottom") else "center"
    just = {"top": "flex-start", "bottom": "flex-end", "center": "center"}[v]
    fam = (_html.escape(font) + ", ") if font else ""
    cap_bg = f"background:{band};" if band else ""
    page_html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;background:#fff}}
#w{{position:relative;width:{w}px;height:{h}px;overflow:hidden}}
#w img{{display:block;width:{w}px;height:{h}px}}
#c{{position:absolute;left:0;top:0;width:{w}px;height:{h}px;display:flex;flex-direction:column;justify-content:{just};align-items:stretch;box-sizing:border-box;padding:{pad}px}}
#t{{{cap_bg}color:{color};font:{weight} {size}px/1.25 {fam}"Noto Sans CJK SC","Noto Sans SC","PingFang SC","Microsoft YaHei","Helvetica Neue",Arial,sans-serif;text-align:{align};padding:{int(size*0.35)}px {int(size*0.6)}px;white-space:pre-wrap;word-break:break-word;text-shadow:{'none' if band else '0 2px 6px rgba(0,0,0,.6), 0 0 2px rgba(0,0,0,.8)'};border-radius:{int(size*0.25)}px}}
</style></head><body><div id="w"><img src="file://{src}"><div id="c"><div id="t">{_html.escape(text)}</div></div></div></body></html>"""
    tmp = os.path.join("/tmp", f"compose_{int(time.time()*1000)}_{os.getpid()}.html")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(page_html)
    await broker.ensure_pw()
    broker.touch()
    async with _pdf["lock"]:
        br = _pdf["browser"]
        if br is None or not br.is_connected():
            br = _pdf["browser"] = await broker.pw.chromium.launch(headless=True)
        ctx = await br.new_context(java_script_enabled=False, device_scale_factor=1, viewport={"width": w, "height": h})
        try:
            async def block(route):
                if route.request.url.startswith(("file://", "data:")):
                    await route.continue_()
                else:
                    await route.abort()
            await ctx.route("**/*", block)
            page = await ctx.new_page()
            await page.goto("file://" + tmp, wait_until="load", timeout=30000)
            data = await page.locator("#w").screenshot(type="png", timeout=30000)
        finally:
            await ctx.close()
            try:
                os.remove(tmp)
            except OSError:
                pass
    os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, "wb") as f:
        f.write(data)
    return {"path": os.path.relpath(op, WORKSPACE), "size": len(data), "width": w, "height": h, "font_px": size}


# ================================================================== fast search / read (no snapshot round trips)
SEARCH_JS = r"""() => {
  const out = [];
  const dec = (h) => { try { const u = new URL(h, location.href); const g = u.searchParams.get('uddg');
                             return g ? decodeURIComponent(g) : u.href; } catch (e) { return h; } };
  for (const r of document.querySelectorAll('.result, .web-result')) {
    const a = r.querySelector('a.result__a'); if (!a) continue;
    const sn = r.querySelector('.result__snippet');
    out.push({title: a.innerText.trim(), url: dec(a.getAttribute('href')), snippet: sn ? sn.innerText.trim() : ''});
  }
  if (!out.length) for (const r of document.querySelectorAll('li.b_algo')) {   // Bing
    const a = r.querySelector('h2 a'); if (!a) continue;
    let url = a.href; const m = url.match(/[?&]u=a1([^&]+)/);
    if (m) { try { url = atob(m[1].replace(/-/g, '+').replace(/_/g, '/')); } catch (e) {} }
    const sn = r.querySelector('.b_caption p, p');
    out.push({title: a.innerText.trim(), url, snippet: sn ? sn.innerText.trim() : ''});
  }
  return out;
}"""
READ_JS = r"""(limit) => {
  const pick = document.querySelector('article') || document.querySelector('main, [role=main]') || document.body;
  let t = (pick ? pick.innerText : '') || '';
  if (t.length < 400 && document.body) t = document.body.innerText || t;
  t = t.replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  return {title: document.title, url: location.href, text: t.slice(0, limit), length: t.length};
}"""


async def _temp_page():
    await broker.ensure_ctx()
    broker.touch()
    p = await broker.ctx.new_page()
    broker.temp_pages.add(p)
    return p


async def _close_temp(p):
    broker.temp_pages.discard(p)
    try:
        await p.close()
    except Exception:
        pass


async def web_search(query: str, n: int = 8) -> dict:
    from urllib.parse import quote_plus
    engines = [("duckduckgo", "https://html.duckduckgo.com/html/?q=" + quote_plus(query)),
               ("bing", "https://www.bing.com/search?setlang=en&q=" + quote_plus(query))]
    if os.environ.get("SEARCH_ENGINES"):   # tests: "name=url-prefix,..."
        engines = [(e.split("=", 1)[0], e.split("=", 1)[1] + quote_plus(query))
                   for e in os.environ["SEARCH_ENGINES"].split(",") if "=" in e]
    last = ""
    for name, url in engines:
        p = await _temp_page()
        try:
            await p.goto(url, wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(0.8)
            res = await p.evaluate(SEARCH_JS)
        except Exception as e:
            res, last = [], f"{name}: {str(e)[:120]}"
        finally:
            await _close_temp(p)
        res = [r for r in res if r.get("url", "").startswith("http") and check_url(r["url"])[0]]
        if res:
            return {"query": query, "engine": name, "results": res[:max(1, min(int(n or 8), 10))]}
        last = last or f"{name}: no results"
    return {"query": query, "engine": "", "results": [], "error": last}


async def web_read(urls: list[str], limit: int = 6000) -> dict:
    async def one(u: str) -> dict:
        ok, why = check_url(u)
        if not ok:
            return {"url": u, "error": why}
        p = await _temp_page()
        try:
            await broker.pace(u)
            resp = await p.goto(u, wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(1.2)
            r = await p.evaluate(READ_JS, limit)
            try:
                blk = await p.main_frame.evaluate(BLOCK_JS, resp.status if resp else 0)
            except Exception:
                blk = None
            if blk:
                r["blocked"] = blk
                broker.note_block(u)
            r["status"] = resp.status if resp else 0
            return r
        except Exception as e:
            msg = str(e)
            if "ERR_BLOCKED_BY_CLIENT" in msg:
                return {"url": u, "error": "该地址被安全策略拦截 (blocked by egress policy)"}
            return {"url": u, "error": f"打开失败 could not open: {msg[:160]}"}
        finally:
            await _close_temp(p)
    pages = await asyncio.gather(*[one(str(u)) for u in urls[:4]])
    return {"pages": pages}


# ================================================================== agent API
@app.post("/agent/{action}", dependencies=[Depends(auth)])
async def agent_action(action: str, req: Request):
    body = await req.json()
    task_id = body.get("task_id") or "default"
    await broker.ensure_ctx()   # every agent web action needs the persistent browser (lazy start)
    broker.touch()
    if action == "describe":
        return await broker.describe(task_id, body.get("ref", ""))
    if action == "page_text":   # Sentinel: the order total shown on the page before a pre-approved "Place order" click
        page = await broker.page_for(task_id)
        try:
            txt = await page.evaluate("() => (document.body && document.body.innerText || '').slice(0, 60000)")
        except Exception:
            txt = ""
        return {"url": page.url, "text": txt}
    if action == "focused":
        return await broker.focused(task_id)
    if action == "describe_at":
        return await broker.at(task_id, float(body.get("x", 0)), float(body.get("y", 0)))
    if action == "request_takeover":
        broker.requests[task_id] = {"task_id": task_id, "reason": str(body.get("reason", ""))[:300], "ts": time.time()}
        await broker.page_for(task_id)
        return {"ok": True, "status": "takeover_requested"}
    if action == "release":   # the task ended: its page stays for a while (to look at), then is recycled
        if task_id in broker.pages:
            broker.finished[task_id] = time.time()
        broker.requests.pop(task_id, None)
        return {"ok": True}
    if action == "search":
        return await web_search(str(body.get("query", ""))[:300], int(body.get("max_results") or 8))
    if action == "read":
        urls = body.get("urls") or ([body["url"]] if body.get("url") else [])
        if isinstance(urls, str):
            urls = [urls]
        return await web_read([str(u) for u in urls if str(u).strip()][:4])
    broker.check_agent(task_id)
    broker.requests.pop(task_id, None)   # the task is working again, so it is no longer waiting for the user
    if action in ("find", "look", "locate"):
        async with broker.task_lock(task_id):
            try:
                if action == "find":
                    return await broker.find(task_id, str(body.get("query", ""))[:200])
                if action == "locate":
                    region, mark = body.get("region"), body.get("mark")
                    if mark:
                        return await broker.grid(task_id, mark=mark)
                    if region:
                        return await broker.grid(task_id, region=region, cols=8, rows=6, labels="numbers")
                    return await broker.grid(task_id, cols=8, rows=6, labels="letters")
                return await broker.look(task_id)
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(500, f"浏览器错误 browser error: {str(e)[:300]}")
    async with broker.task_lock(task_id):
        page = await broker.page_for(task_id)
        try:
            if action == "navigate":
                url = str(body.get("url", "")).strip()
                if url and "://" not in url:
                    url = "https://" + url
                ok, why = check_url(url)
                if not ok:
                    raise HTTPException(403, why)
                await broker.pace(url)
                try:
                    resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    broker.nav_status[task_id] = resp.status if resp else 0
                except Exception as e:
                    if "ERR_BLOCKED_BY_CLIENT" in str(e):
                        raise HTTPException(403, "该地址被安全策略拦截 (blocked by egress policy)")
                    # a plain load timeout is often transient: wait a moment and try once more before giving up
                    if "imeout" in str(e):
                        try:
                            await asyncio.sleep(2.0)
                            resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                            broker.nav_status[task_id] = resp.status if resp else 0
                        except Exception as e2:
                            raise HTTPException(502, f"打开页面失败 navigation failed (retried once): {str(e2)[:180]}")
                    else:
                        raise HTTPException(502, f"打开页面失败 navigation failed: {str(e)[:200]}")
                await broker.settle(page, 1200)
            elif action == "snapshot":
                pass
            elif action == "click":
                loc = broker.locate(task_id, body.get("ref", ""))
                try:
                    await loc.click(timeout=8000)
                except Exception as e:
                    # 2026-10-04 chope.co "Book Now": the button was covered by another layer and every click timed out.
                    # Scroll it into view and try again; if something still covers it, click the element itself via script
                    # (it is the same element the agent chose, so the approval check already covered it).
                    first = str(e)
                    try:
                        await loc.scroll_into_view_if_needed(timeout=3000)
                        await loc.click(timeout=4000)
                    except Exception:
                        try:
                            await loc.evaluate("e => e.click()", timeout=4000)
                        except Exception as e2:
                            cover = " (另一个元素挡住了它 another element covers it)" if "intercepts pointer events" in first else ""
                            raise HTTPException(409, f"点击失败 click failed{cover}: {first[:160]} / {str(e2)[:80]}")
                await broker.settle(page, 1200)
                page = await broker.page_for(task_id)
            elif action == "click_at":
                # visual click (browser_locate found the point): works for iframes, shadow DOM, canvas, unlabeled icons
                x, y = float(body.get("x", -1)), float(body.get("y", -1))
                if not (0 <= x <= VIEWPORT["width"] * 2 and 0 <= y <= VIEWPORT["height"] * 2):
                    raise HTTPException(400, "x/y must be viewport coordinates from browser_locate")
                await page.mouse.click(x, y)
                await broker.settle(page, 900)
                text = str(body.get("text") or "")
                if text:
                    await page.keyboard.type(text, delay=15)
                    if body.get("submit"):
                        await page.keyboard.press("Enter")
                        await broker.settle(page, 1500)
                page = await broker.page_for(task_id)
            elif action == "type":
                loc = broker.locate(task_id, body.get("ref", ""))
                text = str(body.get("text", ""))
                try:
                    loc = await _editable_in(loc)
                    try:   # <input type=time/date/…> only accepts its ISO format: "12:00 PM" or "2026-10-03 12:00" fail
                        kind = await loc.evaluate("e => (e.tagName === 'INPUT' ? e.type : '')", timeout=3000)
                    except Exception:
                        kind = ""
                    text = normalize_date_input(kind, text)
                    if body.get("expiry"):
                        text = expiry_for_field(text, await _field_hint(loc))
                    if body.get("keys"):
                        # card fields (Adyen, Stripe…) format and validate on key events; fill() leaves them "incomplete"
                        await loc.click(timeout=5000)
                        await page.keyboard.press("Control+a")
                        await page.keyboard.press("Backspace")
                        await page.keyboard.type(text, delay=60)
                    else:
                        try:
                            await loc.fill(text, timeout=8000)
                        except Exception:
                            # clear first: typing into a field that still holds "Hartford" gives "HartfordTokyo"
                            await loc.click(timeout=5000)
                            await page.keyboard.press("Control+a")
                            await page.keyboard.press("Backspace")
                            await page.keyboard.type(text, delay=15)
                    if body.get("submit"):
                        await loc.press("Enter", timeout=5000)
                        await broker.settle(page, 1500)
                except Exception as e:
                    raise HTTPException(409, f"输入失败 type failed: {str(e)[:200]}")
            elif action == "select":
                loc = broker.locate(task_id, body.get("ref", ""))
                v = str(body.get("value", ""))
                try:
                    try:
                        await loc.select_option(label=v, timeout=5000)
                    except Exception:
                        await loc.select_option(value=v, timeout=5000)
                except Exception as e:
                    raise HTTPException(409, f"选择失败 select failed: {str(e)[:200]}")
                await broker.settle(page, 500)
            elif action == "press":
                key = str(body.get("key", "Enter"))
                if not re.fullmatch(r"[A-Za-z0-9+]{1,24}", key):
                    raise HTTPException(400, "invalid key")
                await page.keyboard.press(key)
                await broker.settle(page, 1000)
            elif action == "scroll":
                d = body.get("direction", "down")
                js = {"down": "window.scrollBy(0, window.innerHeight*0.85)", "up": "window.scrollBy(0, -window.innerHeight*0.85)",
                      "top": "window.scrollTo(0,0)", "bottom": "window.scrollTo(0, document.body.scrollHeight)"}.get(d)
                if not js:
                    raise HTTPException(400, "direction must be up/down/top/bottom")
                y0 = await page.evaluate("window.scrollY")
                await page.mouse.wheel(0, {"down": 700, "up": -700, "top": -100000, "bottom": 100000}[d])
                await asyncio.sleep(0.5)
                if await page.evaluate("window.scrollY") == y0:     # wheel went to an inner element (or nowhere)
                    await page.evaluate(js)
                    await asyncio.sleep(0.3)
            elif action == "back":
                await page.go_back(timeout=20000)
                await broker.settle(page, 800)
            elif action == "wait":
                secs = max(1, min(int(body.get("seconds", 5)), 120))
                await asyncio.sleep(secs)
            elif action == "save_media":
                saved = await broker.save_media(task_id, page, str(body.get("ref") or ""), str(body.get("url") or ""),
                                                str(body.get("name") or ""))
            elif action == "upload":
                rel = str(body.get("path", ""))
                full = os.path.realpath(os.path.join(WORKSPACE, rel.lstrip("/")))
                if not full.startswith(WORKSPACE + os.sep) or not os.path.isfile(full):
                    raise HTTPException(400, "文件必须位于工作区内 (file must exist inside the workspace)")
                if os.sep + ".quarantine" + os.sep in full:
                    raise HTTPException(403, "隔离区文件不能上传 (quarantined file)")
                loc = broker.locate(task_id, body.get("ref", ""))
                await loc.set_input_files(full, timeout=10000)
                await broker.settle(page, 500)
            else:
                raise HTTPException(404, f"unknown action {action}")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"浏览器错误 browser error: {str(e)[:300]}")
        if action == "save_media":
            return {"saved": saved, "url": page.url, "title": await page.title()}
        near = action == "scroll" or bool(body.get("near"))
        snap = await broker.snapshot(task_id, body.get("max_chars", 12000), near=near)
        if action in ("navigate", "click", "snapshot", "back", "wait", "press"):
            try:
                blk = await page.main_frame.evaluate(BLOCK_JS, broker.nav_status.get(task_id, 0) if action == "navigate" else 0)
            except Exception:
                blk = None
            if blk:
                snap["blocked"] = blk
                broker.note_block(snap.get("url") or page.url)
        return snap


@app.get("/agent/downloads", dependencies=[Depends(auth)])
async def downloads():
    return {"downloads": broker.downloads[-30:]}


# ================================================================== view + takeover API (user)
@app.get("/state", dependencies=[Depends(auth)])
async def state():
    p = broker.view_page()
    title = ""
    if p is not None:
        try:
            title = await p.title()
        except Exception:
            pass
    popup = p is not None and p in broker.parent
    return {"mode": broker.mode, "url": p.url if p is not None else "", "title": title, "view_task": broker.view_task,
            "popup": popup, "popup_opener_url": broker.parent[p].url if popup else "", "headless": broker.headless,
            "requested": broker.requested, "requests": broker.open_requests(), "takeover_task": broker.takeover_task,
            "tasks": [{"task_id": k, "url": v.url} for k, v in broker.pages.items() if not v.is_closed()],
            "viewport": VIEWPORT}


@app.get("/screenshot", dependencies=[Depends(auth)])
async def screenshot(task_id: str | None = None):
    p = broker.pages.get(task_id) if task_id else broker.view_page()
    if p is None or p.is_closed():
        p = broker.view_page()
    if p is None:
        return Response(status_code=204)
    try:
        img = await p.screenshot(type="jpeg", quality=60, timeout=8000)
    except Exception:
        return Response(status_code=204)
    return Response(img, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.post("/user/view", dependencies=[Depends(auth)])
async def user_view(req: Request):
    body = await req.json()
    tid = body.get("task_id")
    if tid in broker.pages:
        broker.view_task = tid
    # the user chose what to watch: keep it for 10 minutes ("pin": false hands the view back to the agents)
    broker.view_pinned_until = time.time() + 600 if body.get("pin", True) and tid in broker.pages else 0.0
    return await state()


@app.post("/user/takeover", dependencies=[Depends(auth)])
async def user_takeover(req: Request):
    body = await req.json()
    tid = body.get("task_id") or (broker.requested or {}).get("task_id") or broker.view_task or "default"
    if broker.mode == "user" and broker.takeover_task and broker.takeover_task != tid:
        # one takeover at a time: switching silently would resume the first task while the user is still in it
        raise HTTPException(409, f"你正在接管另一个任务（{broker.takeover_task}），请先交还它 (hand back the current task first)")
    # Pause the task first (its next action gets 423), then wait briefly for an action already in flight. A hung agent
    # action (a click waiting on a page that never settles) used to hold the lock for minutes, so "Take over" seemed to do
    # nothing and every key the user typed was refused with "take over first" (2026-10-05 decathlon.sg checkout).
    broker.mode = "user"
    broker.takeover_task = tid
    lock = broker.task_lock(tid)
    got = False
    try:
        await asyncio.wait_for(lock.acquire(), timeout=8)
        got = True
    except asyncio.TimeoutError:
        print(f"[browser] takeover of {tid}: an agent action is still running; taking over anyway", flush=True)
    try:
        await broker.page_for(tid)  # the page the user drives is always a registered task page
        broker.view_task = tid
    finally:
        if got:
            lock.release()
    return await state()


@app.post("/user/release", dependencies=[Depends(auth)])
async def user_release():
    # only the request this takeover answered is cleared; other tasks' requests stay open (they still need the user)
    tid = broker.takeover_task
    req = broker.requests.pop(tid, None)
    if req is None and tid in ("", "default") and broker.requests:
        req = broker.requests.pop(broker.requested["task_id"])   # untargeted takeover: it answered the latest request
    released = {"task_id": tid, "requested": req}
    broker.mode = "agent"
    broker.takeover_task = ""
    return {"ok": True, "released": released}


@app.post("/user/input", dependencies=[Depends(auth)])
async def user_input(req: Request):
    if broker.mode != "user":
        raise HTTPException(409, "请先点击「接管」(take over first)")
    body = await req.json()
    async with broker.input_lock:  # user events are applied strictly in arrival order
        return await _user_input(body)


async def _user_input(body: dict):
    # always the page being taken over — never whatever another (still running) task last touched
    page = broker.pages.get(broker.takeover_task or "default")
    if page is None or page.is_closed():
        page = await broker.page_for(broker.takeover_task or "default")
    kind = body.get("type")
    x, y = float(body.get("x", 0)), float(body.get("y", 0))
    if kind in ("click", "dblclick"):
        try:
            await (page.mouse.click(x, y) if kind == "click" else page.mouse.dblclick(x, y))
        except Exception as e:
            # the click itself closed the page (a sign-in popup's "Next" / "Allow" button): that is a successful click
            if not page.is_closed() and "closed" not in str(e).lower():
                raise HTTPException(409, f"点击失败 click failed: {str(e)[:150]}")
    elif kind == "wheel":
        await page.mouse.move(x, y)
        await page.mouse.wheel(float(body.get("dx", 0)), float(body.get("dy", 0)))
    elif kind == "text":
        await page.keyboard.type(str(body.get("text", ""))[:2000], delay=10)
    elif kind == "key":
        key = str(body.get("key", ""))
        if re.fullmatch(r"[A-Za-z0-9+]{1,30}", key):
            await page.keyboard.press(key)
    elif kind == "navigate":
        url = str(body.get("url", "")).strip()
        if url and "://" not in url:
            url = "https://" + url
        ok, why = check_url(url)
        if not ok:
            raise HTTPException(403, why)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            raise HTTPException(502, str(e)[:200])
    elif kind == "back":
        await page.go_back()
    elif kind == "reload":
        await page.reload()
    else:
        raise HTTPException(400, "unknown input type")
    if kind != "wheel":
        await asyncio.sleep(0.15)
    return {"ok": True}


@app.exception_handler(HTTPException)
async def http_exc(req, exc: HTTPException):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


async def _editable_in(loc):
    """The ref may point at a wrapper (a dialog, a combobox div, a label) rather than the text box itself: use the
    first visible input / textarea / contenteditable inside it, so fill() works and nothing is typed into the wrong box."""
    try:
        ok = await loc.evaluate("e => e.tagName === 'INPUT' || e.tagName === 'TEXTAREA' || e.isContentEditable"
                                " || e.getAttribute('role') === 'textbox' || e.getAttribute('role') === 'searchbox'",
                                timeout=3000)
        if ok:
            return loc
        inner = loc.locator("input:not([type=hidden]):visible, textarea:visible, [contenteditable=true]:visible").first
        if await inner.count():
            return inner
    except Exception:
        pass
    return loc


async def _field_hint(loc) -> str:
    try:
        return await loc.evaluate("e => [e.placeholder, e.getAttribute('aria-label'), e.maxLength > 0 ? 'maxlength' + e.maxLength : '']"
                                  ".filter(Boolean).join(' ')", timeout=3000)
    except Exception:
        return ""


def expiry_for_field(value: str, hint: str) -> str:
    """A card expiry from the vault ("12/2028", "12/28", "2028-12", "1228") in the form the box asks for: MM/YYYY when its
    placeholder says YYYY (or it holds 7 characters), otherwise MM/YY."""
    v = str(value or "").strip()
    m = re.fullmatch(r"(\d{4})\s*[-/.]\s*(\d{1,2})", v) or None
    if m:
        mm, yy = m.group(2), m.group(1)
    else:
        m = re.fullmatch(r"(\d{1,2})\s*[-/.\s]?\s*(\d{2}|\d{4})", v)
        if not m:
            return v
        mm, yy = m.group(1), m.group(2)
    mm = mm.zfill(2)
    yyyy = yy if len(yy) == 4 else "20" + yy
    h = (hint or "").lower()
    long = "yyyy" in h or "aaaa" in h or "jjjj" in h or re.search(r"maxlength(7|9)\b", h)
    return f"{mm}/{yyyy}" if long else f"{mm}/{yyyy[2:]}"


_DATE_KINDS = ("date", "time", "datetime-local", "month", "week")


def normalize_date_input(kind: str, text: str) -> str:
    """Rewrite free text into the value format a date/time <input> accepts (date YYYY-MM-DD, time HH:MM,
    datetime-local YYYY-MM-DDTHH:MM, month YYYY-MM). Other inputs, or text that can't be parsed, pass through."""
    if kind not in _DATE_KINDS:
        return text
    t = text.strip()
    d = re.search(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})", t)
    tm = re.search(r"(\d{1,2})[:：](\d{2})(?:[:：]\d{2})?\s*([AaPp]\.?[Mm]\.?|上午|下午|晚上)?", t)
    hhmm = ""
    if tm:
        h, m, ap = int(tm.group(1)), int(tm.group(2)), (tm.group(3) or "").lower().replace(".", "")
        if not ap:   # Chinese puts it first: 下午 3:05
            pre = re.search(r"(上午|下午|晚上)\s*$", t[:tm.start()])
            ap = pre.group(1) if pre else ""

        if ap in ("pm", "下午", "晚上") and h < 12:
            h += 12
        if ap in ("am", "上午") and h == 12:
            h = 0
        if 0 <= h < 24 and 0 <= m < 60:
            hhmm = f"{h:02d}:{m:02d}"
    ymd = f"{int(d.group(1)):04d}-{int(d.group(2)):02d}-{int(d.group(3)):02d}" if d else ""
    if kind == "time":
        return hhmm or text
    if kind == "date":
        return ymd or text
    if kind == "datetime-local":
        return f"{ymd}T{hhmm or '00:00'}" if ymd else text
    if kind == "month":
        mo = re.search(r"(\d{4})[-/.年](\d{1,2})", t)
        return f"{int(mo.group(1)):04d}-{int(mo.group(2)):02d}" if mo else text
    return text
