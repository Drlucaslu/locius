"""The web UI's static files (app/web), served from memory the way a CDN would — but from our own server only.

Why: the page shell must depend on nothing but this server (no CDN <link>/<script>: a slow or blocked third party
leaves the page blank, and a cloud VM may sit behind a filtered network). And it must be cheap on both ends:
- every asset URL in index.html is stamped `?v=<version>`, a digest of all files, so a stamped URL changes exactly
  when the content does and may be cached for a year (`public, max-age=31536000, immutable`) — no revalidation
  round trips on a repeat visit; an unstamped or stale URL stays `no-cache` + ETag → 304, so a shipped UI change
  always reaches existing users (browsers otherwise cache JS/CSS heuristically for days);
- text assets are gzip-compressed once (level 9: ~510 KB of JS/CSS → ~160 KB) and served compressed when the
  client accepts it, with `Vary: Accept-Encoding` and their own ETag — never compressed per request on a one-vCPU
  host, never a middleware on every API request.
The files are re-read when any of them changes on disk (a hot patch), so a running instance never serves stale bytes.
"""
from __future__ import annotations

import gzip
import hashlib
import mimetypes
import os
import re
import threading
from dataclasses import dataclass

from fastapi import Request, Response

COMPRESSIBLE = {".css", ".js", ".mjs", ".svg", ".json", ".html", ".txt", ".md", ".map"}
TEXT_TYPES = {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".html": "text/html",
              ".json": "application/json", ".svg": "image/svg+xml", ".txt": "text/plain", ".md": "text/markdown"}
IMMUTABLE = "public, max-age=31536000, immutable"
REVALIDATE = "no-cache"
STAMP_RE = re.compile(r'(?P<q>["\'])static/(?P<name>[A-Za-z0-9_.\-/]+)(?P=q)')


@dataclass(frozen=True)
class Asset:
    name: str
    body: bytes
    gz: bytes | None       # gzip variant for compressible types, else None
    media_type: str
    etag: str              # "<version>-<name>"; the gzip variant is etag + "-gz"


class Assets:
    """One directory of files, loaded into memory and re-loaded when a file's size or mtime changes."""

    def __init__(self, directory: str):
        self.dir = directory
        self._lock = threading.Lock()
        self._key: tuple | None = None
        self._version = ""
        self._files: dict[str, Asset] = {}

    def _snapshot(self) -> tuple:
        out = []
        for root, _dirs, names in os.walk(self.dir):
            for n in names:
                p = os.path.join(root, n)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                out.append((os.path.relpath(p, self.dir).replace(os.sep, "/"), st.st_mtime_ns, st.st_size))
        return tuple(sorted(out))

    def _load(self, key: tuple) -> None:
        h = hashlib.sha256()
        raw: dict[str, bytes] = {}
        for name, _m, _s in key:
            try:
                with open(os.path.join(self.dir, name), "rb") as fh:
                    raw[name] = fh.read()
            except OSError:
                continue
            h.update(name.encode()); h.update(b"\0"); h.update(raw[name])
        version = h.hexdigest()[:12]
        files = {}
        for name, body in raw.items():
            ext = os.path.splitext(name)[1].lower()
            mt = TEXT_TYPES.get(ext) or mimetypes.guess_type(name)[0] or "application/octet-stream"
            if mt.startswith("text/") or mt in ("application/json", "image/svg+xml"):
                mt += "; charset=utf-8"
            gz = gzip.compress(body, compresslevel=9, mtime=0) if ext in COMPRESSIBLE else None
            files[name] = Asset(name, body, gz, mt, f'"{version}-{name}"')
        self._key, self._version, self._files = key, version, files

    def _sync(self) -> None:
        key = self._snapshot()
        if key != self._key:
            with self._lock:
                if key != self._key:
                    self._load(key)

    def version(self) -> str:
        self._sync()
        return self._version

    def get(self, name: str) -> Asset | None:
        self._sync()
        return self._files.get(name)

    def stamp(self, html: str) -> str:
        """index.html: every `static/<file>` URL gets `?v=<version>`."""
        v = self.version()
        return STAMP_RE.sub(lambda m: f'{m.group("q")}static/{m.group("name")}?v={v}{m.group("q")}', html)

    def response(self, name: str, request: Request) -> Response:
        a = self.get(name)
        if a is None:
            return Response("no such static file", status_code=404, media_type="text/plain")
        stamped = request.query_params.get("v") == self._version
        gz = a.gz if a.gz and "gzip" in (request.headers.get("accept-encoding") or "").lower() else None
        etag = a.etag[:-1] + '-gz"' if gz else a.etag
        headers = {"Cache-Control": IMMUTABLE if stamped else REVALIDATE, "ETag": etag}
        if a.gz:
            headers["Vary"] = "Accept-Encoding"
        inm = request.headers.get("if-none-match") or ""
        # the client may hold either variant; both stand for the same bytes
        if a.etag in inm or a.etag[:-1] + '-gz"' in inm:
            return Response(status_code=304, headers=headers)
        if gz:
            headers["Content-Encoding"] = "gzip"
        body = b"" if request.method == "HEAD" else (gz or a.body)
        headers["Content-Length"] = str(len(gz or a.body))
        return Response(body, media_type=a.media_type, headers=headers)
