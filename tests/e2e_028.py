"""0.2.8 (issue beclab/Olares#4201): the language lives in Settings; English = everything in English.
Run on a FRESH stack (language not chosen yet)."""
import asyncio
import sys
import time

import httpx
from playwright.async_api import async_playwright

B = "http://127.0.0.1:8080"
H = {"X-Persona-UI": "1"}
c = httpx.Client(timeout=90, trust_env=False)
fails = []


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name, "" if cond else str(info)[:800])
    if not cond:
        fails.append(name)


def wait(tid, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        t = c.get(f"{B}/api/tasks/{tid}").json()
        if t["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
            return t
        time.sleep(0.4)
    return t


def langcheck():
    r = c.post(B + "/api/chat", json={"message": "LANGCHECK 你好，检查一下我的邮件"}, headers=H).json()
    t = wait(r["task_id"])
    return t, t.get("result") or ""


check("fresh install: language not chosen yet", c.get(B + "/api/settings").json()["settings"]["language"] == "")


async def ui():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        # an English browser opens OMuse for the first time -> the setting becomes English
        ctx = await b.new_context(locale="en-US", viewport={"width": 1280, "height": 900})
        pg = await ctx.new_page()
        await pg.goto(B + "/#chat")
        await pg.wait_for_timeout(1500)
        check("first visit from an English browser saves language=en",
              c.get(B + "/api/settings").json()["settings"]["language"] == "en")
        check("no language chip in the top bar any more", await pg.locator(".lang-toggle").count() == 0)
        await pg.goto(B + "/#settings")
        await pg.wait_for_timeout(1200)
        sel = pg.locator("select[aria-label=Language]")
        check("Settings has a Language selector set to English", await sel.count() == 1 and await sel.input_value() == "en")
        check("English help text under it", await pg.locator("text=The agent thinks and works in this language").count() == 1)
        await pg.screenshot(path="/tmp/claude-0/settings-lang-en.png", full_page=False)
        # the UI language is its own setting ("" = follow the browser): pick Simplified for the UI and the agent -> saved on
        # the server, page reloads in Chinese
        await sel.select_option("zh")
        await pg.locator("select[aria-label='UI language']").select_option("zh")
        await pg.get_by_role("button", name="Save settings").click()
        await pg.wait_for_timeout(2500)
        check("switching to 中文 in Settings saves language=zh", c.get(B + "/api/settings").json()["settings"]["language"] == "zh")
        check("page reloaded in Chinese", await pg.locator("text=保存设置 Save settings").count() == 1)
        await pg.screenshot(path="/tmp/claude-0/settings-lang-zh.png", full_page=False)
        # another browser (English locale) follows the server setting, not its own locale
        pg2 = await (await b.new_context(locale="en-US")).new_page()
        await pg2.goto(B + "/#settings")
        await pg2.wait_for_timeout(2500)
        check("other devices follow the saved language", await pg2.locator("text=保存设置 Save settings").count() == 1)
        # back to "follow the browser": each browser gets its own language — including Traditional Chinese
        c.put(B + "/api/settings", json={"ui_language": ""}, headers=H)
        pg3 = await (await b.new_context(locale="zh-TW")).new_page()
        await pg3.goto(B + "/#settings")
        await pg3.wait_for_timeout(2500)
        check("a Traditional Chinese browser gets the Traditional UI", await pg3.locator("text=儲存設定 Save settings").count() == 1
              and await pg3.evaluate("document.documentElement.lang") == "zh-TW")
        check("the agent language is untouched by the UI language", c.get(B + "/api/settings").json()["settings"]["language"] == "zh")
        pg4 = await (await b.new_context(locale="en-US")).new_page()
        await pg4.goto(B + "/#settings")
        await pg4.wait_for_timeout(2500)
        check("an English browser gets English while the agent speaks Chinese", await pg4.locator("text=Save settings").count() == 1
              and await pg4.locator("text=保存设置").count() == 0)
        # a chosen UI language wins over the browser, on every device
        c.put(B + "/api/settings", json={"ui_language": "tw"}, headers=H)
        await pg4.reload()
        await pg4.wait_for_timeout(2500)
        check("UI language = Traditional applies to an English browser too", await pg4.locator("text=儲存設定 Save settings").count() == 1)
        await pg4.screenshot(path="/tmp/claude-0/settings-lang-tw.png", full_page=False)
        # theme: Ink / Paper from Settings; "auto" follows the system
        await pg4.locator("select[aria-label=Theme]").select_option("ink")
        await pg4.get_by_role("button", name="儲存設定 Save settings").click()
        await pg4.wait_for_timeout(1500)
        check("Ink theme saved and applied", c.get(B + "/api/settings").json()["settings"]["theme"] == "ink"
              and await pg4.evaluate("document.documentElement.getAttribute('data-theme')") == "ink"
              and await pg4.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(14, 17, 20)")
        await pg4.screenshot(path="/tmp/claude-0/settings-ink.png", full_page=False)
        pg5 = await (await b.new_context(locale="en-US", color_scheme="light")).new_page()
        await pg5.goto(B + "/#chat")
        await pg5.wait_for_timeout(1500)
        check("the theme is per install: another browser also gets Ink", await pg5.evaluate("document.documentElement.getAttribute('data-theme')") == "ink")
        c.put(B + "/api/settings", json={"theme": "paper"}, headers=H)
        await pg5.reload()
        await pg5.wait_for_timeout(1500)
        check("Paper theme: off-white background", await pg5.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(244, 241, 234)")
        pg6 = await (await b.new_context(locale="en-US", color_scheme="dark")).new_page()
        await pg6.goto(B + "/#chat")
        await pg6.wait_for_timeout(1500)
        check("Paper overrides a dark system preference", await pg6.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(244, 241, 234)")
        c.put(B + "/api/settings", json={"theme": "auto", "ui_language": ""}, headers=H)
        await b.close()


asyncio.run(ui())

# ---------------------------------------------------------------- agent in Chinese mode
t, res = langcheck()
check("zh: system prompt starts with the Chinese language rule", "RULE=语言：简体中文" in res, res)
check("zh: plan written under the Chinese rule", (t.get("plan") or {}).get("objective", "").startswith("PLANRULE=语言"), t.get("plan"))

# ---------------------------------------------------------------- agent in English mode (the issue)
c.put(B + "/api/settings", json={"language": "en"}, headers=H)
t, res = langcheck()
check("en: system prompt starts with LANGUAGE: ENGLISH", "RULE=LANGUAGE: ENGLISH" in res, res)
check("en: no Chinese anywhere in the instructions", "SYS_CJK=0 " in res, res)
check("en: no Chinese in any tool description", "TOOLS_CJK=0 " in res, res)
ntools = int(res.split("NTOOLS=")[1]) if "NTOOLS=" in res else 0
check("en: tools still all there", ntools >= 30, ntools)
check("en: planner told to plan in English", (t.get("plan") or {}).get("objective", "").startswith("PLANRULE=LANGUAGE: ENGLISH"), t.get("plan"))
# a Chinese message in English mode still gets the English rule (the setting decides, not the message)
check("en: setting wins over a Chinese request", "SYS_CJK=0" in res)

# the model answers in Chinese anyway (memory says the user likes Chinese) -> OMuse asks once for an English rewrite
r = c.post(B + "/api/chat", json={"message": "ZHANSWER 帮我看看最重要的邮件"}, headers=H).json()
t = wait(r["task_id"])
check("en: a Chinese final answer is rewritten in English", (t.get("result") or "").startswith("Here is the most important email")
      and any(e["type"] == "language_fixed" for e in t["events"]), t.get("result"))
c.put(B + "/api/settings", json={"language": "zh"}, headers=H)
r = c.post(B + "/api/chat", json={"message": "ZHANSWER 帮我看看最重要的邮件"}, headers=H).json()
t = wait(r["task_id"])
check("zh: Chinese answers are left alone", (t.get("result") or "").startswith("最重要的邮件"), t.get("result"))

# 0.2.29: Settings → Reply language = "match": each request is answered in the language it was written in
c.put(B + "/api/settings", json={"language": "zh", "reply_language": "match"}, headers=H)
r = c.post(B + "/api/chat", json={"message": "LANGCHECK please check my inbox for anything important"}, headers=H).json()
t = wait(r["task_id"])
res = t.get("result") or ""
check("match: an English request gets the English rule (UI stays Chinese)", "RULE=LANGUAGE: ENGLISH" in res, res)
check("match: planner too", (t.get("plan") or {}).get("objective", "").startswith("PLANRULE=LANGUAGE: ENGLISH"), t.get("plan"))
t, res = langcheck()
check("match: a Chinese request gets the Chinese rule", "RULE=语言：简体中文" in res, res)
c.put(B + "/api/settings", json={"language": "en", "reply_language": "match"}, headers=H)
t, res = langcheck()
check("match + English UI: a Chinese request is answered in Chinese", "RULE=语言：简体中文" in res, res)
# 0.2.34: English app, but a Chinese request for text to use as written (a poem) runs in Chinese
c.put(B + "/api/settings", json={"language": "en", "reply_language": ""}, headers=H)
r = c.post(B + "/api/chat", json={"message": "LANGCHECK 帮我写一首关于新加坡雨季的现代诗"}, headers=H).json()
t = wait(r["task_id"])
check("en app + Chinese poem request: the task runs in Chinese", "RULE=语言：简体中文" in (t.get("result") or ""), t.get("result"))
t, res = langcheck()
check("en app + ordinary Chinese request: still English", "RULE=LANGUAGE: ENGLISH" in res, res)
c.put(B + "/api/settings", json={"language": "zh", "reply_language": ""}, headers=H)

print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
sys.exit(1 if fails else 0)
