"""Every Chinese UI string in app.js must be wrapped in T()/Tf() and have an English translation in i18n.js."""
import json, re, subprocess, sys
sys.path.insert(0, '/tmp/claude-0')
src = open('app/web/app.js', encoding='utf-8').read()
en = json.loads(re.search(r'window\.OMUSE_EN = (\{.*\});', open('app/web/i18n.js', encoding='utf-8').read(), re.S).group(1))
tw = json.loads(re.search(r'window\.OMUSE_TW = (\{.*\});', open('app/web/i18n_tw.js', encoding='utf-8').read(), re.S).group(1))
keys = set()
for m in re.finditer(r"\bT\((['`])((?:\\.|(?!\1).)*)\1\)", src):
    keys.add(m.group(2))
for m in re.finditer(r'\bTf\(("(?:\\.|[^"\\])*")', src):
    keys.add(json.loads(m.group(1)))
missing = sorted(k for k in keys if re.search(r'[一-鿿]', k) and k not in en)
missing_tw = sorted(k for k in keys if re.search(r'[一-鿿]', k) and k not in tw)
stale_tw = sorted(k for k in tw if k not in en)   # the Traditional table mirrors the English one
# CJK literals not wrapped: strip T(...)/Tf(...) strings, comments and regexes, then look for CJK quotes
body = re.sub(r"\bT\((['`])(?:\\.|(?!\1).)*\1\)", "", src)
body = re.sub(r'\bTf\("(?:\\.|[^"\\])*"', "", body)
body = "\n".join(l for l in body.splitlines() if "i18n-ok" not in l)
body = re.sub(r"//[^\n]*", "", body)
unwrapped = [l.strip()[:100] for l in body.splitlines() if re.search(r"['\"`][^'\"`\n]*[一-鿿]", l)
             and 'DAYS' not in l and "'每周" not in l and '每天' not in l and '工作日' not in l]
print(f"{len(keys)} keys, {len(missing)} missing translations, {len(missing_tw)} missing Traditional, {len(stale_tw)} stale Traditional, {len(unwrapped)} unwrapped lines")
for k in missing: print("MISSING", repr(k))
for k in missing_tw: print("MISSING_TW", repr(k))
for k in stale_tw: print("STALE_TW", repr(k))
for l in unwrapped: print("UNWRAPPED", l)
sys.exit(1 if missing or missing_tw or stale_tw or unwrapped else 0)
