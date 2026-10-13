#!/usr/bin/env python3
"""Build the event catalog inside app/skills/gosim-shenzhen-2026/SKILL.md from the three event sites.

    python3 tools/gosim_catalog.py --fetch            # download the pages into .cache/gosim and rebuild
    python3 tools/gosim_catalog.py --cache DIR        # rebuild from pages downloaded earlier

Sources: https://shenzhen2026.gosim.org/schedule/ (+ every session and speaker page),
https://rustchinaconf.org/schedule (the programme is JSON inside the site's JS bundle) and
https://spotlight.gosim.org/shenzhen2026/. The part of SKILL.md between the catalog markers is replaced; the
hand-written instructions above it are kept. All times are China Standard Time (UTC+8).
"""
from __future__ import annotations

import argparse
import datetime as dt
import html as H
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "app", "skills", "gosim-shenzhen-2026", "SKILL.md")
GOSIM = "https://shenzhen2026.gosim.org"
RCC = "https://rustchinaconf.org"
SPOT = "https://spotlight.gosim.org/shenzhen2026/"
START, END = "<!-- catalog:start -->", "<!-- catalog:end -->"
UA = "Mozilla/5.0 (OMuse catalog builder)"


def get(url: str, path: str) -> str:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        subprocess.run(["curl", "-sL", "-A", UA, "-o", path, url], check=True)
    return open(path, encoding="utf-8", errors="replace").read()


