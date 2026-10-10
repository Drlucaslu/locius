"""Docker image, end to end with a real model: sign in through the gate, then have the agent open web pages, take a
screenshot (browser_look) and say what is on them. Needs a running container with a vision-capable model:

  OMUSE_URL=http://127.0.0.1:8080 OMUSE_PASSWORD=... python3 tests/docker_browser_e2e.py [screenshot-dir]

Cases: a static page (example.com), a live shop front (amazon.com: find the featured products) and a map
(Google Maps: where does the map open, i.e. where does the container appear to be), plus a password change through the
gate. E2E_CASES=password, =static, =shop or =maps runs some of them. The model endpoint and its key are the container's own (OMUSE_MODEL_URL / OMUSE_MODEL /
OMUSE_MODEL_API_KEY)."""
import os
import re
import sys
import time

import httpx

B = os.environ.get("OMUSE_URL", "http://127.0.0.1:8080").rstrip("/")
AUTH = (os.environ.get("OMUSE_USER", "omuse"), os.environ["OMUSE_PASSWORD"])
CASES = [c for c in os.environ.get("E2E_CASES", "password,static,shop,maps").split(",") if c]
SHOT_DIR = sys.argv[1] if len(sys.argv) > 1 else ""
H = {"X-Persona-UI": "1"}
c = httpx.Client(timeout=120, trust_env=False, auth=AUTH)
fails = []


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name, "" if cond else str(info)[:1200])
    if not cond:
        fails.append(name)


def browse(case: str, host: str, ask: str, budget_s: int) -> tuple[str, str, str]:
    """Run one agent task on https://<host>/; returns (final answer, the vision model's answers, the page's URL)."""
    t0 = time.time()
    msg = f"Open https://{host}/ with browser_navigate. Then call browser_look to take a screenshot of the page. {ask}"
    r = c.post(B + "/api/chat", headers=H, json={"message": msg}).json()
    t = {}
    while time.time() - t0 < budget_s:
        t = c.get(f"{B}/api/tasks/{r['task_id']}").json()
        if t["status"] in ("COMPLETED", "FAILED", "CANCELLED") or t.get("waiting"):
            break
        time.sleep(1)
    calls = [e["data"].get("name") for e in t.get("events", []) if e["type"] == "tool_call"]
    vision = "\n".join(e["data"].get("answer", "") for e in t.get("events", []) if e["type"] == "vision")
    out = t.get("result") or ""
    check(f"{case}: task completes without approvals", t.get("status") == "COMPLETED", (t.get("status"), t.get("error"), t.get("waiting")))
    check(f"{case}: agent opened the page", "browser_navigate" in calls, calls)
    check(f"{case}: agent took a screenshot (browser_look)", "browser_look" in calls and bool(vision), calls)
    shot = c.get(f"{B}/sentinel/api/browser/screenshot", params={"task_id": r["task_id"]})
    check(f"{case}: live-view screenshot is a JPEG", shot.status_code == 200 and shot.content[:3] == b"\xff\xd8\xff", (shot.status_code, len(shot.content)))
    if SHOT_DIR and shot.status_code == 200:
        os.makedirs(SHOT_DIR, exist_ok=True)
        open(os.path.join(SHOT_DIR, f"{case}.jpg"), "wb").write(shot.content)
    st = c.get(B + "/sentinel/api/browser/state").json()
    # this task's own page: the top-level "url" is whichever task the live view shows, which may be another one
    url = next((x.get("url", "") for x in st.get("tasks", []) if x.get("task_id") == r["task_id"]), st.get("url", ""))
    check(f"{case}: browser is on the page, headed", host.removeprefix("www.") in url and st.get("headless") is False, st)
    # the chat list shows a short title summarising the chat, not the truncated question
    title = ""
    for _ in range(30):
        conv = next((x for x in c.get(B + "/api/conversations").json()["conversations"] if x["id"] == r["conversation_id"]), {})
        title = conv.get("title") or ""
        if title and not msg.startswith(title):
            break
        time.sleep(1)
    check(f"{case}: the chat got a summarising title that fits the list", title and not msg.startswith(title) and len(title) <= 40, title)
    print(f"\n--- {case}: agent's answer ({time.time() - t0:.0f}s, tools: {calls}; chat title: {title!r}) ---\n{out}\n")
    return out, vision, url


check("no password, no entry", httpx.get(B + "/", trust_env=False).status_code == 401)
check("UI loads after sign-in", c.get(B + "/").status_code == 200)
tm = c.post(B + "/api/settings/test-model", headers=H).json()
check("model endpoint answers (API key accepted)", tm.get("ok") is True, tm)

if "static" in CASES:
    out, vision, _ = browse("static", "example.com", "Tell me what it shows: the heading, the text and any links.", 300)
    check("static: vision model read the page", "documentation examples" in vision.lower() or "example domain" in vision.lower(), vision)
    check("static: final answer describes the page", "example domain" in out.lower() or "documentation examples" in out.lower(), out)

if "shop" in CASES:
    out, vision, _ = browse("shop", "www.amazon.com", "Then list the featured products and promotions shown on the home page "
                         "(names, prices if shown, and which section they are in).", 600)
    # the home page changes daily, so check the shape of the answer, not its wording
    blocked = re.search(r"captcha|not a robot|enter the characters|sorry, we just need to make sure", vision + out, re.I)
    check("shop: got the real home page (no robot check)", not blocked, blocked and blocked.group(0))
    check("shop: vision model saw a store front", len(vision) > 300 and re.search(r"deal|prime|shop", vision, re.I), vision)
    check("shop: final answer lists several featured items", len(re.findall(r"(?m)^\s*(?:[-*•]|\d+\.|\|)\s*\S", out)) >= 4, out)
    check("shop: final answer names promotions or prices", re.search(r"\$\s?\d|% ?off|deal", out, re.I), out)

if "maps" in CASES:
    out, vision, url = browse("maps", "www.google.com/maps", "Tell me where the map is centred: which city or area it shows, "
                         "and name a few places or labels visible on it.", 420)
    # Google centres the map on the caller's IP location, so the place differs per machine: check that a real map
    # was read, and print where it is
    at = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
    check("maps: the map opened on a location (coordinates in the URL)", at, at)
    check("maps: vision model read place labels off the map", len(vision) > 150, vision)
    check("maps: final answer says where the map is", len(out) > 80 and not re.search(r"consent|before you continue|unusual traffic", out, re.I), out)
    if at:
        print(f"maps: centred on {at.group(1)}, {at.group(2)}\n")

if "password" in CASES:
    # change the login password through the UI's API; the gate must switch over at once and OMUSE_PASSWORD must stop working
    r = c.post(B + "/sentinel/api/password", headers=H, json={"current": AUTH[1], "new": "e2e-temp-password-9"})
    check("password: change accepted", r.status_code == 200, (r.status_code, r.text[:200]))
    check("password: the initial password no longer opens the UI", httpx.get(B + "/", auth=AUTH, trust_env=False).status_code == 401)
    c2 = httpx.Client(timeout=60, trust_env=False, auth=(AUTH[0], "e2e-temp-password-9"))
    check("password: the new one does", c2.get(B + "/").status_code == 200)
    check("password: Settings no longer says 'default'", c2.get(B + "/sentinel/api/password").json().get("default") is False)
    r = c2.post(B + "/sentinel/api/password", headers=H, json={"current": "e2e-temp-password-9", "new": AUTH[1]})
    check("password: changed back for the next run", r.status_code == 200 and c.get(B + "/").status_code == 200, (r.status_code, r.text[:200]))

print("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
