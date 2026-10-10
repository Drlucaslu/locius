"""The login password of a standalone (Docker) install.

The container starts with OMUSE_PASSWORD, the password the host chose. The user changes it in Settings; the new one
is stored hashed in $SENTINEL_DATA/auth.json and wins over the variable from then on. Until that file exists the
install still runs on the default password and the UI says so. On Olares there is no OMUSE_PASSWORD (the entrance
does the login) and none of this applies.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets

ITERATIONS = 200_000
MIN_LEN, MAX_LEN = 8, 128


class PasswordError(Exception):
    pass


def enabled() -> bool:
    return bool(os.environ.get("OMUSE_PASSWORD")) and os.environ.get("OMUSE_AUTH", "").lower() != "off"


def user() -> str:
    return os.environ.get("OMUSE_USER") or "omuse"


def path() -> str:
    return os.path.join(os.environ.get("SENTINEL_DATA", "/sdata"), "auth.json")


def is_default() -> bool:
    """True while the install still runs on OMUSE_PASSWORD (the user has not set their own)."""
    return not os.path.exists(path())


def version() -> int:
    """Changes whenever the stored password changes (the gate uses it to drop its cache)."""
    try:
        return os.stat(path()).st_mtime_ns
    except OSError:
        return 0


def _load() -> dict | None:
    try:
        with open(path(), encoding="utf-8") as f:
            rec = json.load(f)
        if rec.get("algo") == "pbkdf2_sha256" and rec.get("salt") and rec.get("hash"):
            return rec
    except (OSError, ValueError):
        pass
    return None


def verify(given_user: str, given_password: str) -> bool:
    """Constant-time check against the stored password, else against OMUSE_PASSWORD."""
    if not enabled() or not hmac.compare_digest(given_user.encode(), user().encode()):
        return False
    rec = _load()
    if rec:
        dk = hashlib.pbkdf2_hmac("sha256", given_password.encode(), bytes.fromhex(rec["salt"]), int(rec.get("iters") or ITERATIONS))
        return hmac.compare_digest(dk.hex(), str(rec["hash"]))
    return hmac.compare_digest(given_password.encode(), os.environ.get("OMUSE_PASSWORD", "").encode())


def set_password(new: str) -> None:
    """Store a new password (hashed, file readable by this user only). Raises PasswordError when it is too short."""
    if len(new) < MIN_LEN:
        raise PasswordError(f"密码至少 {MIN_LEN} 个字符 (at least {MIN_LEN} characters)")
    if len(new) > MAX_LEN:
        raise PasswordError(f"密码最多 {MAX_LEN} 个字符 (at most {MAX_LEN} characters)")
    salt = secrets.token_bytes(16)
    rec = {"algo": "pbkdf2_sha256", "iters": ITERATIONS, "salt": salt.hex(),
           "hash": hashlib.pbkdf2_hmac("sha256", new.encode(), salt, ITERATIONS).hex()}
    p = path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rec, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, p)
