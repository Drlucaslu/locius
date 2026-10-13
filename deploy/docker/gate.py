"""Login gate for standalone (Docker / Fly) installs.

On Olares the entrance does the login, so Sentinel itself has none. Published straight from Docker it would be open to
anyone who finds the port, so this wraps Sentinel in a login. The password is OMUSE_PASSWORD until the user sets their
own in Settings (app/sentinel/passwd.py). It lives outside app/ on purpose: the Olares chart bundle stays unchanged.

Two ways in:
1. A signed session cookie, set by the login page (GET/POST /login). This is what browsers use. It is valid for
   SESSION_DAYS or until the password changes, and it survives server restarts (the signing key is kept in
   $SENTINEL_DATA/session.key) and the browser dropping the page from memory (iOS does that constantly; HTTP Basic
   credentials live only in that memory, which is why Basic auth kept asking on the phone).
2. HTTP Basic auth, sent preemptively by scripts (curl -u, httpx auth=...). The gate issues a Basic challenge only
   to clients that are not browsers (no Sec-Fetch-Mode header), so a browser never sees the native password dialog.

An unauthenticated browser navigation is redirected to /login?next=<url>; a browser fetch gets a 401 JSON answer and
the web app sends the user to /login. GET or POST /logout clears the cookie.

Not gated: /sentinel/api/health (container health check) and /internal/* (the runtime's calls; those carry their own
RUNTIME_TOKEN and Sentinel checks it). The phone port (VOICE_PORT) is a separate app that is public by design.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import html
import os
import secrets
import time
from typing import Callable
from urllib.parse import parse_qs, urlencode

OPEN_PATHS = ("/sentinel/api/health",)
OPEN_PREFIXES = ("/internal/",)
FAIL_DELAY_S = 1.0   # slows password guessing
COOKIE = "omuse_session"
SESSION_DAYS = 180
LOGIN_PATH, LOGOUT_PATH = "/login", "/logout"


def session_key_path() -> str:
    return os.path.join(os.environ.get("SENTINEL_DATA", "/sdata"), "session.key")


def load_session_key() -> bytes:
    """The cookie signing key: created once, kept with the other Sentinel state so sessions outlive restarts."""
    p = session_key_path()
    try:
        with open(p, "rb") as f:
            key = f.read().strip()
        if len(key) >= 32:
            return key
    except OSError:
        pass
    key = secrets.token_hex(32).encode()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "wb") as f:
        f.write(key)
    os.chmod(tmp, 0o600)
    os.replace(tmp, p)
    return key


def safe_next(v: str) -> str:
    """Only a path on this site (with query and fragment): never another host."""
    v = (v or "").strip()
    if not v.startswith("/") or v.startswith("//") or v.startswith("/\\") or "\n" in v or "\r" in v:
        return "/"
    return v


LOGIN_HTML = """<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OMuse</title>
<style>
:root{{--bg:#f4f1ea;--surface:#fffdf8;--line:#e3ddd2;--text:#1f1d1a;--muted:#6b665e;--accent:#0b7a5c;--accent-ink:#fff;--danger:#c62828;color-scheme:light}}
@media (prefers-color-scheme: dark){{:root{{--bg:#0e1114;--surface:#161a1f;--line:#2a3139;--text:#e6e8eb;--muted:#9aa3ad;--accent:#34c79a;--accent-ink:#06231a;--danger:#ff7b72;color-scheme:dark}}}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--bg);color:var(--text);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",system-ui,sans-serif;padding:16px}}
form{{width:100%;max-width:360px;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:24px;display:flex;flex-direction:column;gap:14px}}
h1{{font-size:20px;margin:0}}h1 span{{color:var(--muted);font-weight:400;font-size:14px}}
label{{display:flex;flex-direction:column;gap:4px;font-size:13px;color:var(--muted)}}
input{{font:inherit;color:inherit;background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:10px 12px}}
button{{font:inherit;font-weight:600;background:var(--accent);color:var(--accent-ink);border:0;border-radius:8px;padding:11px;cursor:pointer}}
.err{{color:var(--danger);font-size:13px;margin:0}}.hint{{color:var(--muted);font-size:12.5px;margin:0}}
</style></head><body>
<form method="post" action="/login" autocomplete="on">
<h1>OMuse <span>{title}</span></h1>
{error}
<label>{user_label}<input name="user" value="{user}" autocomplete="username" autocapitalize="none" spellcheck="false" required></label>
<label>{pw_label}<input name="password" type="password" autocomplete="current-password" required autofocus></label>
<input type="hidden" name="next" value="{next}">
<button type="submit">{button}</button>
<p class="hint">{hint}</p>
</form></body></html>"""

TEXT = {
    "zh": {"title": "登录 Sign in", "user_label": "登录名 User", "pw_label": "密码 Password", "button": "登录 Sign in",
           "wrong": "登录名或密码不对 (wrong user or password)", "hint": "登录后这个浏览器会保持登录状态；改密码后需要重新登录。"},
    "en": {"title": "Sign in", "user_label": "User", "pw_label": "Password", "button": "Sign in",
           "wrong": "Wrong user or password", "hint": "This browser stays signed in; changing the password signs every browser out."},
}


class BasicAuthGate:
    """verify(user, password) -> bool does the real check (slow: a password hash); version() changes when the password
    does (sessions and the Basic cache are dropped then). The last accepted Basic credentials are remembered by digest,
    so the hash runs once per sign-in, not per request."""

    def __init__(self, app, verify: Callable[[str, str], bool], version: Callable[[], int] = lambda: 0,
                 fail_delay: float = FAIL_DELAY_S, session_key: bytes | None = None, user: str = "omuse",
                 session_days: int = SESSION_DAYS):
        self.app = app
        self.verify = verify
        self.version = version
        self.fail_delay = fail_delay
        self.key = session_key or load_session_key()
        self.user = user
        self.max_age = int(session_days * 86400)
        self._ok: tuple[int, bytes] | None = None   # (password version, sha256 of the accepted "user:password")

    # ------------------------------------------------------------ session cookies
    def _sign(self, payload: str) -> str:
        return hmac.new(self.key, payload.encode(), hashlib.sha256).hexdigest()[:40]

    def issue_cookie(self) -> str:
        payload = f"{int(time.time())}.{self.version()}.{secrets.token_urlsafe(9)}"
        return f"{payload}.{self._sign(payload)}"

    def cookie_valid(self, value: str) -> bool:
        try:
            issued, ver, nonce, sig = value.split(".")
            payload = f"{issued}.{ver}.{nonce}"
            if not hmac.compare_digest(self._sign(payload), sig):
                return False
            return int(ver) == int(self.version()) and 0 <= time.time() - int(issued) <= self.max_age
        except (ValueError, AttributeError):
            return False

    @staticmethod
    def _cookies(scope) -> dict:
        out = {}
        raw = b"; ".join(v for k, v in (scope.get("headers") or []) if k == b"cookie")   # HTTP/2 clients may send several
        for part in raw.decode("latin-1").split(";"):
            k, _, v = part.strip().partition("=")
            if k:
                out[k] = v
        return out

    def _set_cookie(self, value: str, scope, clear: bool = False) -> tuple[bytes, bytes]:
        secure = "; Secure" if scope.get("scheme") in ("https", "wss") else ""
        age = 0 if clear else self.max_age
        return (b"set-cookie", f"{COOKIE}={value}; Path=/; Max-Age={age}; HttpOnly; SameSite=Lax{secure}".encode())

    # ------------------------------------------------------------ who may pass
    def _basic_ok(self, v: bytes) -> bool:
        scheme, _, cred = v.partition(b" ")
        if scheme.lower() != b"basic":
            return False
        try:
            given = base64.b64decode(cred.strip(), validate=True)
        except ValueError:
            return False
        digest = hashlib.sha256(given).digest()
        ver = self.version()
        if self._ok and self._ok[0] == ver and hmac.compare_digest(self._ok[1], digest):
            return True
        try:
            user, _, password = given.decode().partition(":")
        except UnicodeDecodeError:
            return False
        if self.verify(user, password):
            self._ok = (ver, digest)
            return True
        return False

    def _authorized(self, scope, headers: dict) -> bool:
        if b"authorization" in headers:
            return self._basic_ok(headers[b"authorization"])
        c = self._cookies(scope).get(COOKIE)
        return bool(c) and self.cookie_valid(c)

    # ------------------------------------------------------------ responses
    @staticmethod
    async def _respond(send, status: int, headers: list, body: bytes = b"") -> None:
        await send({"type": "http.response.start", "status": status, "headers": headers + [(b"cache-control", b"no-store")]})
        await send({"type": "http.response.body", "body": body})

    @staticmethod
    async def _body(receive) -> bytes:
        body = b""
        while True:
            m = await receive()
            body += m.get("body", b"")
            if not m.get("more_body"):
                return body[:65536]

    def _page(self, headers: dict, nxt: str, user: str = "", error: str = "") -> bytes:
        lang = "zh" if "zh" in headers.get(b"accept-language", b"").decode("latin-1").lower()[:40] else "en"
        t = TEXT[lang]
        err = f'<p class="err">{html.escape(error)}</p>' if error else ""
        return LOGIN_HTML.format(lang="zh-CN" if lang == "zh" else "en", title=t["title"], user_label=t["user_label"], pw_label=t["pw_label"],
                                 button=t["button"], hint=t["hint"], error=err, user=html.escape(user or self.user),
                                 next=html.escape(nxt)).encode()

    async def _login(self, scope, receive, send, headers: dict) -> None:
        q = parse_qs(scope.get("query_string", b"").decode("latin-1"))
        nxt = safe_next((q.get("next") or [""])[0])
        html_headers = [(b"content-type", b"text/html; charset=utf-8")]
        if scope["method"] == "GET":
            if self._authorized(scope, headers):
                return await self._respond(send, 303, [(b"location", nxt.encode())])
            return await self._respond(send, 200, html_headers, self._page(headers, nxt))
        if scope["method"] != "POST":
            return await self._respond(send, 405, [(b"allow", b"GET, POST")])
        form = parse_qs((await self._body(receive)).decode("utf-8", "replace"))
        user = (form.get("user") or [""])[0].strip()
        password = (form.get("password") or [""])[0]
        nxt = safe_next((form.get("next") or [nxt])[0])
        if not self.verify(user, password):
            if self.fail_delay:
                await asyncio.sleep(self.fail_delay)
            lang = "zh" if "zh" in headers.get(b"accept-language", b"").decode("latin-1").lower()[:40] else "en"
            return await self._respond(send, 401, html_headers, self._page(headers, nxt, user, TEXT[lang]["wrong"]))
        await self._respond(send, 303, [(b"location", nxt.encode()), self._set_cookie(self.issue_cookie(), scope)])

    async def _logout(self, scope, send) -> None:
        await self._respond(send, 303, [(b"location", LOGIN_PATH.encode()), self._set_cookie("", scope, clear=True)])

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)   # lifespan
        path = scope.get("path", "")
        headers = dict(scope.get("headers") or [])
        if scope["type"] == "http" and path == LOGIN_PATH:
            return await self._login(scope, receive, send, headers)
        if scope["type"] == "http" and path == LOGOUT_PATH:
            return await self._logout(scope, send)
        if path in OPEN_PATHS or path.startswith(OPEN_PREFIXES) or self._authorized(scope, headers):
            return await self.app(scope, receive, send)
        if b"authorization" in headers and self.fail_delay:
            await asyncio.sleep(self.fail_delay)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        mode = headers.get(b"sec-fetch-mode", b"").decode("latin-1").lower()
        if mode == "navigate" and scope["method"] in ("GET", "HEAD"):
            here = path + ("?" + scope["query_string"].decode("latin-1") if scope.get("query_string") else "")
            loc = LOGIN_PATH + ("?" + urlencode({"next": here}) if here != "/" else "")
            return await self._respond(send, 302, [(b"location", loc.encode())])
        if mode:   # a browser's fetch / XHR / EventSource: no Basic challenge, so no native password dialog
            return await self._respond(send, 401, [(b"content-type", b"application/json")], b'{"detail": "login required"}')
        await self._respond(send, 401, [(b"www-authenticate", b'Basic realm="OMuse", charset="UTF-8"'),
                                        (b"content-type", b"text/plain; charset=utf-8")], b"login required")


def create():
    """uvicorn --factory entry point."""
    from app.sentinel import passwd
    from app.sentinel.main import app
    if os.environ.get("OMUSE_AUTH", "").lower() == "off":
        print("[gate] OMUSE_AUTH=off: no login. Do not publish this port.", flush=True)
        return app
    if not os.environ.get("OMUSE_PASSWORD"):
        raise ValueError("OMUSE_PASSWORD required")
    if not passwd.is_default():
        print("[gate] using the password set in Settings (OMUSE_PASSWORD is only the initial one)", flush=True)
    return BasicAuthGate(app, passwd.verify, passwd.version, user=passwd.user())
