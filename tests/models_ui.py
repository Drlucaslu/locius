"""Settings → Models: "Use my own model" is a toggle; off = the section is closed and the system's model is in force,
on = the section opens with endpoint, API key and LLM required (the browser refuses to save without them); the saved
values come back after a reload, the key only as "saved"; off again closes the section and the system model is back."""
import asyncio, sys
from playwright.async_api import async_playwright

B = "http://127.0.0.1:8080/"
fails = []


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name, "" if cond else info)
    if not cond:
        fails.append(name)


async def main():
    import httpx
    H = {"X-Persona-UI": "1"}
    c = httpx.Client(trust_env=False, timeout=30)
    c.put(B + "api/settings", json={"language": "zh", "ui_language": "zh", "model_override": False}, headers=H)
    sys_url = c.get(B + "api/settings", headers=H).json()["settings"]["model_base_url"]
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1400, "height": 1000}, locale="zh-CN")
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(B + "#settings")
        await pg.wait_for_selector("#models")
        toggle = pg.locator("#models label.toggle", has_text="使用自己的模型").locator("input")
        box = pg.locator("#modelOverride")
        check("toggle off and the own-model section closed", not await toggle.is_checked() and await box.is_hidden())
        check("the system model is named", "fake" in await pg.locator("#systemModel").inner_text(), await pg.locator("#systemModel").inner_text())
        await toggle.click()
        check("toggle on opens the section with 7 fields", await box.is_visible() and await box.locator("input").count() == 7, await box.locator("input").count())
        check("the three required fields are marked", await box.locator(".req").count() == 3)
        save = pg.locator("button", has_text="保存设置")
        await save.click()
        await pg.wait_for_selector(".toast.err")
        t = await pg.locator(".toast.err").last.inner_text()
        check("saving with nothing filled is refused: endpoint first", "接口地址" in t, t)
        check("...and nothing was saved", c.get(B + "api/settings", headers=H).json()["settings"]["model_override"] is False)
        inputs = box.locator("input")
        await inputs.nth(0).fill(sys_url)
        await save.click()
        await pg.wait_for_timeout(300)
        t = await pg.locator(".toast.err").last.inner_text()
        check("then the API key", "API key" in t, t)
        await inputs.nth(1).fill("ui-key-1")
        await save.click()
        await pg.wait_for_timeout(300)
        t = await pg.locator(".toast.err").last.inner_text()
        check("then the LLM model name", "LLM" in t, t)
        await inputs.nth(2).fill("fake")
        await inputs.nth(3).fill("fake")   # planner
        await save.click()
        await pg.wait_for_selector(".toast:not(.err)")
        s = c.get(B + "api/settings", headers=H).json()
        check("saved: own model on, key stored but not returned", s["settings"]["model_override"] is True and s["settings"]["model_api_key_set"]
              and "model_api_key" not in s["settings"] and s["settings"]["planner_model"] == "fake", s["settings"])
        check("the key field is cleared and says saved", await inputs.nth(1).input_value() == "" and "已保存" in (await inputs.nth(1).get_attribute("placeholder") or ""))
        await pg.reload()
        await pg.wait_for_selector("#models")
        toggle = pg.locator("#models label.toggle", has_text="使用自己的模型").locator("input")
        box = pg.locator("#modelOverride"); inputs = box.locator("input")
        check("after a reload the toggle is on and the section open with the values", await toggle.is_checked() and await box.is_visible()
              and await inputs.nth(0).input_value() == sys_url and await inputs.nth(2).input_value() == "fake" and await inputs.nth(3).input_value() == "fake")
        check("the key is never shown", await inputs.nth(1).input_value() == "" and await inputs.nth(1).get_attribute("type") == "password")
        check("the model chip says own model", "自己的模型" in (await pg.locator("#modelChip").get_attribute("title") or ""))
        await toggle.click()
        check("toggle off closes the section", await box.is_hidden())
        await pg.locator("button", has_text="保存设置").click()
        await pg.wait_for_selector(".toast:not(.err)")
        s = c.get(B + "api/settings", headers=H).json()
        check("off: the system model is in force, the own values kept", s["settings"]["model_override"] is False and s["settings"]["planner_model"] == ""
              and s["model_user"]["planner_model"] == "fake" and s["model_user"]["api_key_set"], s)
        await pg.reload()
        await pg.wait_for_selector("#models")
        check("after a reload the section stays closed", await pg.locator("#modelOverride").is_hidden())
        check("no page errors", not errs, errs)
        await b.close()
    c.put(B + "api/settings", json={"model_override": False}, headers=H)
    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    sys.exit(1 if fails else 0)

asyncio.run(main())
