"""End-to-end scenarios against locally running services (see run_local.sh)."""
import sys, time, httpx

B = "http://127.0.0.1:8080"
H = {"X-Persona-UI": "1"}
c = httpx.Client(timeout=60, trust_env=False)
fails = []

def chat(msg):
    r = c.post(B + "/api/chat", json={"message": msg}, headers=H); r.raise_for_status(); return r.json()["task_id"]

def wait(tid, states, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        t = c.get(f"{B}/api/tasks/{tid}").json()
        if t["status"] in states: return t
        time.sleep(0.5)
    return t

def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name, "" if cond else info)
    if not cond: fails.append(name)

# 1 plain
t = wait(chat("你好"), {"COMPLETED", "FAILED"})
check("plain chat completes", t["status"] == "COMPLETED" and "普通回答" in t["result"] and "<think>" not in t["result"], t)
check("planner produced plan", len(t["plan"].get("steps", [])) == 2, t["plan"])

# 2 browse + risky click -> approval
tid = chat("BROWSE the shop")
t = wait(tid, {"WAITING_APPROVAL", "COMPLETED", "FAILED"})
check("risky click requires approval", t["status"] == "WAITING_APPROVAL", t.get("error") or t["events"][-3:])
nav = [e for e in t["events"] if e["type"] == "tool_result" and e["data"]["name"] == "browser_navigate"]
snap = nav[0]["data"]["preview"] if nav else ""
check("snapshot redacts password value", "secret-should-not-leak" not in snap, snap[:500])
check("snapshot redacts OTP + reset link", "482913" not in snap and "abcdef1234567890" not in snap, snap)
aps = c.get(B + "/sentinel/api/approvals?status=pending").json()["approvals"]
ap = [a for a in aps if a["task_id"] == tid]
check("approval visible to UI", len(ap) == 1, aps)
if ap:
    r = c.post(f"{B}/sentinel/api/approvals/{ap[0]['id']}/resolve", json={"decision": "approve", "scope": "ONCE"}, headers=H).json()
    check("approved action executed", r.get("result", {}).get("status") == "ok", r)
    t = wait(tid, {"COMPLETED", "FAILED"})
    check("task resumes & completes after approval", t["status"] == "COMPLETED" and "submitted" in t["result"].lower() or "Browsed" in t["result"], t["result"][:300])
# approval without UI header is rejected
r = c.post(f"{B}/sentinel/api/approvals/x/resolve", json={"decision": "approve"})
check("CSRF guard (no UI header) rejected", r.status_code == 403, r.status_code)

# 3 password typing denied
t = wait(chat("TYPEPW please"), {"COMPLETED", "FAILED", "WAITING_APPROVAL"})
check("typing into password field is DENIED", "DENIED" in str(t["events"]) and t["status"] == "COMPLETED", t["status"])

# 4 injection -> exfil navigation needs approval
tid = chat("INJECT test: read the blog")
t = wait(tid, {"COMPLETED", "FAILED", "WAITING_APPROVAL"})
check("injection flagged in tool result", "injection_warning" in str(t["events"]), "")
check("exfil navigation after injection needs approval", t["status"] == "WAITING_APPROVAL", t["status"])
ap = [a for a in c.get(B + "/sentinel/api/approvals?status=pending").json()["approvals"] if a["task_id"] == tid]
if ap:
    c.post(f"{B}/sentinel/api/approvals/{ap[0]['id']}/resolve", json={"decision": "deny", "note": "suspicious"}, headers=H)
    t = wait(tid, {"COMPLETED", "FAILED"})
    check("denied result reaches agent", t["status"] == "COMPLETED" and "DENIED" in t["result"], t["result"][:200])

# 5 memory
t = wait(chat("REMEMBER I like quiet hotels"), {"COMPLETED", "FAILED"})
mem = c.get(B + "/api/memory").json()
check("memory_remember saved", any("quiet hotels" in f["fact"] for f in mem["facts"]), mem)
time.sleep(2)
mem = c.get(B + "/api/memory").json()
check("auto memory extraction", any("direct flights" in f["fact"] for f in mem["facts"]), mem["facts"])

# 6 schedule
t = wait(chat("SCHEDULE daily"), {"COMPLETED", "FAILED"})
sch = c.get(B + "/api/schedules").json()["schedules"]
check("schedule created", any(s["spec"] == "0 8 * * *" for s in sch), sch)
if sch:
    r = c.post(f"{B}/api/schedules/{sch[0]['id']}/run", headers=H).json()
    t = wait(r["task_id"], {"COMPLETED", "FAILED"})
    check("schedule run-now completes", t["status"] == "COMPLETED", t["status"])

# 7 takeover
tid = chat("TAKEOVER needed")
t = wait(tid, {"WAITING_EXTERNAL", "COMPLETED", "FAILED"})
check("takeover request pauses task", t["status"] == "WAITING_EXTERNAL", t["status"])
msgs = c.get(B + "/api/conversations/" + t["conv_id"]).json()["messages"]
said = [m for m in msgs if m["role"] == "assistant" and m["task_id"] == tid]
check("the agent says it needs a takeover, with a direct link to this task's browser tab",
      said and "please log in" in said[-1]["content"] and f"#browser/{tid}" in said[-1]["content"], [m["content"][:160] for m in said])
st = c.get(B + "/sentinel/api/browser/state").json()
check("broker shows takeover request", (st.get("requested") or {}).get("task_id") == tid, st)
c.post(B + "/sentinel/api/browser/takeover", json={"task_id": tid}, headers=H)
r = c.post(B + "/sentinel/api/browser/input", json={"type": "navigate", "url": "http://shop.test:8099/page.html"}, headers=H)
check("user can drive during takeover", r.status_code == 200, r.text)
c.post(B + "/sentinel/api/browser/release", json={}, headers=H)
t = wait(tid, {"COMPLETED", "FAILED"})
check("task resumes after hand-back", t["status"] == "COMPLETED" and ("handed control back" in t["result"] or "用户已完成接管" in t["result"]), t["result"][:200])

# 8 xml tool call fallback + file write
t = wait(chat("XMLTOOL write"), {"COMPLETED", "FAILED"})
check("<tool_call> text fallback parsed", t["status"] == "COMPLETED" and "written" in t["result"], t["result"])

# 9 private address blocked
r = c.post(B + "/sentinel/api/browser/takeover", json={}, headers=H)
r = c.post(B + "/sentinel/api/browser/input", json={"type": "navigate", "url": "http://127.0.0.1:8080/"}, headers=H)
check("private address blocked even for user nav", r.status_code == 403, r.status_code)
c.post(B + "/sentinel/api/browser/release", json={}, headers=H)

# 10 audit chain
v = c.get(B + "/sentinel/api/audit/verify").json()
check("audit chain verifies", v["ok"] and v["checked"] > 20, v)
ev = c.get(B + "/sentinel/api/audit?limit=500").json()["events"]
acts = {e["action"] for e in ev}
check("audit has model calls, tool calls, approvals", {"model.executor", "browser_click", "approval.approve"} <= acts, sorted(acts)[:40])
print("\n%d failures" % len(fails), fails)
sys.exit(1 if fails else 0)
