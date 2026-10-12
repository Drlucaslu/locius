"""Small helpers shared by all OMuse services."""
from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

VERSION = "0.2.76"


def release_version(tag: str) -> str:
    """Version string shown in the app for a release tag: "locius-v0.3.1", "home-v0.3.1" or "v0.3.1" -> "0.3.1".
    Anything that is not a `<product>-v<version>` style tag is returned trimmed, so plain versions pass through."""
    t = (tag or "").strip()
    m = re.match(r"^(?:[A-Za-z0-9_.]+-)?v(\d.*)$", t)
    return m.group(1) if m else t


# Release images bake the git tag in at build time (OMUSE_VERSION build arg, see Dockerfile*); the literal above is
# the fallback for source checkouts and untagged builds.
VERSION = release_version(os.environ.get("OMUSE_VERSION", "")) or VERSION


def now_ts() -> float:
    return time.time()


def iso(ts: float | None = None) -> str:
    return datetime.fromtimestamp(ts if ts is not None else time.time(), tz=timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def loads(s: str | bytes | None, default: Any = None) -> Any:
    if s is None or s == "":
        return default
    try:
        return json.loads(s)
    except Exception:
        return default


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def token_ok(given: str | None, expected: str) -> bool:
    if not expected or not given:
        return False
    return hmac.compare_digest(given.encode(), expected.encode())


def random_token() -> str:
    return secrets.token_urlsafe(32)


class DB:
    """Tiny thread-safe sqlite wrapper (WAL mode, dict rows)."""

    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=30000")

    def script(self, sql: str) -> None:
        with self._lock:
            self.conn.executescript(sql)

    def execute(self, sql: str, params: tuple | list = ()) -> sqlite3.Cursor:
        with self._lock:
            return self.conn.execute(sql, params)

    def one(self, sql: str, params: tuple | list = ()) -> dict | None:
        with self._lock:
            row = self.conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def all(self, sql: str, params: tuple | list = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def insert(self, table: str, data: dict) -> int:
        cols = ",".join(data.keys())
        qs = ",".join("?" for _ in data)
        with self._lock:
            cur = self.conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({qs})", list(data.values()))
            return cur.lastrowid

    def update(self, table: str, key: str, key_val: Any, data: dict) -> None:
        sets = ",".join(f"{k}=?" for k in data)
        with self._lock:
            self.conn.execute(f"UPDATE {table} SET {sets} WHERE {key}=?", [*data.values(), key_val])


def truncate(text: str, limit: int) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n…[已截断 truncated, 共 {len(text)} 字符 chars]"
