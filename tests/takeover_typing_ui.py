"""UI test: take over the browser from the Persona web UI, click into a field on the live view and type fast.
The text must arrive complete and in order (regression: "test" arrived as "tste")."""
import asyncio, sys, httpx
from playwright.async_api import async_playwright
B = "http://127.0.0.1:8080/"
TEXT = "lucas.persona+test@example.com"


async def wait_state(pred, timeout=20.0):
    """Poll the browser state until pred(state) holds: the first takeover relaunches Chromium headed and only then opens
    the takeover tab; under load (a full suite run) that takes longer than a fixed pause, which made this suite flaky."""
    import asyncio, time
    t0 = time.time()
    st = {}
    while time.time() - t0 < timeout:
        try:
            st = httpx.get(B + "sentinel/api/browser/state", trust_env=False, timeout=10).json()
            if pred(st):
                return st
        except Exception:
            pass
        await asyncio.sleep(0.3)
    return st
async def main():
    # this test reads the Chinese UI labels; the language is a server setting since 0.2.8
    httpx.put(B + "api/settings", json={"language": "zh"}, headers={"X-Persona-UI": "1"}, trust_env=False)
    async with async_playwright() as p:
        br = await p.chromium.launch(); pg = await br.new_page(viewport={"width": 1400, "height": 900}, locale="zh-CN")
        await pg.goto(B + "#browser"); await pg.wait_for_timeout(1500)
        await pg.click("button.take"); await wait_state(lambda st: st.get("mode") == "user" and not st.get("headless") and st.get("tasks")); await pg.wait_for_timeout(1500)
        await pg.fill(".bbar .url", "http://shop.test:8099/popup_login.html"); await pg.click("text=前往 Go")
        st = await wait_state(lambda st: "popup_login" in (st.get("url") or ""))
        assert "popup_login" in (st.get("url") or ""), f"page did not open: {st}"
        await pg.wait_for_timeout(800)
        img = pg.locator(".screen-wrap img"); bb = await img.bounding_box()
        nat = await img.evaluate("i => [i.naturalWidth, i.naturalHeight]")
        sx, sy = bb["width"] / nat[0], bb["height"] / nat[1]
        await pg.mouse.click(bb["x"] + 250 * sx, bb["y"] + 120 * sy); await pg.wait_for_timeout(600)
        await pg.keyboard.type(TEXT, delay=5)           # fast typing -> many concurrent input events
        await pg.wait_for_timeout(4000)
        await pg.keyboard.press("Backspace"); await pg.keyboard.type("m"); await pg.wait_for_timeout(1500)
        await pg.click("button.release"); await pg.wait_for_timeout(800)
        await br.close()
    c = httpx.Client(trust_env=False, timeout=30)
    st = c.get(B + "sentinel/api/browser/state").json()
    snap = c.post("http://127.0.0.1:8082/agent/snapshot", json={"task_id": st["view_task"]}, headers={"X-Browser-Token": "bt-test"}).json()
    line = [l for l in snap["snapshot"].splitlines() if "Email or phone" in l]
    print(line)
    ok = line and f'value="{TEXT}"' in line[0]
    print("PASS typing arrives complete and in order" if ok else "FAIL typing order/content")
    return bool(ok)


async def first_key_without_click():
    """Typing when the page (not the field) has focus must still reach the remote page, and the hint must show."""
    async with async_playwright() as p:
        br = await p.chromium.launch(); pg = await br.new_page(viewport={"width": 1400, "height": 900}, locale="zh-CN")
        sent = []
        pg.on("request", lambda r: sent.append(r.post_data) if "browser/input" in r.url else None)
        await pg.goto(B + "#browser"); await pg.wait_for_timeout(1500)
        await pg.click("button.take"); await wait_state(lambda st: st.get("mode") == "user" and not st.get("headless") and st.get("tasks")); await pg.wait_for_timeout(1500)
        await pg.wait_for_timeout(800)
        hint = await pg.locator(".kbd-hint").text_content()
        img = pg.locator(".screen-wrap img"); bb = await img.bounding_box()
        nat = await img.evaluate("i => [i.naturalWidth, i.naturalHeight]")
        sx, sy = bb["width"] / nat[0], bb["height"] / nat[1]
        await pg.mouse.click(bb["x"] + 250 * sx, bb["y"] + 120 * sy); await pg.wait_for_timeout(500)
        hint2 = await pg.locator(".kbd-hint").text_content()
        await pg.keyboard.press("Control+a"); await pg.keyboard.press("Backspace")
        await pg.evaluate("document.activeElement.blur()")   # focus lost (e.g. user clicked elsewhere)
        await pg.wait_for_timeout(300)
        hint3 = await pg.locator(".kbd-hint").text_content()
        await pg.keyboard.type("abc", delay=30); await pg.wait_for_timeout(2500)
        print("sent:", sent)
        await pg.click("button.release"); await pg.wait_for_timeout(800)
        await br.close()
    c = httpx.Client(trust_env=False, timeout=30)
    st = c.get(B + "sentinel/api/browser/state").json()
    snap = c.post("http://127.0.0.1:8082/agent/snapshot", json={"task_id": st["view_task"]}, headers={"X-Browser-Token": "bt-test"}).json()
    line = [l for l in snap["snapshot"].splitlines() if "Email or phone" in l]
    print(hint, "|", hint2, "|", hint3, "|", line)
    # since 0.2.52 the keyboard is connected as soon as you take over (focus goes to the page right away); the "click a
    # field first" hint shows once focus is lost, and typing then still reaches the page
    ok = "键盘已连接" in hint and "键盘已连接" in hint2 and "先点一下" in hint3 and line and 'value="abc"' in line[0]
    print("PASS select-all/delete + typing without focus" if ok else "FAIL select-all/typing without focus")
    return ok

if __name__ == "__main__":
    a = asyncio.run(main())
    b = asyncio.run(first_key_without_click())
    sys.exit(0 if a and b else 1)
