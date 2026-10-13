"""0.2.10: shopping on a long page (the 2026-09-29 Amazon run) — browser_find / browser_look (vision) / scroll,
and "Add to Cart" works without an approval while "Buy Now" still needs one."""
import json
import sys
import time

import httpx

B = "http://127.0.0.1:8080"
H = {"X-Persona-UI": "1"}
c = httpx.Client(timeout=90, trust_env=False)
fails = []


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name, "" if cond else str(info)[:1200])
    if not cond:
        fails.append(name)


def run(msg, timeout=120):
    tid = c.post(B + "/api/chat", json={"message": msg}, headers=H).json()["task_id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        t = c.get(f"{B}/api/tasks/{tid}").json()
        if t["status"] in ("COMPLETED", "FAILED", "CANCELLED", "WAITING_APPROVAL"):
            return t
        time.sleep(0.5)
    return t


def results(t, name):
    return [e["data"] for e in t["events"] if e["type"] == "tool_result" and e["data"]["name"] == name]


c.put(B + "/api/settings", json={"language": "en"}, headers=H)

# ---------------------------------------------------------------- the whole add-to-cart run
t = run("SHOPCART open Amazon, search for an iPhone 17 Pro Max case, pick a nice one and add it to the cart. Don't check out.")
check("task completes without waiting for an approval", t["status"] == "COMPLETED", t["status"] + " " + json.dumps(
    [e for e in t["events"] if e["type"] == "waiting"], ensure_ascii=False)[:600])
nav = results(t, "browser_navigate")
check("the first snapshot is cut off in the header (the original problem)",
      nav and "Aurora Glitter" not in nav[0]["preview"], nav[:1])
calls = [e["data"]["name"] for e in t["events"] if e["type"] == "tool_call"]
check("the agent never re-opens the same URL", calls.count("browser_navigate") == 1, calls)
vis = [e["data"] for e in t["events"] if e["type"] == "vision"]
check("browser_look ran the vision model twice", len(vis) == 2, vis)
if vis:
    m = [int(x) for x in __import__("re").findall(r"RED=(\d+)", vis[0]["answer"])]
    check("the screenshot sent to the vision model is a real image with red set-of-marks boxes", m and m[0] > 100, vis[0])
    check("labels were drawn on the page", vis[0]["marks"] > 5, vis[0])
    check("vision can see the products and names the link ref", "Aurora Glitter Case" in vis[0]["answer"] and "click [e" in vis[0]["answer"], vis[0])
fnd = results(t, "browser_find")
check("browser_find locates the product and returns its price as context",
      fnd and "Aurora Glitter Case" in fnd[0]["preview"] and "S$21.90" in fnd[0]["preview"], fnd[:1])
check("browser_find finds the Add to Cart button on the product page",
      len(fnd) > 1 and "add to cart, shift, alt, k" in fnd[1]["preview"].lower(), fnd[1:2])
clicks = results(t, "browser_click")
check("clicked into the chosen product", clicks and "product.html?id=3" in clicks[0]["preview"], clicks[:1])
check("Add to Cart clicked without approval, cart updated",
      len(clicks) > 1 and clicks[1]["ok"] and "1 items in cart" in clicks[1]["preview"], clicks[1:2])
check("the final look confirms the cart", len(vis) == 2 and "1 items in cart" in vis[1]["answer"] and "Added to Cart" in vis[1]["answer"], vis[1:])
check("no approval was created for Add to Cart", not any(e["type"] == "waiting" for e in t["events"]))

# ---------------------------------------------------------------- scroll shows the next part of the page
t = run("SHOPSCROLL")
sc = results(t, "browser_scroll")
check("browser_scroll returns the region around the new position (not the header again)",
      sc and "around the current scroll position" in sc[0]["preview"] and "Case for iPhone 17 Pro Max" in sc[0]["preview"]
      and "Department number" not in sc[0]["preview"], sc[:1])

# ---------------------------------------------------------------- the approval rule itself
from app.sentinel import guard  # noqa: E402
check("Add to Cart (an <input type=submit> on Amazon) is a normal click", not guard.click_is_risky("button", "Add to Cart", "submit"))
check("...also with Amazon's shortcut suffix", not guard.click_is_risky("button", "Add to cart, shift, Alt, K", "submit"))
check("Buy Now still needs approval", guard.click_is_risky("button", "Buy Now", "submit"))
check("going to checkout is navigation (0.2.65); placing the order still needs approval",
      not guard.click_is_risky("link", "Proceed to checkout", "") and guard.click_is_risky("button", "Place order", "submit"))

# ---------------------------------------------------------------- the configured vision model can't take images
sys_url = c.get(B + "/api/settings", headers=H).json()["settings"]["model_base_url"]
c.put(B + "/api/settings", json={"model_override": True, "model_base_url": sys_url, "model_api_key": "k", "model_name": "fake", "vision_model": "text-only"}, headers=H)
t = run("SHOPCART open Amazon and add an iPhone case")
looks = results(t, "browser_look")
check("without a vision model browser_look fails cleanly with a hint", looks and not looks[0]["ok"] and "Vision model" in looks[0]["preview"], looks[:1])
c.put(B + "/api/settings", json={"model_override": False, "language": "zh"}, headers=H)

print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
sys.exit(1 if fails else 0)
