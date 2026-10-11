"""Agent Runtime HTTP API (reached only through Sentinel's reverse proxy)."""
from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import re
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from app.common.util import VERSION, token_ok
from app.runtime.agent import TERMINAL, WORKSPACE, Runtime
from app.runtime import goals as G
from app.runtime.scheduler import EVENT_SOURCES, Scheduler, create_schedule, describe, next_run, validate
from app.runtime.scheduler import WAITING as SCHED_WAITING

DATA = os.environ.get("RUNTIME_DATA", "/data")
RUNTIME_TOKEN = os.environ.get("RUNTIME_TOKEN", "")

subscribers: set[asyncio.Queue] = set()


async def publish(ev: dict):
    ev.setdefault("ts", time.time())
    for q in list(subscribers):
        try:
            q.put_nowait(ev)
        except asyncio.QueueFull:
            pass


rt: Runtime = None  # type: ignore
sched: Scheduler = None  # type: ignore


@asynccontextmanager
async def lifespan(app):
    global rt, sched
    from app.common import stallwatch
    stallwatch.start(DATA, "runtime")
    rt = Runtime(DATA, publish)
    from app.runtime import skills as SK
    seeded = SK.seed(rt.store)
    if seeded is not None:
        print(f"[skills] initial selection written: {'all on' if not seeded else 'off: ' + ', '.join(seeded)}"
              f"{' (from OMUSE_SKILLS)' if os.environ.get('OMUSE_SKILLS') else ''}", flush=True)
    sched = Scheduler(rt)
    sched.start()
    rt.health.start()
    rt.golden.start()
    await rt.recover()
    yield


app = FastAPI(lifespan=lifespan, title="OMuse Runtime")


def internal_auth(x_persona_runtime: str | None = Header(default=None)):
    if not token_ok(x_persona_runtime, RUNTIME_TOKEN):
        raise HTTPException(401, "unauthorized")


@app.get("/api/health")
async def health():
    return {"ok": True, "version": VERSION}


# ------------------------------------------------------------------ chat & conversations
@app.put("/api/upload")
async def upload(req: Request, name: str = ""):
    """The chat's ＋ button: the raw file is the request body; it is stored under workspace/uploads/<YYYY-MM>/."""
    from app.runtime import attachments as AT
    if int(req.headers.get("content-length") or 0) > AT.UPLOAD_MAX:
        raise HTTPException(413, f"文件超过 {AT.UPLOAD_MAX // 1024 // 1024} MB (file too large)")
    data = await req.body()
    try:
        info = await asyncio.to_thread(AT.save_upload, WORKSPACE, name, data)
    except AT.AttachmentError as e:
        raise HTTPException(400, str(e))
    await rt.audit("user", "file.upload", resource=info["path"], detail={"size": info["size"], "mime": info["mime"]})
    return info


def _attachments(raw) -> list[dict]:
    from app.runtime import attachments as AT
    out = []
    for x in (raw or [])[:AT.UPLOAD_MAX_FILES]:
        rel = str((x or {}).get("path") if isinstance(x, dict) else x or "").strip().lstrip("/")
        fp = os.path.realpath(os.path.join(WORKSPACE, rel))
        if not rel.startswith("uploads/") or not fp.startswith(os.path.join(WORKSPACE, "uploads") + os.sep) or not os.path.isfile(fp):
            raise HTTPException(400, f"附件不存在 attachment not found: {rel}")
        out.append(AT.info(WORKSPACE, fp))
    return out


@app.post("/api/chat")
async def chat(req: Request):
    b = await req.json()
    text = str(b.get("message", "")).strip()
    atts = _attachments(b.get("attachments"))
    if not text and atts:
        en = rt.store.settings().get("language") == "en"
        text = "Please look at the attached file(s)." if en else "请看一下附件。"
    if not text:
        raise HTTPException(400, "message is empty")
    cid = b.get("conversation_id")
    if not cid or not rt.store.conv(cid):
        cid = rt.store.create_conv(text[:40])
    rt.store.add_msg(cid, "user", text, meta={"attachments": atts} if atts else None)
    t = await rt.submit(cid, text, attachments=atts)
    rt.store.db.execute("UPDATE messages SET task_id=? WHERE id=(SELECT MAX(id) FROM messages WHERE conv_id=? AND role='user')", (t["id"], cid))
    await publish({"kind": "conv_update", "conv_id": cid})
    return {"conversation_id": cid, "task_id": t["id"]}