def text(t: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
    t = H.unescape(re.sub(r"<[^>]+>", "\n", t))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", t)).strip()


def gist(s: str, n: int = 170) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    if len(s) <= n:
        return s
    cut = s[:n]
    for sep in (". ", "; ", ", "):
        k = cut.rfind(sep)
        if k > n // 2:
            return cut[:k + (1 if sep == ". " else 0)].rstrip() + ("" if sep == ". " else " …")
    return cut.rsplit(" ", 1)[0] + " …"


def fetch_gosim(cache: str) -> dict:
    os.makedirs(os.path.join(cache, "sessions"), exist_ok=True)
    os.makedirs(os.path.join(cache, "speakers"), exist_ok=True)
    s = get(GOSIM + "/schedule/", os.path.join(cache, "schedule.html"))
    sessions, slugs = [], set()
    for p in re.split(r'(?=<div class="preview-track-panel" data-preview-track-panel=")', s)[1:]:
        slug = re.search(r'data-preview-track-panel="([^"]+)"', p).group(1)
        track = re.search(r"<h2>(.*?)</h2>", p, re.S)
        track = H.unescape(track.group(1)).strip() if track else slug
        room = re.search(r'<p class="preview-program-room">(.*?)</p>', p, re.S)
        room = H.unescape(room.group(1)).strip() if room else ""
        for lst in re.finditer(r'<div class="preview-session-list" data-preview-day-panel="([^"]+)"[^>]*>(.*?)(?=<div class="preview-session-list"|<div class="preview-workshop-notice"|$)', p, re.S):
            day, body = lst.group(1), lst.group(2)
            for card in re.finditer(r'<article class="preview-session-card"[^>]*>(.*?)</article>', body, re.S):
                c = card.group(1)
                href = re.search(r'href="/schedule/([^"]+)/"', c)
                t1 = re.search(r'preview-time-start">([^<]*)', c)
                t2 = re.search(r'preview-time-end">([^<]*)', c)
                title = re.search(r"<h3>(.*?)</h3>", c, re.S)
                sp = [{"slug": a, "name": H.unescape(b).strip(), "role": re.sub(r"\s+", " ", H.unescape(cc)).strip()}
                      for a, b, cc in re.findall(r'href="/speakers/([^"]+)/".*?<strong>(.*?)</strong>\s*<small>(.*?)</small>', c, re.S)]
                for x in sp:
                    slugs.add(x["slug"])
                sessions.append({"track": track, "room": room, "day": day, "start": t1.group(1).strip() if t1 else "",
                                 "end": t2.group(1).strip() if t2 else "",
                                 "title": H.unescape(re.sub(r"<[^>]+>", "", title.group(1))).strip() if title else "",
                                 "slug": href.group(1) if href else "", "speakers": sp})
    idx = get(GOSIM + "/speakers/", os.path.join(cache, "speakers.html"))
    slugs |= set(re.findall(r'href="/speakers/([a-z0-9-]+)/"', idx))

    def session_page(x):
        if not x["slug"]:
            return
        page = get(f"{GOSIM}/schedule/{x['slug']}/", os.path.join(cache, "sessions", x["slug"] + ".html"))
        m = re.search(r"<main.*?</main>", page, re.S)
        t = text(m.group(0) if m else page)
        a = re.search(r"Talk overview\n(.*?)\n(?:Speakers|$)", t, re.S)
        x["abstract"] = a.group(1).strip() if a else ""

    def speaker_page(slug):
        page = get(f"{GOSIM}/speakers/{slug}/", os.path.join(cache, "speakers", slug + ".html"))
        m = re.search(r"<main.*?</main>", page, re.S)
        t = m.group(0) if m else page
        links = [l for l in dict.fromkeys(re.findall(r'href="(https?://[^"]+)"', t)) if "gosim.org" not in l and not re.search(r"\.(png|jpe?g|svg|webp)(\?|$)", l)]
        lines = text(t).split("\n")
        # Previous / <prev> / All Speakers / Next / <next> / Name / title line(s) / bio … / Talks
        try:
            k = lines.index("Next") + 2
        except ValueError:
            k = 0
        name = lines[k] if k < len(lines) else slug
        try:
            end = lines.index("Talks", k)
        except ValueError:
            end = len(lines)
        body = lines[k + 1:end]
        bio = next((l for l in body if len(l) > 60), "")
        role = ", ".join(l for l in body[:3] if len(l) <= 60 and l != bio)
        return slug, {"name": name, "role": role, "bio": bio, "links": links[:4]}

    with ThreadPoolExecutor(8) as ex:
        list(ex.map(session_page, sessions))
        speakers = dict(ex.map(speaker_page, sorted(slugs)))
    for x in sessions:  # the schedule's one-line role (title, org) is the cleanest; prefer it
        for sp in x["speakers"]:
            if sp["slug"] in speakers and sp["role"]:
                speakers[sp["slug"]]["role"] = sp["role"]
    return {"sessions": sessions, "speakers": speakers}


def fetch_rcc(cache: str) -> list:
    page = get(RCC + "/schedule", os.path.join(cache, "rcc_schedule.html"))
    js = re.search(r'src="(/assets/index-[^"]+\.js)"', page).group(1)
    s = get(RCC + js, os.path.join(cache, "rcc_index.js"))
    for m in re.finditer(r"JSON\.parse\(`", s):
        i = m.end(); j = i
        while True:
            j = s.find("`", j)
            if j < 0 or s[j - 1] != "\\":
                break
            j += 1
        try:
            obj = json.loads(s[i:j].replace("\\`", "`").replace("\\\\", "\\"))
        except ValueError:
            continue
        if isinstance(obj, list) and obj and isinstance(obj[0], dict) and "venues" in obj[0]:
            return obj
    raise SystemExit("RustChinaConf programme not found in the bundle")


def fetch_spotlight(cache: str) -> list:
    s = get(SPOT, os.path.join(cache, "spotlight.html"))
    out = []
    cards = re.findall(r'<article class="selection-card selected-project-card".*?</article>', s, re.S)
    for m in (re.search(r"<h3[^>]*>(.*?)</h3>.*?<p[^>]*>(.*?)</p>\s*<a href=\"(https?://[^\"]+)\"", c, re.S) for c in cards):
        if not m:
            continue
        out.append({"name": H.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip(),
                    "blurb": H.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip(), "url": m.group(3)})
    return out


def md(day: str) -> str:
    d = dt.date.fromisoformat(day)
    return d.strftime("%a %b %-d")


def render(g: dict, rcc: list, spot: list, when: str) -> str:
    out = [START, f"_Catalog snapshot {when} from the three sites above; breaks and lunches omitted. Session URL: "
           f"{GOSIM}/schedule/<id>/ · speaker URL: {GOSIM}/speakers/<id>/._", ""]
    out.append("## GOSIM Shenzhen 2026 — sessions by day and track (CST)")
    by = {}
    for x in g["sessions"]:
        if not x["speakers"] and re.search(r"lunch|tea break|break|registration|check-in", x["title"], re.I):
            continue
        by.setdefault((x["day"], x["track"], x["room"]), []).append(x)
    for (day, track, room), xs in sorted(by.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        out.append(f"\n### {md(day)} · {track} · {room}")
        for x in sorted(xs, key=lambda x: x["start"]):
            who = "; ".join(f"{sp['name']} ({sp['role']})" if sp["role"] else sp["name"] for sp in x["speakers"])
            line = f"- {x['start']}–{x['end']} **{x['title']}**"
            if who:
                line += f" — {who}"
            if x.get("abstract"):
                line += f". {gist(x['abstract'], 140)}"
            line += f" `{x['slug']}`"
            out.append(line)
    out.append("\n## GOSIM speakers (name · role · links) — speaker page: /speakers/<id>/")
    for slug, sp in sorted(g["speakers"].items(), key=lambda kv: kv[1]["name"].split()[-1].lower()):
        line = f"- **{sp['name']}** `{slug}`"
        if sp["role"]:
            line += f" · {sp['role']}"
        bio = re.sub(r"^\S+(\s\S+){0,3}\s(is|was)\s", "", sp["bio"])      # "Name is …" → "…"
        if bio and sp["role"].split(",")[0][:20].lower() not in bio.lower():                 # only when it adds to the role line
            line += f" · {gist(bio[0].upper() + bio[1:], 120)}"
        if sp["links"]:
            line += " · " + " ".join(sp["links"])
        out.append(line)
    out.append("\n## RustChinaConf 2026 (co-located; Oct 15 workshops, Oct 16–17 afternoons; all CST)")
    for d in rcc:
        for v in d["venues"]:
            for t in v["tracks"]:
                out.append(f"\n### {md(d['date'])} · RustChinaConf {t['name']} · {v['name']}")
                for x in t["sessions"]:
                    if x.get("kind") in ("break", "meal", "transition", "networking", "registration"):
                        continue
                    talks = x.get("talks") or [{"title": x["title"], "description": x.get("details", ""), "speakers": []}]
                    for tk in talks:
                        who = "; ".join(f"{sp['name']} ({sp.get('jobTitle') or sp.get('organization') or ''})".replace(" ()", "") for sp in tk.get("speakers", []))
                        line = f"- {x['start']}–{x['end']} **{tk['title']}**"
                        if who:
                            line += f" — {who}"
                        if tk.get("description"):
                            line += f". {gist(tk['description'], 140)}"
                        out.append(line)
    out.append(f"\n## Spotlight Shenzhen 2026 — {len(spot)} selected AI-native product projects (booths both days + a main-stage showcase slot)")
    for i, p in enumerate(spot, 1):
        out.append(f"- {i:02d} **{p['name']}** — {p['blurb']} {p['url']}")
    out.append(END)
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="download into .cache/gosim (default cache dir)")
    ap.add_argument("--cache", default=os.path.join(ROOT, ".cache", "gosim"))
    a = ap.parse_args()
    os.makedirs(a.cache, exist_ok=True)
    g = fetch_gosim(a.cache)
    rcc = fetch_rcc(a.cache)
    spot = fetch_spotlight(a.cache)
    body = render(g, rcc, spot, dt.date.today().isoformat())
    skill = open(SKILL, encoding="utf-8").read()
    i, j = skill.index(START), skill.index(END) + len(END)
    open(SKILL, "w", encoding="utf-8").write(skill[:i] + body + skill[j:])
    n = sum(1 for x in g["sessions"] if x["speakers"])
    print(f"GOSIM: {n} talks, {len(g['speakers'])} speakers; RustChinaConf: {sum(len(t['sessions']) for d in rcc for v in d['venues'] for t in v['tracks'])} slots; "
          f"Spotlight: {len(spot)} projects; SKILL.md {os.path.getsize(SKILL)} bytes")


if __name__ == "__main__":
    main()
