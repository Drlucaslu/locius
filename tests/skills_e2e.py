"""Skills page: every skill is on by default; the user turns some off (they leave the agent's instructions and
load_skill refuses them); a skill is imported from a GitHub link (fake raw server) and can be removed."""
import sys
import time

import httpx

B = "http://127.0.0.1:8080"
H = {"X-Persona-UI": "1"}
c = httpx.Client(timeout=60, trust_env=False)
fails = []


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name, "" if cond else str(info)[:1200])
    if not cond:
        fails.append(name)


def run(msg):
    r = c.post(B + "/api/chat", json={"message": msg}, headers=H).json()
    t0 = time.time()
    while time.time() - t0 < 60:
        t = c.get(f"{B}/api/tasks/{r['task_id']}").json()
        if t["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
            return t.get("result") or ""
        time.sleep(0.5)
    return ""


sk = c.get(B + "/api/skills").json()
names = [s["name"] for s in sk["skills"]]
check("built-in skills listed, all enabled by default", len(names) >= 9 and all(s["enabled"] and s["source"] == "builtin" for s in sk["skills"]), sk)
check("no OMUSE_SKILLS in the test stack", sk["env"] == "")
listed = run("SKILLCHECK")
check("the agent's instructions list every enabled skill", listed.startswith("SKILLS=") and set(listed[7:].split(",")) == set(names), (listed, names))

# turn two off
off = ["online-shopping", "phone-call"]
r = c.put(B + "/api/skills", json={"disabled": off}, headers=H).json()
check("selection saved", [s["name"] for s in r["skills"] if not s["enabled"]] == off, r)
listed = run("SKILLCHECK")
check("disabled skills leave the agent's instructions", listed.startswith("SKILLS=") and not set(off) & set(listed[7:].split(",")) and "reply-email" in listed, listed)
out = run("LOADSKILL online-shopping")
check("load_skill refuses a disabled skill", "turned off" in out, out)
out = run("LOADSKILL reply-email")
check("load_skill still works for an enabled one", "LOADED=---" in out and "reply-email" in out, out)

# import from GitHub (the runtime's raw base points at the fake server)
r = c.post(B + "/api/skills/import", json={"url": "https://github.com/acme/skills/tree/main/flight-watch"}, headers=H)
check("a skill is imported from a GitHub folder link", r.status_code == 200 and r.json()["skill"]["name"] == "flight-watch", r.text[:300])
sk = c.get(B + "/api/skills").json()["skills"]
fw = next((s for s in sk if s["name"] == "flight-watch"), None)
check("the imported skill is listed, enabled, with its source link", fw and fw["enabled"] and fw["source"] == "imported" and fw["url"].startswith("https://github.com/acme"), fw)
listed = run("SKILLCHECK")
check("the imported skill reaches the agent", "flight-watch" in listed, listed)
out = run("LOADSKILL flight-watch")
check("and can be loaded", "Flight watch" in out or "flight-watch" in out, out)
r = c.post(B + "/api/skills/import", json={"url": "https://github.com/acme/skills/tree/main/noname"}, headers=H)
check("a SKILL.md without front matter is refused", r.status_code == 400 and "name" in r.text, r.text[:200])
r = c.post(B + "/api/skills/import", json={"url": "https://gitlab.com/acme/skills"}, headers=H)
check("non-GitHub links are refused", r.status_code == 400, r.text[:200])
r = c.post(B + "/api/skills/import", json={"url": "https://github.com/acme/skills/tree/main/missing"}, headers=H)
check("a link without SKILL.md is refused with a hint", r.status_code == 400 and "SKILL.md" in r.text, r.text[:200])
check("built-in skills cannot be deleted", c.delete(B + "/api/skills/reply-email", headers=H).status_code == 404)
check("the imported skill can be removed", c.delete(B + "/api/skills/flight-watch", headers=H).status_code == 200
      and not any(s["name"] == "flight-watch" for s in c.get(B + "/api/skills").json()["skills"]))
aud = c.get(B + "/sentinel/api/audit", params={"limit": 400, "actor": "user"}).text
check("skills changes are audited", "skills.select" in aud and "skills.import" in aud and "skills.delete" in aud)
c.put(B + "/api/skills", json={"disabled": []}, headers=H)
print("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
