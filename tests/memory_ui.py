"""Memory page (batch 2): domain chips filter the facts, the learned list, the try-it preview, entities."""
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
    c.put(B + "api/settings", json={"language": "zh", "ui_language": "zh"}, headers=H)
    # the page needs some memory to show (this suite used to run after batch2_e2e.py, which seeded it)
    c.post(B + "api/memory", json={"fact": "我身高177，体重76公斤，鞋子42码，运动鞋43码。", "domain": "preference"}, headers=H)
    c.post(B + "api/memory", json={"fact": "shop.test 网站支持访客结账；电话号码填 8 位，不要加 +65。", "domain": "site"}, headers=H)
    c.post(B + "api/memory", json={"fact": "The user prefers business class seats.", "domain": "preference"}, headers=H)
    c.post(B + "api/memory", json={"fact": "Mei collects jazz vinyl records.", "domain": "person", "entity": "Mei"}, headers=H)
    mei = next((e for e in c.get(B + "api/memory", headers=H).json()["entities"] if e["name"] == "Mei"), None)
    if mei:
        c.put(f"{B}api/entities/{mei['id']}", json={"aliases": "梅梅", "relation": "太太"}, headers=H)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1400, "height": 1000}, locale="zh-CN")
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(B + "#memory")
        await pg.wait_for_selector("text=长期记忆")
        chips = await pg.locator("button.chip").all_inner_texts()
        check("domain chips with counts", any(c.startswith("网站习惯") for c in chips) and any(c.startswith("偏好") for c in chips), chips)
        await pg.locator("button.chip", has_text="网站习惯").first.click()
        rows = await pg.locator("table.memtable tbody tr").all_inner_texts()
        check("a chip filters the table to that domain", rows and all("shop.test" in r for r in rows), rows)
        await pg.fill("input[placeholder^='输入一个请求']", "帮我在 shop.test 挑一双跑鞋")
        await pg.click("text=看看 Preview")
        await pg.wait_for_timeout(800)
        txt = await pg.locator(".card", has_text="试一试").inner_text()
        check("try-it shows the size and the shop habit", "43码" in txt and "shop.test" in txt, txt[:600])
        await pg.locator("button.chip", has_text="全部").first.click()
        await pg.screenshot(path="/tmp/claude-0/sc/memory_page.png", full_page=True)
        ent = await pg.locator(".card", has_text="人物、地点").inner_text()
        check("entities card lists Mei with relation", "Mei" in ent and "太太" in ent, ent[:300])
        check("no page errors", not errs, errs)
        await b.close()
    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    sys.exit(1 if fails else 0)

asyncio.run(main())
