"""Model-call retries: the fake LLM fails the first calls of a task (RETRY429x2: two 429s with Retry-After: 1;
RETRY503x1: one 503), the runtime retries as instructed, the task still completes, and the retries show in the
task's event stream (the UI renders them as "Retrying 1 of N")."""
import sys
import time

import httpx

B = "http://127.0.0.1:8080"
H = {"X-Persona-UI": "1"}
c = httpx.Client(timeout=120, trust_env=False)
fails = []


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name, "" if cond else str(info)[:1200])
    if not cond:
        fails.append(name)


def run(msg, budget):
    t0 = time.time()
    r = c.post(B + "/api/chat", json={"message": msg}, headers=H).json()
    while time.time() - t0 < budget:
        t = c.get(f"{B}/api/tasks/{r['task_id']}").json()
        if t["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
            return t, time.time() - t0
        time.sleep(0.5)
    return t, time.time() - t0


t, took = run("RETRY429x2 你好", 60)
ev = [e["data"] for e in t["events"] if e["type"] == "llm_retry"]
check("429 + Retry-After: the task completes after the retries", t["status"] == "COMPLETED", (t["status"], t.get("error")))
check("two retries, each after the second the server asked for", [(e["attempt"], e["source"], e["wait_s"]) for e in ev] == [(1, "retry-after", 1.0), (2, "retry-after", 1.0)], ev)
check("the reason names the error", all("HTTP 429" in e["reason"] for e in ev), ev)
check("it waited about 2 s, not the 5/10/20 backoff", 1.5 <= took < 12, took)

t, took = run("RETRY503x1 你好", 60)
ev = [e["data"] for e in t["events"] if e["type"] == "llm_retry"]
check("503 without Retry-After: retried after 5 s and completed", t["status"] == "COMPLETED" and [(e["attempt"], e["of"], e["source"], e["wait_s"]) for e in ev] == [(1, 3, "backoff", 5.0)], (t["status"], ev))
check("took at least the 5 s backoff", 5 <= took < 30, took)
print("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
