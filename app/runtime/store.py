"""Runtime persistent state: conversations, tasks, events, schedules, memory, settings."""
from __future__ import annotations

import os
import re

from app.common.util import DB, dumps, loads, new_id, now_ts

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, title TEXT, kind TEXT DEFAULT 'chat', created_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT, conv_id TEXT, role TEXT, content TEXT, task_id TEXT, created_at REAL
);
CREATE INDEX IF NOT EXISTS ix_msg_conv ON messages(conv_id);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, conv_id TEXT, goal TEXT, status TEXT, plan TEXT, transcript TEXT, pending TEXT,
  result TEXT, error TEXT, source TEXT, schedule_id TEXT, parent_id TEXT, steps INTEGER DEFAULT 0,
  waiting TEXT, created_at REAL, updated_at REAL, finished_at REAL
);
CREATE INDEX IF NOT EXISTS ix_task_status ON tasks(status);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, ts REAL, type TEXT, data TEXT
);
CREATE INDEX IF NOT EXISTS ix_ev_task ON events(task_id);
CREATE TABLE IF NOT EXISTS schedules (
  id TEXT PRIMARY KEY, name TEXT, goal TEXT, kind TEXT, spec TEXT, tz TEXT, enabled INTEGER,
  last_run REAL, next_run REAL, state TEXT, conv_id TEXT, created_at REAL, last_task TEXT
);
CREATE TABLE IF NOT EXISTS facts (
  id TEXT PRIMARY KEY, fact TEXT, category TEXT, entity TEXT, source TEXT, confidence REAL,
  created_at REAL, last_verified REAL, ttl_days INTEGER
);
CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(id UNINDEXED, fact, entity, tokenize='trigram');
CREATE TABLE IF NOT EXISTS subjects (
  id TEXT PRIMARY KEY, slug TEXT UNIQUE, title TEXT, brief TEXT, status TEXT, conv_id TEXT, created_at REAL, updated_at REAL,
  last_task TEXT, runs INTEGER DEFAULT 0, chars INTEGER DEFAULT 0, error TEXT DEFAULT ''
);
CREATE VIRTUAL TABLE IF NOT EXISTS library_fts USING fts5(subject_id UNINDEXED, heading, text, tokenize='trigram');
CREATE TABLE IF NOT EXISTS episodes (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, task_id TEXT, summary TEXT);
CREATE TABLE IF NOT EXISTS entities (id TEXT PRIMARY KEY, type TEXT, name TEXT, attrs TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS relations (src TEXT, rel TEXT, dst TEXT, source TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS goals (
  id TEXT PRIMARY KEY, title TEXT, objective TEXT, criteria TEXT, status TEXT, deadline REAL, schedule_id TEXT,
  conv_id TEXT, progress TEXT, result TEXT, created_at REAL, updated_at REAL, finished_at REAL
);
CREATE TABLE IF NOT EXISTS profile (key TEXT PRIMARY KEY, value TEXT, updated_at REAL, source TEXT);
CREATE TABLE IF NOT EXISTS profile_pending (
  id TEXT PRIMARY KEY, key TEXT, value TEXT, old TEXT, reason TEXT, source TEXT, status TEXT, created_at REAL, resolved_at REAL
);
CREATE TABLE IF NOT EXISTS memory_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, kind TEXT, report TEXT);
CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, title TEXT, body TEXT, task_id TEXT, level TEXT, read INTEGER DEFAULT 0
);
"""

DEFAULT_SETTINGS = {
    "model_base_url": os.environ.get("OMUSE_MODEL_URL") or os.environ.get("PERSONA_MODEL_URL", ""),
    "model_name": os.environ.get("OMUSE_MODEL") or os.environ.get("PERSONA_MODEL", "Olares/unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL"),
    "planner_model": os.environ.get("OMUSE_PLANNER_MODEL", "").strip(),
    "vision_model": os.environ.get("OMUSE_VISION_MODEL", "").strip(),       # "" = the executor model (Qwen3.x on Olares can read images)
    "stt_model": os.environ.get("OMUSE_STT_MODEL", "").strip(),          # speech-to-text for audio/video attachments; "" = a whisper-like model on the endpoint, if any
    "image_base_url": os.environ.get("OMUSE_IMAGE_URL", ""),   # OpenAI-Images-compatible endpoint for make_image; "" = the model endpoint
    "image_model": os.environ.get("OMUSE_IMAGE_MODEL", ""),    # image model id (gpt-image-1 / dall-e-3 / FLUX …); "" = auto-pick
    "temperature": 0.3,
    "max_steps": 40,
    "llm_concurrency": 2,   # model requests in flight at once (match the model server's parallel slots, llama.cpp -np)
    "max_minutes": 20,      # time budget per run: told to wrap up at 70%, answers with what it has at 100%
    "max_tokens": 4096,
    "timezone": os.environ.get("TZ", "Asia/Singapore"),
    "user_name": "",
    "language": "",          # the agent's language (zh / en); "" = not chosen yet: filled from the browser on first visit
    "ui_language": "",       # the web UI's language: "" = follow the browser (en / zh / tw), or one of those
    "theme": "auto",         # web UI theme: auto (follow the system) / ink (dark) / paper (off-white)
    "reply_language": "",    # "" = answer in Settings → Language; "match" = answer in the language of each request
    "memory_extraction": True,
    "memory_consolidation": True,     # tidy memory once a day (merge, promote, expire) and send a short report
    "memory_consolidate_at": "03:30",  # local time (Settings → Timezone)
    "disable_thinking": False,
    "extra_body": "",
    "llm_timeout": 600,
}


PROFILE_FIELDS = [   # key, 中文, English
    ("name_zh", "中文姓名", "Chinese name"),
    ("name_en", "英文姓名（证件拼写）", "Name as on passport"),
    ("preferred_name", "称呼", "Preferred name"),
    ("phone", "手机", "Mobile phone"),
    ("email_personal", "私人邮箱", "Personal email"),
    ("email_work", "工作邮箱", "Work email"),
    ("address_home", "家庭地址", "Home address"),
    ("address_work", "公司地址", "Work address"),
    ("company", "公司", "Company"),
    ("job_title", "职位", "Job title"),
    ("birthday", "生日", "Date of birth"),
    ("nationality", "国籍", "Nationality"),
]
PROFILE_KEYS = {k for k, _, _ in PROFILE_FIELDS}


def profile_key(key: str) -> str:
    """A fixed field, or a custom one written as 'custom:<label>'."""
    key = (key or "").strip()
    if key in PROFILE_KEYS:
        return key
    if key.startswith("custom:") and 1 < len(key) <= 60:
        return "custom:" + re.sub(r"\s+", " ", key[7:]).strip()[:50]
    return ""


def norm_fact(s: str) -> str:
    return re.sub(r"\W+", "", (s or "").lower())


_SENSITIVE = re.compile(r"(?<![+\d])(?:\d[ -]?){12,19}|\b[A-Z]{1,2}\d{6,9}\b|\b[STFGM]\d{7}[A-Z]\b|(?i:password|密码|cvv|cvc)")


_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def profile_value_ok(key: str, value: str) -> bool:
    """Basic shape checks so a suggestion like email_work = 'bytetrade' never reaches the user."""
    v = (value or "").strip()
    if not v:
        return False
    if key.startswith("email"):
        return bool(_EMAIL.match(v))
    if key == "phone":
        digits = re.sub(r"\D", "", v)
        return 6 <= len(digits) <= 15 and bool(re.fullmatch(r"[+\d\s().-]+", v))
    return True


def looks_sensitive(text: str) -> bool:
    """Card / ID / passport-looking numbers and passwords never go into memory — they belong in the vault."""
    return bool(_SENSITIVE.search(text or ""))


def mentions_fact(fact: str, text: str) -> bool:
    """Whether `text` restates `fact`: its numbers plus at least two of its words (CJK bigrams or latin words)."""
    import re as _re
    nums = set(_re.findall(r"\d[\d,.]*\d|\d{2,}", fact))
    toks = set()
    for run in _re.findall(r"[\u4e00-\u9fff]+", fact):
        toks |= {run[i:i + 2] for i in range(len(run) - 1)}
    toks |= {w.lower() for w in _re.findall(r"[A-Za-z]{4,}", fact)}
    low = text.lower()
    hits = sum(1 for t in toks if t in low)
    if nums:
        return any(n in text for n in nums) and hits >= 2
    return bool(toks) and hits >= max(3, len(toks) // 2)


class RStore:
    def __init__(self, data_dir: str):
        self.db = DB(os.path.join(data_dir, "runtime.db"))
        try:
            self.db.script(SCHEMA)
        except Exception:
            # sqlite without trigram tokenizer: fall back to unicode61
            self.db.script(SCHEMA.replace("tokenize='trigram'", "tokenize='unicode61'"))
        cols = {r["name"] for r in self.db.all("PRAGMA table_info(schedules)")}
        if "goal_id" not in cols:
            self.db.execute("ALTER TABLE schedules ADD COLUMN goal_id TEXT DEFAULT ''")
        mcols = {r["name"] for r in self.db.all("PRAGMA table_info(messages)")}
        if "meta" not in mcols:
            self.db.execute("ALTER TABLE messages ADD COLUMN meta TEXT DEFAULT ''")   # e.g. the user's attachments
        tcols = {r["name"] for r in self.db.all("PRAGMA table_info(tasks)")}
        if "attachments" not in tcols:
            self.db.execute("ALTER TABLE tasks ADD COLUMN attachments TEXT DEFAULT ''")
        if "outcome" not in tcols:   # proof that a consequential task really finished (app/runtime/outcome.py)
            self.db.execute("ALTER TABLE tasks ADD COLUMN outcome TEXT DEFAULT ''")
        fcols = {r["name"] for r in self.db.all("PRAGMA table_info(facts)")}
        for col, ddl in (("tier", "TEXT DEFAULT 'long'"), ("uses", "INTEGER DEFAULT 0"), ("last_used", "REAL"),
                         ("expires_at", "REAL"), ("history", "TEXT DEFAULT ''"), ("domain", "TEXT DEFAULT ''"),
                         ("status", "TEXT DEFAULT 'active'")):
            if col not in fcols:
                self.db.execute(f"ALTER TABLE facts ADD COLUMN {col} {ddl}")
        self._sort_domains()

    # ------------------------------------------------------------ settings
    def settings(self) -> dict:
        s = dict(DEFAULT_SETTINGS)
        for r in self.db.all("SELECT key, value FROM settings"):
            s[r["key"]] = loads(r["value"], r["value"])
        return s

    def set_settings(self, d: dict) -> dict:
        for k, v in d.items():
            if k in DEFAULT_SETTINGS:
                self.db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?,?)", (k, dumps(v)))
        return self.settings()

    # ------------------------------------------------------------ conversations
    def create_conv(self, title: str, kind: str = "chat", cid: str | None = None) -> str:
        cid = cid or new_id("conv")
        self.db.execute("INSERT OR IGNORE INTO conversations(id, title, kind, created_at, updated_at) VALUES (?,?,?,?,?)",
                        (cid, title[:80], kind, now_ts(), now_ts()))
        return cid

    def convs(self, limit=100) -> list[dict]:
        return self.db.all("SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?", (limit,))

    def conv(self, cid: str) -> dict | None:
        return self.db.one("SELECT * FROM conversations WHERE id=?", (cid,))

    # ------------------------------------------------------------ research library (app/runtime/library.py)
    def subjects(self) -> list[dict]:
        return self.db.all("SELECT * FROM subjects ORDER BY updated_at DESC")

    def subject(self, sid: str) -> dict | None:
        return self.db.one("SELECT * FROM subjects WHERE id=?", (sid,))

    def subject_by_conv(self, cid: str) -> dict | None:
        return self.db.one("SELECT * FROM subjects WHERE conv_id=?", (cid,)) if cid else None

    def create_subject(self, rec: dict) -> dict:
        base, n = rec["slug"], 2
        while self.db.one("SELECT id FROM subjects WHERE slug=?", (rec["slug"],)):
            rec["slug"] = f"{base}-{n}"; n += 1
        self.db.insert("subjects", rec)
        return self.subject(rec["id"])

    def update_subject(self, sid: str, **kw) -> None:
        data = {k: v for k, v in kw.items() if k in ("title", "brief", "status", "conv_id", "last_task", "runs", "chars", "error")}
        data["updated_at"] = now_ts()
        self.db.update("subjects", "id", sid, data)

    def delete_subject(self, sid: str) -> None:
        self.db.execute("DELETE FROM library_fts WHERE subject_id=?", (sid,))
        self.db.execute("DELETE FROM subjects WHERE id=?", (sid,))

    def library_replace(self, sid: str, pieces: list[tuple[str, str]]) -> None:
        self.db.execute("DELETE FROM library_fts WHERE subject_id=?", (sid,))
        for heading, text in pieces:
            self.db.execute("INSERT INTO library_fts(subject_id, heading, text) VALUES (?,?,?)", (sid, heading, text))

    def library_search(self, query: str, limit: int = 6) -> list[dict]:
        """Report passages matching the query: FTS (trigram) first, a plain LIKE fallback; each hit names its subject."""
        terms = [t for t in re.split(r"[\s,，。.!?？！;；:：]+", query or "") if len(t) >= 2][:12]
        if not terms:
            return []
        subs = {x["id"]: x for x in self.subjects()}
        q = " OR ".join('"' + t.replace('"', "") + '"' for t in terms)
        try:
            rows = self.db.all("SELECT subject_id, heading, text, bm25(library_fts) AS rank FROM library_fts WHERE library_fts MATCH ? "
                               "ORDER BY rank LIMIT ?", (q, limit))
        except Exception:
            rows = []
        if not rows:
            like = [f"%{t}%" for t in terms]
            cond = " OR ".join("text LIKE ?" for _ in like)
            rows = self.db.all(f"SELECT subject_id, heading, text FROM library_fts WHERE {cond} LIMIT ?", (*like, limit))
        out = []
        for r in rows:
            sub = subs.get(r["subject_id"])
            if sub:
                out.append({"subject_id": sub["id"], "slug": sub["slug"], "title": sub["title"], "heading": r["heading"] or "",
                            "text": r["text"]})
        return out

    def set_conv_title(self, cid: str, title: str) -> None:
        self.db.execute("UPDATE conversations SET title=? WHERE id=?", (title[:80], cid))

    def add_msg(self, cid: str, role: str, content: str, task_id: str = "", meta: dict | None = None) -> int:
        mid = self.db.insert("messages", {"conv_id": cid, "role": role, "content": content, "task_id": task_id,
                                          "created_at": now_ts(), "meta": dumps(meta) if meta else ""})
        self.db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now_ts(), cid))
        return mid

    def msgs(self, cid: str, limit=200) -> list[dict]:
        rows = self.db.all("SELECT * FROM messages WHERE conv_id=? ORDER BY id DESC LIMIT ?", (cid, limit))
        for r in rows:
            r["meta"] = loads(r.get("meta") or "", None)
        return list(reversed(rows))

    def conv_attachments(self, cid: str) -> list[dict]:
        """Every file the user attached in this conversation (oldest first)."""
        out = []
        for m in self.msgs(cid, 400):
            for a in ((m.get("meta") or {}).get("attachments") or []) if isinstance(m.get("meta"), dict) else []:
                out.append(a)
        return out

    def delete_conv(self, cid: str):
        self.db.execute("DELETE FROM messages WHERE conv_id=?", (cid,))
        self.db.execute("DELETE FROM conversations WHERE id=?", (cid,))

    # ------------------------------------------------------------ tasks
    def create_task(self, goal: str, conv_id: str, source: str = "chat", schedule_id: str = "", parent_id: str = "",
                    attachments: list | None = None) -> dict:
        tid = new_id("task")
        self.db.insert("tasks", {"attachments": dumps(attachments) if attachments else "",
            "id": tid, "conv_id": conv_id, "goal": goal, "status": "CREATED", "plan": dumps({}), "transcript": dumps([]),
            "pending": dumps(None), "result": "", "error": "", "source": source, "schedule_id": schedule_id,
            "parent_id": parent_id, "steps": 0, "waiting": dumps(None), "created_at": now_ts(), "updated_at": now_ts(),
            "finished_at": None,
        })
        return self.task(tid)

    def task(self, tid: str) -> dict | None:
        r = self.db.one("SELECT * FROM tasks WHERE id=?", (tid,))
        if not r:
            return None
        for k, d in (("plan", {}), ("transcript", []), ("pending", None), ("waiting", None)):
            r[k] = loads(r[k], d)
        r["attachments"] = loads(r.get("attachments") or "", []) or []
        r["outcome"] = loads(r.get("outcome") or "", None)
        return r

    def update_task(self, tid: str, **kw):
        data = {}
        for k, v in kw.items():
            data[k] = dumps(v) if k in ("plan", "transcript", "pending", "waiting", "outcome") else v
        data["updated_at"] = now_ts()
        self.db.update("tasks", "id", tid, data)

    def tasks(self, status: str | None = None, limit=100, conv_id: str | None = None) -> list[dict]:
        q = "SELECT id, conv_id, goal, status, plan, result, error, source, schedule_id, parent_id, steps, waiting, created_at, updated_at, finished_at, outcome FROM tasks WHERE parent_id=''"
        p: list = []
        if status:
            q += " AND status IN (%s)" % ",".join("?" for _ in status.split(","))
            p += status.split(",")
        if conv_id:
            q += " AND conv_id=?"
            p.append(conv_id)
        q += " ORDER BY created_at DESC LIMIT ?"
        p.append(limit)
        rows = self.db.all(q, p)
        for r in rows:
            r["plan"] = loads(r["plan"], {})
            r["waiting"] = loads(r["waiting"], None)
            r["outcome"] = loads(r.get("outcome") or "", None)
        return rows

    # ------------------------------------------------------------ events
    def add_event(self, task_id: str, type_: str, data: dict) -> dict:
        ts = now_ts()
        eid = self.db.insert("events", {"task_id": task_id, "ts": ts, "type": type_, "data": dumps(data)})
        return {"id": eid, "task_id": task_id, "ts": ts, "type": type_, "data": data}

    def events(self, task_id: str, after: int = 0) -> list[dict]:
        rows = self.db.all("SELECT * FROM events WHERE task_id=? AND id>? ORDER BY id", (task_id, after))
        for r in rows:
            r["data"] = loads(r["data"], {})
        return rows

    # ------------------------------------------------------------ memory
    # Three layers: the profile (fixed fields for forms and emails; changes need the user's OK), long-term facts
    # (preferences, people, companies, projects, habits) and recent facts/episodes (one-off details, kept 30 days).
    RECENT_DAYS = 30

    def add_fact(self, fact: str, category: str = "general", entity: str = "", source: str = "user",
                 confidence: float = 0.9, ttl_days: int | None = None, tier: str = "long",
                 domain: str = "", status: str = "active") -> dict | None:
        from app.runtime.context import DOMAIN_KEYS, domain_of
        fact = fact.strip()
        if not fact:
            return None
        tier = "recent" if tier == "recent" else "long"
        norm = norm_fact(fact)
        for r in self.db.all("SELECT id, fact, tier FROM facts"):
            if norm_fact(r["fact"]) == norm:
                upd = {"last_verified": now_ts()}
                if status == "active":           # the user said it again: no longer just something OMuse learned
                    upd["status"] = "active"
                if tier == "long" and r["tier"] == "recent":     # said again / asked to remember: keep it for good
                    upd.update(tier="long", expires_at=None)
                self.db.update("facts", "id", r["id"], upd)
                return {"id": r["id"], "fact": r["fact"], "duplicate": True}
        fid = new_id("fact")
        exp = now_ts() + self.RECENT_DAYS * 86400 if tier == "recent" else None
        domain = domain if domain in DOMAIN_KEYS else domain_of(fact, category, entity)
        status = "pending" if status == "pending" else "active"
        self.db.insert("facts", {"id": fid, "fact": fact, "category": category, "entity": entity, "source": source,
                                 "confidence": confidence, "created_at": now_ts(), "last_verified": now_ts(),
                                 "ttl_days": ttl_days, "tier": tier, "uses": 0, "expires_at": exp, "history": "",
                                 "domain": domain, "status": status})
        self.db.execute("INSERT INTO facts_fts(id, fact, entity) VALUES (?,?,?)", (fid, fact, entity))
        self.sync_entity(domain, entity)
        return {"id": fid, "fact": fact, "tier": tier, "domain": domain, "status": status}

    def fact(self, fid: str) -> dict | None:
        return self.db.one("SELECT * FROM facts WHERE id=?", (fid,))

    def update_fact(self, fid: str, **kw) -> dict | None:
        r = self.fact(fid)
        if not r:
            return None
        from app.runtime.context import DOMAIN_KEYS, domain_of
        data = {k: v for k, v in kw.items() if k in ("fact", "category", "entity", "tier", "uses", "last_used", "expires_at",
                                                    "history", "last_verified", "confidence", "domain", "status")}
        if data.get("domain") not in (None, *DOMAIN_KEYS):
            data.pop("domain")
        if data.get("status") not in (None, "active", "pending"):
            data.pop("status")
        if "domain" not in data and any(k in data for k in ("fact", "category", "entity")):
            # re-sort only if the domain was the automatic one (a domain the user picked stays)
            if (r.get("domain") or "") in ("", domain_of(r["fact"], r.get("category") or "", r.get("entity") or "")):
                data["domain"] = domain_of(data.get("fact", r["fact"]), data.get("category", r.get("category") or ""),
                                           data.get("entity", r.get("entity") or ""))
        if data.get("tier") == "long":
            data.setdefault("expires_at", None)
        elif data.get("tier") == "recent" and r["tier"] != "recent":
            data.setdefault("expires_at", now_ts() + self.RECENT_DAYS * 86400)
        if "fact" in data and data["fact"] != r["fact"]:
            data["history"] = ((r.get("history") or "") + "\n" + r["fact"]).strip()[-2000:]
            self.db.execute("DELETE FROM facts_fts WHERE id=?", (fid,))
            self.db.execute("INSERT INTO facts_fts(id, fact, entity) VALUES (?,?,?)", (fid, data["fact"], data.get("entity", r["entity"])))
        if data:
            self.db.update("facts", "id", fid, data)
            if "domain" in data or "entity" in data:
                self.sync_entity(data.get("domain", r.get("domain") or ""), data.get("entity", r.get("entity") or ""))
        return self.fact(fid)

    # ------------------------------------------------------------ personal context (domains + entities)
    def _sort_domains(self):
        """Give older facts a domain (one-off, cheap; the user can change it on the Memory page)."""
        from app.runtime.context import domain_of
        rows = self.db.all("SELECT id, fact, category, entity FROM facts WHERE COALESCE(domain,'')=''")
        for r in rows:
            dom = domain_of(r["fact"] or "", r["category"] or "", r["entity"] or "")
            self.db.execute("UPDATE facts SET domain=? WHERE id=?", (dom, r["id"]))
            self.sync_entity(dom, r["entity"] or "")

    ENTITY_DOMAINS = ("person", "place", "account", "site")

    def sync_entity(self, domain: str, name: str):
        """People, places, accounts and sites named by facts become entities (aliases + relation live there)."""
        name = (name or "").strip()
        if domain not in self.ENTITY_DOMAINS or not (2 <= len(name) <= 60) or "@" in name:
            return
        if not self.db.one("SELECT id FROM entities WHERE lower(name)=lower(?)", (name,)):
            self.db.insert("entities", {"id": new_id("ent"), "type": domain, "name": name, "attrs": dumps({"aliases": []}),
                                        "created_at": now_ts()})

    def entities(self, kind: str | None = None) -> list[dict]:
        rows = self.db.all("SELECT * FROM entities" + (" WHERE type=?" if kind else "") + " ORDER BY type, name",
                           (kind,) if kind else ())
        rel = {r["dst"]: r["rel"] for r in self.db.all("SELECT dst, rel FROM relations WHERE src='me'")}
        for r in rows:
            r["attrs"] = loads(r["attrs"], {}) or {}
            r["relation"] = rel.get(r["id"], "")
        return rows

    def update_entity(self, eid: str, aliases: list[str] | None = None, relation: str | None = None,
                      kind: str | None = None) -> dict | None:
        e = self.db.one("SELECT * FROM entities WHERE id=?", (eid,))
        if not e:
            return None
        attrs = loads(e["attrs"], {}) or {}
        if aliases is not None:
            attrs["aliases"] = [a.strip()[:40] for a in aliases if a and a.strip()][:12]
        upd = {"attrs": dumps(attrs)}
        if kind in self.ENTITY_DOMAINS:
            upd["type"] = kind
        self.db.update("entities", "id", eid, upd)
        if relation is not None:
            self.db.execute("DELETE FROM relations WHERE src='me' AND dst=?", (eid,))
            if relation.strip():
                self.db.insert("relations", {"src": "me", "rel": relation.strip()[:40], "dst": eid, "source": "user",
                                             "created_at": now_ts()})
        return next((x for x in self.entities() if x["id"] == eid), None)

    def delete_entity(self, eid: str):
        self.db.execute("DELETE FROM entities WHERE id=?", (eid,))
        self.db.execute("DELETE FROM relations WHERE dst=? OR src=?", (eid, eid))

    def delete_fact(self, fid: str):
        row = self.db.one("SELECT fact FROM facts WHERE id=?", (fid,))
        self.db.execute("DELETE FROM facts WHERE id=?", (fid,))
        self.db.execute("DELETE FROM facts_fts WHERE id=?", (fid,))
        if row and row.get("fact"):
            # 2026-10-04 M4-21: after "forget my taxi budget" the agent still answered "300" from a past-task summary —
            # a forgotten fact must not live on in the episodes that quote it
            for e in self.db.all("SELECT id, summary FROM episodes"):
                if mentions_fact(row["fact"], e["summary"] or ""):
                    self.db.execute("DELETE FROM episodes WHERE id=?", (e["id"],))

    def _live(self, r: dict) -> bool:
        if r.get("expires_at") and r["expires_at"] < now_ts():
            return False
        return not (r["ttl_days"] and r["created_at"] + r["ttl_days"] * 86400 < now_ts())

    def facts(self, limit=500, tier: str | None = "long") -> list[dict]:
        q, p = "SELECT * FROM facts", []
        if tier:
            q += " WHERE COALESCE(tier,'long')=?"
            p.append(tier)
        rows = self.db.all(q + " ORDER BY created_at DESC LIMIT ?", (*p, limit))
        return [r for r in rows if self._live(r)]

    def search_facts(self, query: str, limit=12, tier: str | None = "long", fuzzy: bool = True) -> list[dict]:
        terms = [t for t in re.split(r"[\s,，。.!?？！;；:：]+", query or "") if len(t) >= 2][:12]
        rows: list[dict] = []
        if terms:
            q = " OR ".join('"' + t.replace('"', "") + '"' for t in terms)
            try:
                ids = [r["id"] for r in self.db.all("SELECT id FROM facts_fts WHERE facts_fts MATCH ? LIMIT ?", (q, limit * 3))]
            except Exception:
                ids = []
            if not ids:
                like = [f"%{t}%" for t in terms]
                cond = " OR ".join("fact LIKE ?" for _ in like)
                ids = [r["id"] for r in self.db.all(f"SELECT id FROM facts WHERE {cond} LIMIT ?", (*like, limit * 3))]
            for i in ids:
                r = self.fact(i)
                if r and self._live(r) and (not tier or (r.get("tier") or "long") == tier):
                    rows.append(r)
        if fuzzy and len(rows) < limit:
            # a Chinese query is one long "word" ("我穿多大码的鞋"): rank by shared bigrams / words and by topic
            from app.runtime import context
            qt = context.tokens(query)
            its = context.intents(query)
            have = {r["id"] for r in rows}
            pool = self.facts(1000, tier=tier) if tier else self.facts(1000, tier=None)
            ranked = []
            for r in pool:
                if r["id"] in have:
                    continue
                txt = f"{r['fact']} {r.get('entity') or ''}"
                sc = len(qt & context.tokens(txt)) + sum(2 for k in its if context._INTENT_RX[k][1].search(txt))
                if sc >= 2:
                    ranked.append((sc, r))
            ranked.sort(key=lambda x: -x[0])
            rows += [r for _, r in ranked[:limit - len(rows)]]
        return rows[:limit]

    def mark_used(self, ids: list[str]):
        for fid in ids:
            self.db.execute("UPDATE facts SET uses=COALESCE(uses,0)+1, last_used=? WHERE id=?", (now_ts(), fid))

    def prune_memory(self) -> dict:
        """Drop expired recent facts and episodes older than RECENT_DAYS."""
        gone = [r["id"] for r in self.db.all("SELECT id FROM facts WHERE expires_at IS NOT NULL AND expires_at < ?", (now_ts(),))]
        for fid in gone:
            self.delete_fact(fid)
        cut = now_ts() - self.RECENT_DAYS * 86400
        n_ep = self.db.one("SELECT COUNT(*) AS n FROM episodes WHERE ts < ?", (cut,))["n"]
        self.db.execute("DELETE FROM episodes WHERE ts < ?", (cut,))
        return {"facts": len(gone), "episodes": n_ep}

    def add_episode(self, task_id: str, summary: str):
        self.db.insert("episodes", {"ts": now_ts(), "task_id": task_id, "summary": summary[:1000]})

    def episodes(self, limit=50) -> list[dict]:
        cut = now_ts() - self.RECENT_DAYS * 86400
        return self.db.all("SELECT * FROM episodes WHERE ts >= ? ORDER BY id DESC LIMIT ?", (cut, limit))

    # ------------------------------------------------------------ profile (fixed fields; every change needs the user)
    def profile(self) -> dict:
        return {r["key"]: r["value"] for r in self.db.all("SELECT key, value FROM profile") if (r["value"] or "").strip()}

    def set_profile(self, key: str, value: str, source: str = "user"):
        key = profile_key(key)
        if not key:
            raise ValueError("unknown profile field")
        value = (value or "").strip()[:500]
        if value:
            self.db.execute("INSERT OR REPLACE INTO profile(key, value, updated_at, source) VALUES (?,?,?,?)",
                            (key, value, now_ts(), source))
        else:
            self.db.execute("DELETE FROM profile WHERE key=?", (key,))
        # a pending suggestion for this field is settled by the user's own edit
        self.db.execute("UPDATE profile_pending SET status='superseded', resolved_at=? WHERE key=? AND status='pending'",
                        (now_ts(), key))

    def suggest_profile(self, key: str, value: str, reason: str = "", source: str = "") -> dict | None:
        """Queue a change for the user to confirm. Never changes the profile by itself."""
        key = profile_key(key)
        value = (value or "").strip()[:500]
        if not key or not value or looks_sensitive(value) or not profile_value_ok(key, value):
            return None
        cur = self.profile().get(key, "")
        if norm_fact(cur) == norm_fact(value):
            return None
        for r in self.db.all("SELECT * FROM profile_pending WHERE key=? AND status='pending'", (key,)):
            if norm_fact(r["value"]) == norm_fact(value):
                return None
        pid = new_id("pp")
        self.db.insert("profile_pending", {"id": pid, "key": key, "value": value, "old": cur, "reason": reason[:300],
                                           "source": source[:80], "status": "pending", "created_at": now_ts(),
                                           "resolved_at": None})
        return self.db.one("SELECT * FROM profile_pending WHERE id=?", (pid,))

    def profile_pending(self, status: str = "pending") -> list[dict]:
        return self.db.all("SELECT * FROM profile_pending WHERE status=? ORDER BY created_at DESC LIMIT 100", (status,))

    def resolve_profile(self, pid: str, accept: bool, value: str | None = None) -> dict | None:
        r = self.db.one("SELECT * FROM profile_pending WHERE id=?", (pid,))
        if not r or r["status"] != "pending":
            return None
        if accept:
            self.set_profile(r["key"], value if value is not None else r["value"], source=f"confirmed:{r['source']}")
        self.db.execute("UPDATE profile_pending SET status=?, resolved_at=? WHERE id=?",
                        ("accepted" if accept else "rejected", now_ts(), pid))
        return self.db.one("SELECT * FROM profile_pending WHERE id=?", (pid,))

    # ------------------------------------------------------------ memory housekeeping runs
    def add_memory_run(self, kind: str, report: dict) -> int:
        return self.db.insert("memory_runs", {"ts": now_ts(), "kind": kind, "report": dumps(report)})

    def memory_runs(self, limit=10) -> list[dict]:
        rows = self.db.all("SELECT * FROM memory_runs ORDER BY id DESC LIMIT ?", (limit,))
        for r in rows:
            r["report"] = loads(r["report"], {})
        return rows

    # ------------------------------------------------------------ schedules
    def schedules(self) -> list[dict]:
        rows = self.db.all("SELECT * FROM schedules ORDER BY created_at DESC")
        for r in rows:
            r["state"] = loads(r["state"], {})
        return rows

    def schedule(self, sid: str) -> dict | None:
        r = self.db.one("SELECT * FROM schedules WHERE id=?", (sid,))
        if r:
            r["state"] = loads(r["state"], {})
        return r

    # ------------------------------------------------------------ goals
    def goals(self) -> list[dict]:
        rows = self.db.all("SELECT * FROM goals ORDER BY (status='active') DESC, created_at DESC")
        for r in rows:
            r["progress"] = loads(r["progress"], [])
        return rows

    def goal(self, gid: str) -> dict | None:
        r = self.db.one("SELECT * FROM goals WHERE id=?", (gid,))
        if r:
            r["progress"] = loads(r["progress"], [])
        return r

    # ------------------------------------------------------------ notifications
    def notify(self, title: str, body: str, task_id: str = "", level: str = "info") -> dict:
        nid = self.db.insert("notifications", {"ts": now_ts(), "title": title, "body": body, "task_id": task_id,
                                               "level": level, "read": 0})
        return {"id": nid, "ts": now_ts(), "title": title, "body": body, "task_id": task_id, "level": level, "read": 0}

    def notifications(self, limit=50) -> list[dict]:
        return self.db.all("SELECT * FROM notifications ORDER BY id DESC LIMIT ?", (limit,))
