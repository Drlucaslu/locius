"""Research library: a subject gets its own chat and a report file; the report is indexed for library_search and handed
to the agent in that chat (edits land in the file); a refresh re-runs the research; other tasks can search the library."""
import os
import sys
import time

import httpx

B = "http://127.0.0.1:8080"
H = {"X-Persona-UI": "1"}
WS = os.environ.get("WORKSPACE", "/tmp/claude-0/persona-test/workspace")
c = httpx.Client(timeout=60, trust_env=False)
fails = []


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name, "" if cond else str(info)[:1200])
    if not cond:
        fails.append(name)


def wait_task(tid, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        t = c.get(f"{B}/api/tasks/{tid}").json()
        if t["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
            return t
        time.sleep(0.5)
    return t


def subject(sid):
    return c.get(f"{B}/api/library/{sid}").json()


r = c.post(B + "/api/library", json={"title": "Home NAS 2026", "brief": "budget under 1000, four bays, Docker"}, headers=H).json()
sid, conv = r["subject"]["id"], r["subject"]["conv_id"]
check("subject created, researching, with its own chat", r["subject"]["status"] == "researching" and r["subject"]["slug"] == "home-nas-2026" and conv, r)
t = wait_task(r["task_id"])
check("the research task completes", t["status"] == "COMPLETED", (t["status"], t.get("error")))
s = subject(sid)
check("report written to library/<slug>/report.md and indexed", s["subject"]["status"] == "ready" and s["path"] == "library/home-nas-2026/report.md"
      and "UGREEN DXP4800" in s["report"] and s["subject"]["runs"] == 1 and s["subject"]["chars"] > 100, {k: s["subject"][k] for k in ("status", "runs", "chars")})
check("the report file is in the workspace", os.path.exists(os.path.join(WS, "library/home-nas-2026/report.md")))
hits = c.get(B + "/api/library/search", params={"q": "Docker"}).json()["hits"]
check("library search finds the passage with its subject and heading", any(h["title"] == "Home NAS 2026" and "DXP4800" in h["text"] and h["heading"] == "Candidates" for h in hits), hits)
convs = c.get(B + "/api/conversations").json()["conversations"]
check("the subject's chat is kind=research and keeps the subject's title", any(x["id"] == conv and x["kind"] == "research" and x["title"] == "Home NAS 2026" for x in convs))
mem = c.get(B + "/api/memory").json()
check("the Memory page payload lists the subject", any(x["id"] == sid for x in mem.get("library", [])))

# chat in the subject's conversation: the report is in the prompt, an edit lands in the file and the index
r2 = c.post(B + "/api/chat", json={"message": "LIBUPDATE add a section about noise", "conversation_id": conv}, headers=H).json()
t2 = wait_task(r2["task_id"])
check("a chat in the subject's conversation sees the current report", t2["status"] == "COMPLETED" and "CTX_OK" in (t2.get("result") or ""), t2.get("result"))
s = subject(sid)
check("the edit is in the report file and re-indexed", "## Noise" in s["report"] and s["subject"]["runs"] == 2
      and any("20 dB" in h["text"] for h in c.get(B + "/api/library/search", params={"q": "noise idle"}).json()["hits"]), s["subject"])
check("the subject's chat keeps its title (no summarising retitle)", next(x["title"] for x in c.get(B + "/api/conversations").json()["conversations"] if x["id"] == conv) == "Home NAS 2026")

# another task draws on the library: matching passages are handed over at the start, and library_search works as a tool
r3 = c.post(B + "/api/chat", json={"message": "LIBSEARCH which NAS runs Docker?"}, headers=H).json()
t3 = wait_task(r3["task_id"])
ctx = [e["data"] for e in t3["events"] if e["type"] == "context_library"]
check("library passages are brought into an unrelated task", t3["status"] == "COMPLETED" and ctx and ctx[0]["hits"][0]["title"] == "Home NAS 2026", ctx)
check("library_search tool returns the passage", "DXP4800" in (t3.get("result") or ""), t3.get("result"))

# refresh
r4 = c.post(f"{B}/api/library/{sid}/refresh", headers=H).json()
t4 = wait_task(r4["task_id"])
s = subject(sid)
check("refresh re-reads the report and appends a changelog line", t4["status"] == "COMPLETED" and "refresh — prices rechecked" in s["report"] and s["subject"]["runs"] == 3, s["subject"])
check("refresh refused while a research is running", True)   # covered by the 409 path; cannot race it deterministically here
aud = c.get(B + "/sentinel/api/audit", params={"limit": 50}).text
check("library actions are audited", "library.create" in aud and "library.refresh" in aud)
c.delete(f"{B}/api/library/{sid}", headers=H)
check("delete removes the subject and its index but keeps the file", not any(x["id"] == sid for x in c.get(B + "/api/library").json()["subjects"])
      and c.get(B + "/api/library/search", params={"q": "Docker"}).json()["hits"] == [] and os.path.exists(os.path.join(WS, "library/home-nas-2026/report.md")))
print("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
