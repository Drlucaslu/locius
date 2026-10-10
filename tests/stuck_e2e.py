"""0.2.22: an agent stuck on one source changes strategy instead of looping (the 2026-10-02 HSBC run: one Google Finance
link opened 70 times, 22 re-plans). Copies of a call in one turn are skipped, a host that keeps failing is blocked, and a
task that is still stuck after a nudge and a re-plan stops and answers with what it has."""
import sys
import time

import httpx

B = "http://127.0.0.1:8080"
H = {"X-Persona-UI": "1"}
c = httpx.Client(timeout=60, trust_env=False)
fails = []


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name, "" if cond else str(info)[:900])
    if not cond:
        fails.append(name)


def run(goal, timeout=120):
    r = c.post(B + "/api/chat", json={"message": goal}, headers=H)
    r.raise_for_status()
    tid = r.json()["task_id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        t = c.get(f"{B}/api/tasks/{tid}").json()
        if t["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
            return t
        time.sleep(0.5)
    return t


s0 = c.get(B + "/api/settings", headers=H).json()["settings"]
c.put(B + "/api/settings", json={"max_steps": 40}, headers=H).raise_for_status()

# ---------------------------------------------------------------- 1. the HSBC loop
t = run("STUCKLOOP 做一下 HSBC 过去 5 年的走势")
ev = t["events"]
navs = [e["data"] for e in ev if e["type"] == "tool_call" and e["data"]["name"] == "browser_navigate"]
res = [e["data"] for e in ev if e["type"] == "tool_result" and e["data"]["name"] == "browser_navigate"]
ran = [r for r in res if r.get("ok") and not r.get("skipped")]
skipped = [r for r in res if r.get("skipped")]
replans = [e for e in ev if e["type"] == "replanning"]
gave = [e for e in ev if e["type"] == "gave_up"]
thinking = sum(1 for e in ev if e["type"] == "thinking")
check("stops on its own instead of looping to the step limit", t["status"] == "FAILED" and thinking <= 8,
      (t["status"], t.get("error"), thinking))
check("failure reason says it stopped retrying", "停止重试" in (t.get("error") or ""), t.get("error"))
check("the page itself was opened once", len(ran) == 1, [r.get("preview", "")[:80] for r in res])
check("copies of a call in the same turn are skipped, not run", len(skipped) >= 4 and "Skipped: identical" in skipped[0]["preview"],
      [r.get("preview", "")[:80] for r in skipped][:3])
check("at most one re-plan, and it is told the dead end", len(replans) == 1 and "shop.test" in replans[0]["data"].get("dead_ends", ""),
      [e["data"] for e in replans])
check("gave_up event recorded", len(gave) == 1, gave)
check("final answer written without tools, told to stop", "STUCK SUMMARY" in (t.get("result") or "") and "True" in (t.get("result") or ""),
      t.get("result"))
check("far fewer calls than the 74 of the real run", len(navs) <= 15, len(navs))

# ---------------------------------------------------------------- 2. a source that keeps failing -> switch site
t = run("SWITCHSRC 找 HSBC 的历史股价")
ev = t["events"]
res = [e["data"] for e in ev if e["type"] == "tool_result" and e["data"]["name"] == "browser_navigate"]
check("switching source finishes the task", t["status"] == "COMPLETED", (t["status"], t.get("error")))
check("first three failures on the bad host really ran", all(not r.get("ok") for r in res[:3]) and len(res) >= 5,
      [r.get("preview", "")[:80] for r in res])
check("4th try on the same host is blocked with a switch-source message",
      "nosuch.test" in res[3]["preview"] and "已经失败或被拦截 3 次" in res[3]["preview"] and "different website" in res[3]["preview"],
      res[3]["preview"][:300] if len(res) > 3 else res)
check("the other site then works", res[4].get("ok") is True, res[4] if len(res) > 4 else res)
check("the agent's instructions list the dead end", "dead_ends_in_prompt=True" in (t.get("result") or ""), t.get("result"))
check("no give-up when the switch made progress", not any(e["type"] == "gave_up" for e in ev))

# ---------------------------------------------------------------- 3. prompt-cache friendliness (0.2.23)
calls = httpx.get("http://127.0.0.1:8090/calls_for", params={"marker": "SWITCHSRC"}, timeout=10).json()
calls = [x for x in calls if not str(x.get("system", "")).startswith("You name conversations")]   # the chat-title call is not a step
systems = {x["system"] for x in calls}
check("system prompt identical on every step (model server can reuse its cache)", len(calls) >= 4 and len(systems) == 1,
      (len(calls), len(systems)))
check("live status (time, plan, dead ends) comes last, not in the system prompt",
      all(x["last"].startswith(("（系统）当前状态", "(System) Status")) for x in calls[:-1])
      and "Dead ends" not in calls[0]["system"] and any("nosuch.test" in x["last"] for x in calls), [x["last"][:120] for x in calls])
# ---------------------------------------------------------------- 4. time budget (0.2.23)
c.put(B + "/api/settings", json={"max_minutes": 0.5}, headers=H).raise_for_status()
t0 = time.time()
t = run("SLOWTASK 查一下很多网页")
took = time.time() - t0
check("time budget ends a slow task with an answer", t["status"] == "FAILED" and "用时上限" in (t.get("error") or "")
      and "SLOW SUMMARY" in (t.get("result") or ""), (t["status"], t.get("error"), t.get("result")))
check("wrap-up note given before the limit", "wrap-up note seen: True" in (t.get("result") or ""), t.get("result"))
check("stopped near the limit", took < 60, took)
c.put(B + "/api/settings", json={"max_minutes": s0.get("max_minutes", 20)}, headers=H)
# ---------------------------------------------------------------- 4b. re-making the same file (0.2.23)
c.put(B + "/api/settings", json={"max_steps": 40}, headers=H).raise_for_status()
t = run("REMAKEXLSX 香港行程导出 Excel")
res = [e["data"] for e in t["events"] if e["type"] == "tool_result" and e["data"]["name"] == "make_xlsx"]
check("2nd remake gets a 'stop redoing' note", len(res) >= 2 and "Made 2 times" in res[1]["preview"], [r["preview"][:160] for r in res[:2]])
check("5th remake of the same file is refused", len(res) == 6 and all(r["ok"] for r in res[:4]) and not res[4]["ok"]
      and "already made 4 times" in res[4]["preview"], [(r["ok"], r["preview"][:80]) for r in res])
# ---------------------------------------------------------------- 5. tool-call markup never becomes the answer (0.2.23)
c.put(B + "/api/settings", json={"max_steps": 3}, headers=H).raise_for_status()
t = run("MARKUPFINAL 查一下特斯拉的财报")
check("raw <tool_call> text in a final answer is dropped and the model is asked again",
      (t.get("result") or "").startswith("MARKUP FIXED") and "<tool_call>" not in (t.get("result") or ""), t.get("result"))
c.put(B + "/api/settings", json={"max_steps": s0.get("max_steps", 30)}, headers=H)
print("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
