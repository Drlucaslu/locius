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
    await pg.clock.install()   # to spin the verb (a 3.5 s interval) without waiting for it
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
    verbs, titles, spun = set(), set(), None
    get_verbs = "() => [...document.querySelectorAll('.taskcard .typing.verb')].map(e => [e.textContent, e.title])"
    for _ in range(40):
        await pg.wait_for_timeout(500)
        seen = await pg.evaluate(get_verbs)
        verbs.update(v for v, _t in seen); titles.update(t for _v, t in seen)
        if seen and spun is None:   # 3.5 s later the card shows another verb
            await pg.clock.run_for(3600)
            after = await pg.evaluate(get_verbs)
            spun = (seen[0][0], after[0][0] if after else None)
        st = await card_state(pg)
        if st and st[-1]["approve"]:
            got = st[-1]
            break
    check(f"{name}: card shows the approval without a reload", got is not None, await card_state(pg))
    flat = {"规划中", "执行中", "規劃中", "執行中", "Planning", "Running"}
    check(f"{name}: while working the card shows a fun verb, not the flat state", verbs and all(v and v not in flat for v in verbs), verbs)
    check(f"{name}: ...and the real state in its tooltip", titles and titles <= flat, titles)
    check(f"{name}: the verb changes", spun and spun[1] and spun[0] != spun[1], spun)
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
