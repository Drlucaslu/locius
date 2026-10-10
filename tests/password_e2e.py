"""Standalone installs (run_local.sh sets OMUSE_PASSWORD=local-test): the chat view reminds the user to change the
initial password, Settings has a Password section, and changing it stores a hashed password that the gate verifies."""
import asyncio
import json
import os
import sys

import httpx
from playwright.async_api import async_playwright

sys.path.insert(0, ".")
B = "http://127.0.0.1:8080"
H = {"X-Persona-UI": "1"}
c = httpx.Client(timeout=60, trust_env=False)
fails = []


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name, "" if cond else str(info)[:1200])
    if not cond:
        fails.append(name)


SDATA = os.environ.get("SENTINEL_DATA", "/tmp/claude-0/persona-test/sdata")
auth_file = os.path.join(SDATA, "auth.json")
if os.path.exists(auth_file):
    os.remove(auth_file)

s = c.get(B + "/sentinel/api/password").json()
check("login exists and still runs on the initial password", s == {"enabled": True, "default": True, "user": "omuse", "min_length": 8}, s)
check("change needs the UI header (no cross-site posts)", c.post(B + "/sentinel/api/password", json={}).status_code == 403)
r = c.post(B + "/sentinel/api/password", json={"current": "wrong", "new": "a-new-password"}, headers=H)
check("wrong current password is refused", r.status_code == 403, (r.status_code, r.text[:200]))
r = c.post(B + "/sentinel/api/password", json={"current": "local-test", "new": "short"}, headers=H)
check("too short is refused", r.status_code == 400 and "8" in r.text, (r.status_code, r.text[:200]))


async def ui():
    async with async_playwright() as pw:
        br = await pw.chromium.launch()
        pg = await br.new_page(locale="en-US")
        await pg.goto(B + "/#chat")
        rem = pg.locator("#pwReminder")
        await rem.wait_for(timeout=15000)
        check("front screen reminds about the initial password", "initial password" in await rem.inner_text())
        await rem.get_by_role("link", name="Change").click()
        card = pg.locator("#password")
        await card.wait_for(timeout=15000)
        check("Settings has a Password section that says it is the initial one", await pg.locator("#pwDefault").count() == 1)
        await card.get_by_label("Current password").fill("local-test")
        await card.get_by_label("New password (at least 8 characters)").fill("my-own-password-1")
        await card.get_by_label("New password again").fill("different")
        await card.get_by_role("button", name="Change password").click()
        check("mismatch is caught in the UI", await pg.locator(".toast").first.inner_text() != "" and not os.path.exists(auth_file))
        await card.get_by_label("New password again").fill("my-own-password-1")
        await card.get_by_role("button", name="Change password").click()
        await pg.wait_for_function("() => [...document.querySelectorAll('.toast')].some(t => /Password changed/.test(t.textContent))", timeout=10000)
        check("the new password is stored hashed", os.path.exists(auth_file) and "my-own-password-1" not in open(auth_file).read()
              and json.load(open(auth_file)).get("algo") == "pbkdf2_sha256", auth_file)
        await br.close()


asyncio.run(ui())
s = c.get(B + "/sentinel/api/password").json()
check("no longer on the default", s.get("default") is False, s)
from app.sentinel import passwd
os.environ["SENTINEL_DATA"] = SDATA; os.environ["OMUSE_PASSWORD"] = "local-test"
check("the gate's check accepts the new password and refuses the initial one",
      passwd.verify("omuse", "my-own-password-1") and not passwd.verify("omuse", "local-test"))
r = c.post(B + "/sentinel/api/password", json={"current": "my-own-password-1", "new": "another-one-2"}, headers=H)
check("changing again needs the new current password", r.status_code == 200 and passwd.verify("omuse", "another-one-2"), r.text[:200])
aud = c.get(B + "/sentinel/api/audit", params={"limit": 30}).text
check("changes are in the audit log, without the passwords", "password.change" in aud and "my-own-password" not in aud and "another-one" not in aud, aud[:300])
os.remove(auth_file)
print("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
