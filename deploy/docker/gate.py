"""Password gate for standalone (Docker) installs.

On Olares the entrance does the login, so Sentinel itself has none. Published straight from Docker it would be open to
anyone who finds the port, so this wraps Sentinel in HTTP Basic auth. The password is OMUSE_PASSWORD until the user
sets their own in Settings (app/sentinel/passwd.py). It lives outside app/ on purpose: the Olares chart bundle stays
unchanged.

Not gated: /sentinel/api/health (container health check) and /internal/* (the runtime's calls; those carry their own
RUNTIME_TOKEN and Sentinel checks it). The phone port (VOICE_PORT) is a separate app that is public by design.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import os
from typing import Callable

OPEN_PATHS = ("/sentinel/api/health",)
OPEN_PREFIXES = ("/internal/",)
FAIL_DELAY_S = 1.0   # slows password guessing


class BasicAuthGate:
    """verify(user, password) -> bool does the real check (slow: a password hash); version() changes when the password
    does. The last accepted credentials are remembered by digest, so the hash runs once per sign-in, not per request."""

    def __init__(self, app, verify: Callable[[str, str], bool], version: Callable[[], int] = lambda: 0,
                 fail_delay: float = FAIL_DELAY_S):
        self.app = app
        self.verify = verify
        self.version = version
        self.fail_delay = fail_delay
        self._ok: tuple[int, bytes] | None = None   # (password version, sha256 of the accepted "user:password")

    def _authorized(self, scope) -> bool:
        for k, v in scope.get("headers") or []:
            if k == b"authorization":
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
        return False

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)   # lifespan
        path = scope.get("path", "")
        if path in OPEN_PATHS or path.startswith(OPEN_PREFIXES) or self._authorized(scope):
            return await self.app(scope, receive, send)
        has_cred = any(k == b"authorization" for k, _ in scope.get("headers") or [])
        if has_cred and self.fail_delay:
            await asyncio.sleep(self.fail_delay)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        await send({"type": "http.response.start", "status": 401,
                    "headers": [(b"www-authenticate", b'Basic realm="OMuse", charset="UTF-8"'),
                                (b"content-type", b"text/plain; charset=utf-8"), (b"cache-control", b"no-store")]})
        await send({"type": "http.response.body", "body": b"login required"})


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
    return BasicAuthGate(app, passwd.verify, passwd.version)
