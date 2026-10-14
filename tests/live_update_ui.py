"""Chat page keeps up even when the live event stream is broken (dead / dropped), e.g. after laptop sleep or an
Olares session refresh: a new chat's task card must move past "Planning" and show the approval button by itself."""
import asyncio, sys
from playwright.async_api import async_playwright

URL = "http://127.0.0.1:8080/"
fails = []


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name, "" if cond else info)
    if not cond:
        fails.append(name)


async def card_state(pg):
    return await pg.evaluate("""() => [...document.querySelectorAll('.taskcard')].map(c => ({
        status: (c.querySelector('.pill') || {}).textContent || '', approve: !!c.querySelector('.btn.approve')}))""")


def deny_pending():
    """The previous scenario's approval would pop up on page load and cover the page."""
    import httpx
    c = httpx.Client(timeout=30, trust_env=False)
    for a in c.get(URL + "sentinel/api/approvals?status=pending").json()["approvals"]:
        c.post(f"{URL}sentinel/api/approvals/{a['id']}/resolve", json={"decision": "deny"}, headers={"X-Persona-UI": "1"})


async def scenario(p, name, route_stream):
    deny_pending()
    b = await p.chromium.launch()
    pg = await b.new_page(viewport={"width": 1280, "height": 800})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    if route_stream:
        await pg.route("**/api/stream", route_stream)
    await pg.goto(URL + "#chat")
    await pg.wait_for_selector("#chatInput")
    await pg.click("button.newchat")
    await pg.fill("#chatInput", "BROWSE the shop " + name)
    await pg.keyboard.press("Enter")
    got = None
    verbs = set()
    for _ in range(40):
        await pg.wait_for_timeout(500)
        verbs.update(await pg.evaluate("() => [...document.querySelectorAll('.taskcard .typing.verb')].map(e => e.textContent)"))
        st = await card_state(pg)
        if st and st[-1]["approve"]:
            got = st[-1]
            break
    check(f"{name}: card shows the approval without a reload", got is not None, await card_state(pg))
    words = set(await pg.evaluate("() => VERBS[LANG] || VERBS.en"))
    check(f"{name}: while working the card shows a fun verb from the list", verbs and verbs <= words, verbs)
    a, b2 = await pg.evaluate("() => [pickVerb(), pickVerb()]")
    check(f"{name}: the verb changes", a != b2 and a in words and b2 in words, (a, b2))
    check(f"{name}: no page errors", not errs, errs)
    await b.close()


async def main():
    async with async_playwright() as p:
        await scenario(p, "live stream", None)
        await scenario(p, "stream down", lambda route: route.abort())

        async def silent(route):   # connects, then closes without delivering any event (a reconnect that lost the gap)
            await route.fulfill(status=200, headers={"content-type": "text/event-stream"}, body="retry: 60000\n\n")
        await scenario(p, "stream lost events", silent)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}")
    sys.exit(1 if fails else 0)

asyncio.run(main())