@app.get("/api/conversations")
async def conversations(kind: str | None = None):
    rows = rt.store.convs(200)
    if kind:
        rows = [r for r in rows if r["kind"] == kind]
    return {"conversations": rows}


@app.get("/api/conversations/{cid}")
async def conversation(cid: str):
    c = rt.store.conv(cid)
    if not c:
        raise HTTPException(404)
    msgs = rt.store.msgs(cid, 300)
    tids = sorted({m["task_id"] for m in msgs if m["task_id"]})
    tasks = {tid: rt.task_brief(rt.store.task(tid)) for tid in tids if rt.store.task(tid)}
    return {"conversation": c, "messages": msgs, "tasks": tasks}


@app.delete("/api/conversations/{cid}")
async def del_conv(cid: str):
    rt.store.delete_conv(cid)
    return {"ok": True}


# ------------------------------------------------------------------ tasks
@app.get("/api/tasks")
async def tasks(status: str | None = None, limit: int = 100):
    return {"tasks": rt.store.tasks(status, min(limit, 500))}


@app.get("/api/tasks/{tid}")
async def task(tid: str):
    t = rt.store.task(tid)
    if not t:
        raise HTTPException(404)
    brief = rt.task_brief(t)
    brief["events"] = rt.store.events(tid)
    return brief


@app.post("/api/tasks/{tid}/{action}")
async def task_action(tid: str, action: str):
    t = rt.store.task(tid)
    if not t:
        raise HTTPException(404)
    if action == "cancel":
        await rt.cancel(tid)
    elif action == "pause":
        await rt.pause(tid)
    elif action == "resume":
        await rt.resume(tid)
    elif action == "retry":
        if t["status"] not in TERMINAL:
            raise HTTPException(409, "task still active")
        nt = await rt.submit(t["conv_id"], t["goal"], t["source"], t["schedule_id"], attachments=t.get("attachments") or None)
        return {"ok": True, "task_id": nt["id"]}
    else:
        raise HTTPException(404, "unknown action")
    return {"ok": True}


# ------------------------------------------------------------------ live events (SSE)
@app.get("/api/stream")
async def stream(request: Request):
    q: asyncio.Queue = asyncio.Queue(maxsize=500)
    subscribers.add(q)

    async def gen():
        try:
            yield "retry: 3000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
                except asyncio.TimeoutError:
                    # a real event (not an SSE comment) so the page can tell a live stream from a silently dead one
                    yield 'data: {"kind": "ping"}\n\n'
        finally:
            subscribers.discard(q)
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ------------------------------------------------------------------ schedules
@app.get("/api/schedules")
async def schedules():
    out = []
    for x in rt.store.schedules():
        if x.get("goal_id"):
            continue  # shown on the goal card
        st = x["state"] or {}
        x["describe"] = describe(x)
        x["state"] = {k: v for k, v in st.items() if not str(k).startswith("_")}
        x["trigger"] = {k: st.get(k) for k in ("_error", "_error_at", "_checked", "_seen", "_last_events") if st.get(k) is not None}
        last = rt.store.task(x["last_task"]) if x.get("last_task") else None
        x["last_status"] = last["status"] if last else ""
        x["blocked"] = {k[1:]: st[k] for k in ("_skipped", "_superseded") if st.get(k)}
        out.append(x)
    return {"schedules": out, "sources": EVENT_SOURCES}


# ------------------------------------------------------------------ goals
@app.get("/api/goals")
async def goals():
    return {"goals": [G.brief(rt.store, g) for g in rt.store.goals()]}


@app.post("/api/goals")
async def add_goal(req: Request):
    b = await req.json()
    try:
        g = G.create_goal(rt.store, title=str(b.get("title", "")), objective=str(b.get("objective", "")),
                          criteria=str(b.get("criteria", "")), kind=str(b.get("kind", "interval")), spec=b.get("spec", "60"),
                          tz=rt.store.settings()["timezone"], deadline=b.get("deadline") or None)
    except ValueError as e:
        raise HTTPException(400, str(e))
    await rt.audit("user", "goal.create", resource=g["id"], detail={"title": g["title"]})
    if b.get("run_now"):
        await sched.run_now(g["schedule_id"])
    return G.brief(rt.store, rt.store.goal(g["id"]))


