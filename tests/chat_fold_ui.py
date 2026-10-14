"""Chat timeline: while a task runs its card shows the plan; once it is finished the plan folds away under a one-line
head and only the answer is shown. A tap on the head opens the plan again (and stays open across re-renders)."""
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
    c = httpx.Client(trust_env=False, timeout=30)
    c.put(B + "api/settings", json={"language": "zh", "ui_language": "zh"}, headers={"X-Persona-UI": "1"})
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1280, "height": 800})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(B + "#chat")
        await pg.wait_for_selector("#chatInput")
        await pg.click("button.newchat")
        await pg.fill("#chatInput", "你好，折叠测试 fold test")
        await pg.keyboard.press("Enter")
        await pg.wait_for_selector(".msg.assistant .bubble", timeout=60000)
        await pg.wait_for_selector("details.taskfold", timeout=20000)
        fold = pg.locator("details.taskfold").last
        check("the finished task's plan is folded", not await fold.evaluate("d => d.open"))
        check("...only its one-line head shows, with the status and step count", await fold.locator("summary .pill").is_visible()
              and "步" in await fold.locator("summary").inner_text(), await fold.locator("summary").inner_text())
        check("...the plan and the activity are hidden", not await fold.locator("ol.plan").is_visible() and not await fold.locator("details.trace summary").is_visible())
        check("the answer is shown", await pg.locator(".msg.assistant .bubble").last.is_visible())
        await fold.locator("summary").click()
        check("a tap opens the plan", await fold.evaluate("d => d.open") and await fold.locator("ol.plan").is_visible())
        # a re-render of the card (e.g. a task update) keeps it open
        await pg.evaluate("() => { const id = document.querySelector('details.taskfold').closest('.taskcard').id.slice(3); "
                          "document.getElementById('tc-' + id).parentElement.replaceWith(taskCard(S.tasks[id])); }")
        check("...and it stays open when the card re-renders", await pg.locator("details.taskfold").last.evaluate("d => d.open"))
        await pg.reload()
        await pg.wait_for_selector("details.taskfold", timeout=20000)
        check("after a reload it is folded again", not await pg.locator("details.taskfold").last.evaluate("d => d.open"))
        check("no page errors", not errs, errs)
        await b.close()
    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    sys.exit(1 if fails else 0)

asyncio.run(main())
