"""The UI's static files through the real stack: every asset URL in the page is stamped, a stamped URL is immutable,
an unstamped one revalidates (304), text is served gzip-compressed when accepted, and nothing loads off-site."""
import re
import sys

import httpx

sys.path.insert(0, ".")
B = "http://127.0.0.1:8080"
c = httpx.Client(timeout=60, trust_env=False)
fails = []


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name, "" if cond else str(info)[:1200])
    if not cond:
        fails.append(name)


html = c.get(B + "/").text
urls = re.findall(r'<(?:link|script)\b[^>]*\b(?:href|src)="([^"]+)"', html)
assets = [u for u in urls if not u.startswith("data:")]
check("the page loads nothing off-site", all(u.startswith("static/") for u in assets), urls)
stamps = {u.split("?v=")[1] for u in assets if "?v=" in u}
check("every asset URL carries the same stamp", len(assets) >= 6 and len(stamps) == 1 and all("?v=" in u for u in assets), assets)
v = stamps.pop()

plain = gz = 0
for u in assets:
    name = u[len("static/"):].split("?")[0]
    r = c.get(f"{B}/static/{name}", params={"v": v}, headers={"Accept-Encoding": "identity"})
    check(f"{name}: stamped URL is immutable", r.status_code == 200 and r.headers["cache-control"] == "public, max-age=31536000, immutable", r.headers)
    plain += len(r.content)
    g = c.get(f"{B}/static/{name}", params={"v": v}, headers={"Accept-Encoding": "gzip"})
    check(f"{name}: gzip when accepted", g.headers.get("content-encoding") == "gzip" and g.headers.get("vary") == "Accept-Encoding"
          and g.content == r.content, dict(g.headers))
    gz += int(g.headers["content-length"])
    etag = r.headers["etag"]
    n = c.get(f"{B}/static/{name}", headers={"Accept-Encoding": "identity", "If-None-Match": etag})
    check(f"{name}: unstamped URL revalidates", n.status_code == 304 and n.headers["cache-control"] == "no-cache", (n.status_code, dict(n.headers)))
check("compressed page shell is under 40% of the plain bytes", gz * 10 < plain * 4, (plain, gz))
print(f"page shell: {plain} bytes plain, {gz} bytes gzip, {len(assets)} files")
check("unknown asset is 404", c.get(B + "/static/nope.js").status_code == 404)
check("stale stamp revalidates", c.get(B + "/static/app.js", params={"v": "deadbeef0000"}).headers["cache-control"] == "no-cache")
check("index itself is no-cache", c.get(B + "/").headers["cache-control"] == "no-cache")

print("\nFAILED:" if fails else "\nALL ASSETS CHECKS PASS", fails or "")
sys.exit(1 if fails else 0)