@app.put("/api/goals/{gid}")
async def upd_goal(gid: str, req: Request):
    g = rt.store.goal(gid)
    if not g:
        raise HTTPException(404)
    b = await req.json()
    data = {}
    for k in ("title", "objective", "criteria"):
        if k in b:
            data[k] = str(b[k])[:3000]
    try:
        if "deadline" in b:
            data["deadline"] = G.parse_deadline(b["deadline"])
        if data:
            data["updated_at"] = time.time()
            rt.store.db.update("goals", "id", gid, data)
        if "kind" in b or "spec" in b:
            sch = rt.store.schedule(g["schedule_id"])
            kind, spec = str(b.get("kind", sch["kind"])), b.get("spec", sch["spec"])
            spec = spec if isinstance(spec, str) else json.dumps(spec, ensure_ascii=False)
            validate(kind, spec)
            rt.store.db.update("schedules", "id", sch["id"], {"kind": kind, "spec": spec, "next_run": next_run(kind, spec, sch["tz"])})
        if "status" in b:
            G.set_status(rt.store, gid, str(b["status"]))
    except ValueError as e:
        raise HTTPException(400, str(e))
    await rt.audit("user", "goal.update", resource=gid, detail={k: b[k] for k in b if k != "objective"})
    return G.brief(rt.store, rt.store.goal(gid))


@app.post("/api/goals/{gid}/run")
async def run_goal(gid: str):
    g = rt.store.goal(gid)
    if not g:
        raise HTTPException(404)
    if g["status"] != "active":
        raise HTTPException(400, "目标不在进行中 (goal is not active)")
    t = await sched.run_now(g["schedule_id"])
    return {"task_id": t["id"]}


@app.delete("/api/goals/{gid}")
async def del_goal(gid: str):
    g = rt.store.goal(gid)
    if g:
        rt.store.db.execute("DELETE FROM schedules WHERE id=?", (g["schedule_id"],))
        rt.store.db.execute("DELETE FROM goals WHERE id=?", (gid,))
    await rt.audit("user", "goal.delete", resource=gid)
    return {"ok": True}


@app.post("/api/schedules")
async def add_schedule(req: Request):
    b = await req.json()
    try:
        spec = b["spec"] if isinstance(b["spec"], str) else json.dumps(b["spec"], ensure_ascii=False)
        s = create_schedule(rt.store, str(b["name"]), str(b["goal"]), str(b.get("kind", "cron")), spec,
                            str(b.get("tz") or rt.store.settings()["timezone"]))
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e))
    await rt.audit("user", "schedule.create", resource=s["id"], detail={"name": s["name"], "spec": s["spec"]})
    return s


