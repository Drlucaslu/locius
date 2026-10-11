"""Skills: SKILL.md files the agent can load (name + description in the prompt, full text on load_skill).

Two places: the built-in ones shipped in app/skills (SKILLS_DIR) and the ones the user imported from GitHub, kept in
$RUNTIME_DATA/skills so they survive upgrades. Which ones the agent sees is Settings → Skills (skills_disabled); when
nothing was saved yet, OMUSE_SKILLS (comma-separated names) says which are on at startup, and without it every skill
is on. A skill that is off is not listed in the prompt and load_skill refuses it.
"""
from __future__ import annotations

import os
import re
from urllib.parse import urlparse

import httpx

BUILTIN_DIR = os.environ.get("SKILLS_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills"))
USER_DIR = os.path.join(os.environ.get("RUNTIME_DATA", "/data"), "skills")
GITHUB_RAW = os.environ.get("GITHUB_RAW_URL", "https://raw.githubusercontent.com").rstrip("/")
MAX_BYTES = 256 * 1024
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class SkillError(Exception):
    pass


def front_matter(text: str) -> dict:
    """name / description from the YAML front matter (--- ... ---) at the top of a SKILL.md; {} when there is none."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*(\n|$)", text or "", re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        if _ and k.strip() in ("name", "description"):
            out[k.strip()] = v.strip().strip("\"'")
    return out


def _scan(folder: str, source: str) -> list[dict]:
    out = []
    if not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder)):
        p = os.path.join(folder, name, "SKILL.md")
        if os.path.isfile(p):
            try:
                txt = open(p, encoding="utf-8").read()
            except OSError:
                continue
            fm = front_matter(txt)
            out.append({"name": name, "description": fm.get("description", ""), "path": p, "source": source})
    return out


def all_skills() -> list[dict]:
    """Built-in skills, then imported ones; an imported skill with a built-in's name is not possible (import refuses)."""
    seen = set()
    out = []
    for s in _scan(BUILTIN_DIR, "builtin") + _scan(USER_DIR, "imported"):
        if s["name"] not in seen:
            seen.add(s["name"])
            out.append(s)
    return out


def env_disabled(names: list[str]) -> list[str]:
    """What OMUSE_SKILLS leaves off: every skill not named in it; nothing when the variable is unset or empty."""
    raw = (os.environ.get("OMUSE_SKILLS") or "").strip()
    if not raw:
        return []
    on = {x.strip() for x in raw.split(",") if x.strip()}
    return [n for n in names if n not in on]


def disabled_names(settings: dict) -> list[str]:
    """The saved selection (Settings → Skills); until one is saved, OMUSE_SKILLS decides."""
    saved = settings.get("skills_disabled")
    if isinstance(saved, list):
        return [str(x) for x in saved]
    return env_disabled([s["name"] for s in all_skills()])


def listing(settings: dict) -> list[dict]:
    off = set(disabled_names(settings))
    return [{**s, "enabled": s["name"] not in off} for s in all_skills()]


def enabled(settings: dict) -> list[dict]:
    return [s for s in listing(settings) if s["enabled"]]


def raw_url(link: str) -> str:
    """The raw SKILL.md address for a GitHub link: a repo (SKILL.md at its root, default branch), a folder
    (…/tree/<branch>/<path>), a file (…/blob/<branch>/<path>/SKILL.md) or a raw.githubusercontent.com address."""
    link = (link or "").strip()
    u = urlparse(link)
    if u.scheme not in ("http", "https"):
        raise SkillError("请输入 GitHub 链接 (enter a GitHub link)")
    host = (u.hostname or "").lower()
    parts = [p for p in u.path.split("/") if p]
    if host == "raw.githubusercontent.com":
        return GITHUB_RAW + u.path if GITHUB_RAW != "https://raw.githubusercontent.com" else link
    if host not in ("github.com", "www.github.com") or len(parts) < 2:
        raise SkillError("只支持 github.com 上的仓库或目录链接 (only github.com repository / folder links are supported)")
    owner, repo = parts[0], parts[1].removesuffix(".git")
    if len(parts) >= 4 and parts[2] in ("tree", "blob"):
        branch, rest = parts[3], parts[4:]
        if rest and rest[-1].upper() == "SKILL.MD":
            rest = rest[:-1]
        return f"{GITHUB_RAW}/{owner}/{repo}/{branch}/{'/'.join(rest + ['SKILL.md'])}"
    return f"{GITHUB_RAW}/{owner}/{repo}/HEAD/SKILL.md"


async def import_from_github(link: str) -> dict:
    """Fetch the SKILL.md a GitHub link points at and save it under the user's skills; returns the listing entry."""
    url = raw_url(link)
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
            r = await c.get(url, headers={"Accept": "text/plain"})
    except httpx.HTTPError as e:
        raise SkillError(f"下载失败 download failed: {type(e).__name__}")
    if r.status_code == 404:
        raise SkillError("这个链接下没有 SKILL.md (no SKILL.md at that link: give the repository or the skill's folder)")
    if r.status_code >= 400:
        raise SkillError(f"下载失败 download failed: HTTP {r.status_code}")
    if len(r.content) > MAX_BYTES:
        raise SkillError("SKILL.md 太大 (file too large)")
    text = r.content.decode("utf-8", errors="replace")
    fm = front_matter(text)
    name = (fm.get("name") or "").strip().lower()
    if not name or not fm.get("description"):
        raise SkillError("SKILL.md 需要 name 和 description 两个字段 (the front matter needs name and description)")
    if not NAME_RE.match(name):
        raise SkillError("技能名只能用小写字母、数字、. _ - (name: lowercase letters, digits, . _ -)")
    if any(s["name"] == name and s["source"] == "builtin" for s in all_skills()):
        raise SkillError(f"已有内置技能叫 {name} (a built-in skill has that name)")
    folder = os.path.join(USER_DIR, name)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(text)
    with open(os.path.join(folder, "SOURCE"), "w", encoding="utf-8") as f:
        f.write(link.strip() + "\n")
    return {"name": name, "description": fm["description"], "source": "imported", "url": link.strip()}


def delete_imported(name: str) -> bool:
    import shutil
    folder = os.path.join(USER_DIR, name)
    if not NAME_RE.match(name or "") or not os.path.isfile(os.path.join(folder, "SKILL.md")):
        return False
    shutil.rmtree(folder, ignore_errors=True)
    return True


def source_link(name: str) -> str:
    try:
        return open(os.path.join(USER_DIR, name, "SOURCE"), encoding="utf-8").read().strip()
    except OSError:
        return ""
