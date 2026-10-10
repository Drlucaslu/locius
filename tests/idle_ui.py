"""A hidden tab makes no requests at all (no approvals poll, stream closed), so an idle box can sleep; when the tab is
shown again the stream reconnects and pending approvals that arrived meanwhile show up."""
import asyncio
import sys
import time

import httpx
from playwright.async_api import async_playwright

B = "http://127.0.0.1:8080/"
H = {"X-Persona-UI": "1"}
c = httpx.Client(timeout=30, trust_env=False)
fails = []


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name, "" if cond else str(info)[:800])
    if not cond:
        fails.append(name)


for a in c.get(B + "sentinel/api/approvals?status=pending").json()["approvals"]:
    c.post(f"{B}sentinel/api/approvals/{a['id']}/resolve", json={"decision": "deny"}, headers=H)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1280, "height": 800})
        reqs = []
        pg.on("request", lambda r: reqs.append((time.time(), r.url.replace(B, "/"))))
        await pg.goto(B + "#chat")
        await pg.wait_for_selector("#chatInput")
        await pg.wait_for_timeout(2000)
        polls0 = len([u for t, u in reqs if "approvals?status=pending" in u])   # read on load (seed + bell)
        await pg.wait_for_timeout(10000)   # a visible, idle page: the stream only (no approvals poll every 4 s any more)
        polls = len([u for t, u in reqs if "approvals?status=pending" in u])
        check("visible idle tab: approvals are read on load, then not polled", polls0 <= 2 and polls == polls0, (polls0, polls))
        check("the live stream is open", any("api/stream" in u for _, u in reqs))
        # hide the tab (what a background tab / minimised window reports)
        await pg.evaluate("""() => { Object.defineProperty(document, 'hidden', { get: () => true, configurable: true });
            Object.defineProperty(document, 'visibilityState', { get: () => 'hidden', configurable: true });
            document.dispatchEvent(new Event('visibilitychange')); }""")
        n0 = len(reqs)
        await pg.wait_for_timeout(15000)
        quiet = [u for _, u in reqs[n0:]]
        check("hidden tab: no requests for 15 s (stream closed, nothing polls)", quiet == [], quiet)
        # an approval arrives while hidden
        r = c.post(B + "api/chat", json={"message": "BROWSE the shop idle"}, headers=H).json()   # the fake LLM clicks Submit -> approval
        for _ in range(60):
            if c.get(B + "sentinel/api/approvals?status=pending").json()["approvals"]:
                break
            await asyncio.sleep(0.5)
        pend = c.get(B + "sentinel/api/approvals?status=pending").json()["approvals"]
        check("an approval is pending on the server", len(pend) >= 1, pend)
        quiet = [u for _, u in reqs[n0:]]
        check("still no requests from the hidden tab", quiet == [], quiet)
        # show the tab again: stream reconnects, state is re-read, the approval pops up
        await pg.evaluate("""() => { Object.defineProperty(document, 'hidden', { get: () => false, configurable: true });
            Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true });
            document.dispatchEvent(new Event('visibilitychange')); }""")
        await pg.wait_for_timeout(3000)
        after = [u for _, u in reqs[n0:]]
        check("shown again: the stream reconnects and approvals are re-read", any("api/stream" in u for u in after) and any("approvals?status=pending" in u for u in after), after)
        cnt = await pg.evaluate("document.querySelector('#approvalCount').textContent")
        check("the pending approval shows on the bell", cnt == str(len(pend)), cnt)
        await b.close()
    for a in c.get(B + "sentinel/api/approvals?status=pending").json()["approvals"]:
        c.post(f"{B}sentinel/api/approvals/{a['id']}/resolve", json={"decision": "deny"}, headers=H)


asyncio.run(main())
print("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