@app.put("/api/schedules/{sid}")
async def upd_schedule(sid: str, req: Request):
    s = rt.store.schedule(sid)
    if not s:
        raise HTTPException(404)
    b = await req.json()
    data = {}
    for k in ("name", "goal", "kind", "spec", "tz"):
        if k in b:
            data[k] = b[k] if isinstance(b[k], str) else json.dumps(b[k], ensure_ascii=False)
    if "enabled" in b:
        data["enabled"] = 1 if b["enabled"] else 0
    merged = {**s, **data}
    try:
        validate(merged["kind"], merged["spec"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    data["next_run"] = next_run(merged["kind"], merged["spec"], merged["tz"])
    rt.store.db.update("schedules", "id", sid, data)
    return rt.store.schedule(sid)


@app.delete("/api/schedules/{sid}")
async def del_schedule(sid: str):
    rt.store.db.execute("DELETE FROM schedules WHERE id=?", (sid,))
    await rt.audit("user", "schedule.delete", resource=sid)
    return {"ok": True}


@app.post("/api/schedules/{sid}/poll")
async def poll_schedule(sid: str):
    """Check an event trigger right now (instead of waiting for the next poll)."""
    s = rt.store.schedule(sid)
    if not s or s["kind"] != "event":
        raise HTTPException(400, "不是事件触发器 (not an event trigger)")
    last = rt.store.task(s["last_task"]) if s.get("last_task") else None
    if last and last["status"] not in TERMINAL:
        raise HTTPException(409, "上一次运行还没结束 (previous run still active)")
    n = await sched.poll_event(s)
    s2 = rt.store.schedule(sid)
    st = s2["state"] or {}
    return {"ok": not st.get("_error"), "error": st.get("_error", ""), "fired": bool(n) or s2["last_task"] != s.get("last_task"),
            "task_id": s2["last_task"] if s2["last_task"] != s.get("last_task") else ""}


@app.post("/api/schedules/{sid}/run")
async def run_schedule(sid: str):
    s = rt.store.schedule(sid)
    last = rt.store.task(s["last_task"]) if s and s.get("last_task") else None
    if last and last["status"] in SCHED_WAITING:
        await sched.supersede(s, last, manual=True)   # don't leave the old run (and its approval) dangling
    t = await sched.run_now(sid)
    return {"task_id": t["id"]}


# ------------------------------------------------------------------ memory
# ------------------------------------------------------------------ skills
@app.get("/api/skills")
async def skills_list():
    from app.runtime import skills as SK
    out = SK.listing(rt.store.settings())
    for x in out:
        x.pop("path", None)
        if x["source"] == "imported":
            x["url"] = SK.source_link(x["name"])
    return {"skills": out, "env": (os.environ.get("OMUSE_SKILLS") or "").strip()}   # env: informational only (seed at first start)


@app.put("/api/skills")
async def skills_select(req: Request):
    """Which skills are on: the body lists the names that are off (an empty list = everything on)."""
    from app.runtime import skills as SK
    b = await req.json()
    known = {s["name"] for s in SK.all_skills()}
    off = sorted({str(x) for x in (b.get("disabled") or []) if str(x) in known})
    rt.store.set_settings({"skills_disabled": off})
    await rt.audit("user", "skills.select", detail={"disabled": off})
    return {"skills": [{k: v for k, v in x.items() if k != "path"} for x in SK.listing(rt.store.settings())]}


@app.post("/api/skills/import")
async def skills_import(req: Request):
    from app.runtime import skills as SK
    b = await req.json()
    try:
        info = await SK.import_from_github(str(b.get("url") or ""))
    except SK.SkillError as e:
        raise HTTPException(400, str(e))
    await rt.audit("user", "skills.import", resource=info["name"], detail={"url": info["url"]})
    return {"skill": info}


@app.delete("/api/skills/{name}")
async def skills_delete(name: str):
    from app.runtime import skills as SK
    if not SK.delete_imported(name):
        raise HTTPException(404, "只能删除导入的技能 (only imported skills can be removed)")
    cur = rt.store.settings().get("skills_disabled")
    if isinstance(cur, list):
        rt.store.set_settings({"skills_disabled": [x for x in cur if x != name]})
    await rt.audit("user", "skills.delete", resource=name)


# ------------------------------------------------------------------ research library
async def _start_research(sub: dict, refresh: bool) -> dict:
    from app.runtime import library as LIB
    lang = rt.store.settings().get("language") or "zh"
    rt.store.update_subject(sub["id"], status="researching", error="")
    t = await rt.submit(sub["conv_id"], LIB.research_goal(sub, refresh, lang), source="library")
    rt.store.update_subject(sub["id"], last_task=t["id"])
    await publish({"kind": "conv_update", "conv_id": sub["conv_id"]})
    await publish({"kind": "library_update", "subject_id": sub["id"]})
    return t


@app.get("/api/library")
async def library_list():
    return {"subjects": rt.store.subjects()}


@app.post("/api/library")
async def library_create(req: Request):
    """A new research subject: its report file, its own conversation, and the first research task."""
    from app.runtime import library as LIB
    b = await req.json()
    title = str(b.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title required")
    rec = LIB.new_subject(title, str(b.get("brief") or ""))
    rec["conv_id"] = rt.store.create_conv(title, kind="research")
    sub = rt.store.create_subject(rec)
    os.makedirs(os.path.join(WORKSPACE, "library", sub["slug"]), exist_ok=True)
    await rt.audit("user", "library.create", detail={"title": title, "slug": sub["slug"]})
    t = await _start_research(sub, refresh=False)
    return {"subject": rt.store.subject(sub["id"]), "task_id": t["id"]}


@app.get("/api/library/search")
async def library_search(q: str = ""):
    return {"hits": rt.store.library_search(q, 10)}


@app.get("/api/library/{sid}")
async def library_get(sid: str):
    from app.runtime import library as LIB
    sub = rt.store.subject(sid)
    if not sub:
        raise HTTPException(404)
    return {"subject": sub, "report": LIB.read_report(WORKSPACE, sub["slug"]), "path": LIB.report_path(sub["slug"])}


@app.post("/api/library/{sid}/refresh")
async def library_refresh(sid: str):
    sub = rt.store.subject(sid)
    if not sub:
        raise HTTPException(404)
    if sub["status"] == "researching" and sub["last_task"] and (rt.store.task(sub["last_task"]) or {}).get("status") not in TERMINAL:
        raise HTTPException(409, "这个课题正在研究中 (research already running)")
    await rt.audit("user", "library.refresh", detail={"slug": sub["slug"]})
    t = await _start_research(sub, refresh=True)
    return {"subject": rt.store.subject(sid), "task_id": t["id"]}


@app.delete("/api/library/{sid}")
async def library_delete(sid: str):
    """Removes the subject and its index; the report files stay in the workspace and the chat stays in the list."""
    sub = rt.store.subject(sid)
    if not sub:
        raise HTTPException(404)
    rt.store.delete_subject(sid)
    await rt.audit("user", "library.delete", detail={"slug": sub["slug"]})
    await publish({"kind": "library_update", "subject_id": sid})
    return {"ok": True}


@app.get("/api/memory")
async def memory():
    from app.runtime import memory_tidy as MT
    from app.runtime.store import PROFILE_FIELDS
    st = rt.store
    runs = [{"id": r["id"], "ts": r["ts"], "kind": r["kind"], "lines": (r["report"] or {}).get("lines") or [],
             "errors": (r["report"] or {}).get("errors") or [], "applied": (r["report"] or {}).get("applied")}
            for r in st.memory_runs(10)]
    from app.runtime.context import DOMAINS
    return {"facts": st.facts(), "recent": st.facts(1000, tier="recent"), "episodes": st.episodes(50),
            "domains": [{"key": k, "zh": zh, "en": en} for k, zh, en in DOMAINS], "entities": st.entities(),
            "profile": st.profile(), "profile_fields": [{"key": k, "zh": zh, "en": en} for k, zh, en in PROFILE_FIELDS],
            "pending": st.profile_pending(), "runs": runs, "job": MT.job_state(),
            "needs_first_review": MT.needs_first_review(st), "library": st.subjects(),
            "settings": {k: st.settings().get(k) for k in ("memory_consolidation", "memory_consolidate_at", "memory_extraction")}}


@app.post("/api/memory")
async def add_memory(req: Request):
    from app.runtime.store import looks_sensitive
    b = await req.json()
    fact = str(b.get("fact", ""))
    if looks_sensitive(fact):
        raise HTTPException(400, "证件号、卡号和密码请放进保险箱 (ID / card numbers and passwords belong in the vault)")
    r = rt.store.add_fact(fact, str(b.get("category") or "preference"), str(b.get("entity") or ""),
                          source="user-ui", confidence=1.0, tier="recent" if b.get("tier") == "recent" else "long",
                          domain=str(b.get("domain") or ""))
    if not r:
        raise HTTPException(400, "empty fact")
    await rt.audit("user", "memory.add", detail={"fact": r["fact"]})
    return r


@app.put("/api/memory/{fid}")
async def edit_memory(fid: str, req: Request):
    from app.runtime.store import looks_sensitive
    b = await req.json()
    kw = {}
    if isinstance(b.get("fact"), str) and b["fact"].strip():
        if looks_sensitive(b["fact"]):
            raise HTTPException(400, "证件号、卡号和密码请放进保险箱 (ID / card numbers and passwords belong in the vault)")
        kw["fact"] = b["fact"].strip()[:500]
    if b.get("tier") in ("long", "recent"):
        kw["tier"] = b["tier"]
    if isinstance(b.get("category"), str):
        kw["category"] = b["category"][:30]
    if isinstance(b.get("domain"), str):
        kw["domain"] = b["domain"]
    if b.get("status") in ("active", "pending"):
        kw["status"] = b["status"]       # "active" = the user confirmed something OMuse learned
    if isinstance(b.get("entity"), str):
        kw["entity"] = b["entity"].strip()[:60]
    r = rt.store.update_fact(fid, **kw)
    if not r:
        raise HTTPException(404, "not found")
    await rt.audit("user", "memory.edit", resource=fid, detail={k: v for k, v in kw.items()})
    return r


@app.get("/api/context/preview")
async def context_preview(q: str = "", mode: str = "v1"):
    """What OMuse would know going into a request (Memory page → "试一试"; also used by the batch 2 tests)."""
    from app.runtime import context
    if mode == "legacy":
        facts = rt._facts_legacy(q)
    else:
        facts = context.select(q, rt.store.facts(500), rt.store.entities(), limit=12)
    return {"mode": mode, "facts": [{"id": f["id"], "fact": f["fact"], "domain": f.get("domain"), "status": f.get("status"),
                                     "why": f.get("why", ""), "score": f.get("score")} for f in facts]}


@app.put("/api/entities/{eid}")
async def edit_entity(eid: str, req: Request):
    b = await req.json()
    al = b.get("aliases")
    if isinstance(al, str):
        al = [x for x in re.split(r"[,，、;；]", al)]
    r = rt.store.update_entity(eid, aliases=al if isinstance(al, list) else None,
                               relation=b.get("relation") if isinstance(b.get("relation"), str) else None,
                               kind=b.get("type"))
    if not r:
        raise HTTPException(404, "not found")
    await rt.audit("user", "memory.entity", resource=eid, detail={k: b.get(k) for k in ("aliases", "relation", "type")})
    await rt.publish({"kind": "memory_update"})
    return r


@app.delete("/api/entities/{eid}")
async def del_entity(eid: str):
    rt.store.delete_entity(eid)
    return {"ok": True}


@app.delete("/api/memory/{fid}")
async def del_memory(fid: str):
    rt.store.delete_fact(fid)
    await rt.audit("user", "memory.forget", resource=fid)
    return {"ok": True}


@app.put("/api/profile")
async def set_profile(req: Request):
    """The user's own edit on the Memory page (this is the confirmation)."""
    from app.runtime.store import looks_sensitive, profile_key
    b = await req.json()
    key, val = profile_key(str(b.get("key", ""))), str(b.get("value") or "")
    if not key:
        raise HTTPException(400, "unknown field")
    if looks_sensitive(val):
        raise HTTPException(400, "证件号、卡号和密码请放进保险箱 (ID / card numbers and passwords belong in the vault)")
    rt.store.set_profile(key, val, source="user-ui")
    await rt.audit("user", "profile.set", resource=key)
    return {"profile": rt.store.profile()}


@app.post("/api/profile/pending/{pid}")
async def resolve_profile(pid: str, req: Request):
    b = await req.json()
    val = b.get("value")
    r = rt.store.resolve_profile(pid, bool(b.get("accept")), str(val) if isinstance(val, str) and val.strip() else None)
    if not r:
        raise HTTPException(409, "already resolved")
    await rt.audit("user", "profile.accept" if r["status"] == "accepted" else "profile.reject", resource=r["key"])
    await publish({"kind": "memory_update"})
    return r


@app.post("/api/memory/consolidate")
async def consolidate(req: Request):
    """{dry_run: true} → preview; {from_run: <id>} → apply that preview exactly; {} → plan and apply now."""
    from app.runtime import memory_tidy as MT
    b = await req.json()
    from_run = int(b["from_run"]) if str(b.get("from_run") or "").isdigit() else None
    ok = MT.start(rt, dry_run=bool(b.get("dry_run")) and not from_run, kind="manual", from_run=from_run)
    if not ok:
        raise HTTPException(409, "正在整理中 (a tidy run is already in progress)")
    return {"started": True}


@app.get("/api/memory/runs/{rid}")
async def memory_run(rid: int):
    r = next((x for x in rt.store.memory_runs(50) if x["id"] == rid), None)
    if not r:
        raise HTTPException(404, "not found")
    return r


# ------------------------------------------------------------------ trust: metrics, health, golden runs, outcomes
@app.get("/api/metrics")
async def api_metrics(days: int = 7):
    from app.runtime import metrics
    days = max(1, min(int(days), 90))
    off = float(rt.store.settings().get("tz_offset_hours") or 8)
    m = await asyncio.to_thread(metrics.compute, rt.store, days, None, off)
    runs = rt.golden.runs(6)
    return {"metrics": m, "health": rt.health.status(), "golden": {"running": rt.golden.running, "runs": runs}}


@app.get("/api/health/status")
async def api_health():
    return rt.health.status()


@app.post("/api/health/check")
async def api_health_check():
    res = await rt.health.run_checks()
    for comp, (ok, detail) in res.items():
        await rt.health.observe(comp, ok, detail)
    return rt.health.status()


@app.get("/api/golden/runs")
async def golden_runs(limit: int = 10):
    from app.runtime.golden import CASES, CTX_CASES
    return {"running": rt.golden.running, "runs": rt.golden.runs(min(limit, 50)),
            "cases": [{"id": c["id"], "title": c["title"], "prompt": c["prompt"]} for c in CASES],
            "context_cases": [{"id": c["id"], "title": c["title"], "prompt": c["prompt"]} for c in CTX_CASES]}


@app.post("/api/golden/run")
async def golden_run(req: Request):
    b = await req.json() if (req.headers.get("content-length") or "0") != "0" else {}
    if rt.golden.running:
        raise HTTPException(409, "黄金测试已在运行 (already running)")
    if b.get("suite") == "context_probe":
        asyncio.create_task(rt.golden.context_probe("legacy" if b.get("context") == "legacy" else "v1"))
        await asyncio.sleep(0.2)
        return {"ok": True, "run_id": rt.golden.running}
    only = [str(x) for x in (b.get("only") or [])] or None
    suite = "context" if b.get("suite") == "context" else ""
    ctx = "legacy" if b.get("context") == "legacy" else ""
    asyncio.create_task(rt.golden.run("manual", only, suite, ctx))
    await asyncio.sleep(0.2)
    return {"ok": True, "run_id": rt.golden.running}


@app.post("/api/ledger/backfill")
async def ledger_backfill():
    """Ledger entries for purchases made before the ledger existed, with the order number their task got."""
    from app.runtime import outcome
    res = await rt.sentinel("POST", "/internal/ledger/backfill", {}, timeout=60)
    done = []
    for tid in res.get("tasks") or []:
        t = rt.store.task(tid)
        if not t:
            continue
        oc = t.get("outcome") or {}
        if not oc:
            texts = [str(m.get("content") or "") for m in (t.get("transcript") or []) if m.get("role") == "tool"]
            oc = outcome.assess(rt.store.events(tid), str(t.get("result") or ""), texts, t.get("goal") or "")
        await rt._ledger_confirm(tid, oc, str(t.get("result") or ""))
        done.append(tid)
    return {"created": res.get("created") or [], "confirmed": done}


@app.post("/api/ledger/reconcile")
async def ledger_reconcile():
    return await rt.health.reconcile_ledger()


@app.post("/api/outcome/{tid}")
async def task_outcome(tid: str):
    """Re-assess an older task's outcome from what it did (the tool results kept in its transcript)."""
    from app.runtime import outcome
    t = rt.store.task(tid)
    if not t:
        raise HTTPException(404, "no such task")
    texts = [str(m.get("content") or "") for m in (t.get("transcript") or []) if m.get("role") == "tool"]
    oc = outcome.assess(rt.store.events(tid), str(t.get("result") or ""), texts, t.get("goal") or "")
    rt.store.update_task(tid, outcome=oc)
    return {"task_id": tid, "outcome": oc}


# ------------------------------------------------------------------ notifications
@app.get("/api/notifications")
async def notifications():
    return {"notifications": rt.store.notifications(50)}


@app.post("/api/notifications/read")
async def notifications_read():
    rt.store.db.execute("UPDATE notifications SET read=1")
    return {"ok": True}


# ------------------------------------------------------------------ settings
@app.get("/api/settings")
async def get_settings():
    return {"settings": rt.store.settings(), "skills": [{"name": s["name"], "description": s["description"]} for s in rt.skills()]}


@app.put("/api/settings")
async def put_settings(req: Request):
    b = await req.json()
    if "memory_consolidate_at" in b and not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", str(b["memory_consolidate_at"]).strip()):
        raise HTTPException(400, "整理时间格式应为 HH:MM (time must be HH:MM)")
    s = rt.store.set_settings(b)
    await rt.audit("user", "settings.update", detail={k: v for k, v in b.items() if k != "extra_body"})
    return {"settings": s}


@app.post("/api/settings/test-model")
async def test_model():
    t0 = time.time()
    try:
        r = await rt.llm.chat([{"role": "user", "content": "只回复 OK 两个字母。Reply with just OK."}], purpose="test",
                              max_tokens=400, no_think=True)
        return {"ok": True, "reply": r["content"][:200], "latency_s": round(time.time() - t0, 2)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:500]}


@app.post("/api/settings/test-image")
async def test_image(req: Request):
    """Reachability check for the image endpoint — resolves base URL + model and lists models; never generates (no cost)."""
    from app.runtime import imagegen
    b = await req.json()
    s = dict(rt.store.settings())
    for k in ("image_base_url", "image_model"):
        if k in b:
            s[k] = str(b[k] or "").strip()
    t0 = time.time()
    try:
        base, model = await imagegen.resolve(s)
        listed = None
        try:
            ids = [str(m.get("id") or "") for m in await imagegen.list_models(base)]
            listed = model in ids
        except Exception:
            pass   # some image servers have no /models; the explicit model is still usable
        key = "OMUSE_IMAGE_API_KEY" if os.environ.get("OMUSE_IMAGE_API_KEY", "").strip() else (
            "model key" if imagegen.auth_headers() else "none")
        if listed is False:
            return {"ok": False, "error": f"端点可达，但模型列表里没有 {model} (endpoint reachable, but it does not list {model})",
                    "base": base, "model": model, "key": key}
        return {"ok": True, "base": base, "model": model, "key": key, "listed": listed, "latency_s": round(time.time() - t0, 2)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:500]}


# ------------------------------------------------------------------ workspace files (read-only for the UI)
@app.get("/api/files")
async def files(path: str = ""):
    base = os.path.realpath(os.path.join(WORKSPACE, path.lstrip("/")))
    if not base.startswith(WORKSPACE):
        raise HTTPException(400)
    if not os.path.isdir(base):
        raise HTTPException(404)
    items = []
    for n in sorted(os.listdir(base)):
        if n.startswith("."):
            continue
        fp = os.path.join(base, n)
        items.append({"name": n, "path": os.path.relpath(fp, WORKSPACE), "dir": os.path.isdir(fp),
                      "size": os.path.getsize(fp) if os.path.isfile(fp) else None, "mtime": os.path.getmtime(fp)})
    return {"path": os.path.relpath(base, WORKSPACE), "items": items}


@app.get("/api/files/raw")
async def file_raw(path: str, download: int = 0):
    fp = os.path.realpath(os.path.join(WORKSPACE, path.lstrip("/")))
    if not fp.startswith(WORKSPACE + os.sep) or not os.path.isfile(fp) or "/.quarantine/" in fp:
        raise HTTPException(404)
    # download=1: save with its real name (the chat's download button); otherwise open in the browser (PDF, images).
    # Active content (HTML/SVG/XML/JS, e.g. a page the agent downloaded) is never rendered on the app's own origin —
    # it could call the app's APIs — so it is always a download, and sandboxed just in case.
    mime = mimetypes.guess_type(fp)[0] or "application/octet-stream"
    risky = any(x in mime for x in ("html", "svg", "xml", "javascript")) or fp.lower().endswith((".htm", ".html", ".svg", ".xhtml", ".js", ".mjs"))
    inline = not download and not risky
    headers = {"X-Content-Type-Options": "nosniff"}
    if risky:
        headers["Content-Security-Policy"] = "sandbox; default-src 'none'"
    return FileResponse(fp, filename=os.path.basename(fp), content_disposition_type="inline" if inline else "attachment",
                        media_type=mime if not risky else "application/octet-stream", headers=headers)


# ------------------------------------------------------------------ internal callbacks from Sentinel
@app.post("/internal/approval_resolved", dependencies=[Depends(internal_auth)])
async def approval_resolved(req: Request):
    await rt.on_approval_resolved(await req.json())
    return {"ok": True}


@app.post("/internal/notify_user", dependencies=[Depends(internal_auth)])
async def notify_user(req: Request):
    b = await req.json()
    n = rt.store.notify(str(b.get("title") or "")[:120], str(b.get("body") or "")[:1000], level="info")
    await rt.publish({"kind": "notification", "notification": n})
    return {"ok": True}


@app.post("/internal/takeover_ended", dependencies=[Depends(internal_auth)])
async def takeover_ended(req: Request):
    await rt.on_takeover_ended(await req.json())
    return {"ok": True}


@app.exception_handler(HTTPException)
async def http_exc(req, exc: HTTPException):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
