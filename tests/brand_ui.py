"""Settings → Interface → Name: the install's name sits next to the logo and in the tab title. It is set in Settings
(saved without a reload, back after one), blank means OMuse, and the API trims and caps it."""
import asyncio, sys
from playwright.async_api import async_playwright

B = "http://127.0.0.1:8080/"
H = {"X-Persona-UI": "1"}
fails = []


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name, "" if cond else info)
    if not cond:
        fails.append(name)


async def main():
    import httpx
    c = httpx.Client(trust_env=False, timeout=30)
    c.put(B + "api/settings", json={"language": "zh", "ui_language": "zh", "instance_name": "OMuse"}, headers=H)
    r = c.put(B + "api/settings", json={"instance_name": "  Jarvis   at\n home  "}, headers=H).json()["settings"]
    check("the API trims the name to one line", r["instance_name"] == "Jarvis at home", r["instance_name"])
    r = c.put(B + "api/settings", json={"instance_name": "x" * 60}, headers=H).json()["settings"]
    check("...and caps it at 40 characters", r["instance_name"] == "x" * 40, len(r["instance_name"]))
    r = c.put(B + "api/settings", json={"instance_name": "   "}, headers=H).json()["settings"]
    check("...blank = OMuse", r["instance_name"] == "OMuse", r["instance_name"])
    c.put(B + "api/settings", json={"instance_name": "Jarvis"}, headers=H)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1280, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(B + "#chat")
        await pg.wait_for_selector("#chatInput")
        await pg.wait_for_function("() => document.querySelector('.brand b').textContent === 'Jarvis'", timeout=10000)
        check("the name sits next to the logo", await pg.locator(".brand b").inner_text() == "Jarvis", await pg.locator(".brand b").inner_text())
        check("...and is the tab title", await pg.title() == "Jarvis", await pg.title())
        await pg.goto(B + "#settings")
        await pg.wait_for_selector("#interface input[aria-label=Name]")
        inp = pg.locator("#interface input[aria-label=Name]")
        check("Settings → Interface shows it", await inp.input_value() == "Jarvis", await inp.input_value())
        await inp.fill("Friday")
        await pg.click("text=保存设置")
        await pg.wait_for_function("() => document.querySelector('.brand b').textContent === 'Friday'", timeout=10000)
        check("saving renames the logo without a reload", await pg.locator(".brand b").inner_text() == "Friday" and await pg.title() == "Friday", await pg.title())
        await pg.reload()
        await pg.wait_for_selector("#interface input[aria-label=Name]")
        check("...and it is back after a reload", await pg.locator(".brand b").inner_text() == "Friday"
              and await pg.locator("#interface input[aria-label=Name]").input_value() == "Friday")
        await pg.locator("#interface input[aria-label=Name]").fill("")
        await pg.click("text=保存设置")
        await pg.wait_for_function("() => document.querySelector('.brand b').textContent === 'OMuse'", timeout=10000)
        check("blank goes back to OMuse, in the field too", await pg.locator("#interface input[aria-label=Name]").input_value() == "OMuse")
        check("no page errors", not errs, errs)
        await b.close()
    c.put(B + "api/settings", json={"instance_name": "OMuse"}, headers=H)
    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    sys.exit(1 if fails else 0)

asyncio.run(main())
