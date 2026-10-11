"""Settings → Models → "Test models": one standard request per model (LLM, planner, vision, speech-to-text) and a
reachability check for the image model, each reported on its own line; the form's unsaved values can be tested."""
import sys

import httpx

B = "http://127.0.0.1:8080"
H = {"X-Persona-UI": "1"}
c = httpx.Client(timeout=120, trust_env=False)
fails = []


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name, "" if cond else str(info)[:1200])
    if not cond:
        fails.append(name)


r = c.post(B + "/api/settings/test-models", json={}, headers=H).json()
by = {x["kind"]: x for x in r["results"]}
check("every model kind is reported once", [x["kind"] for x in r["results"]] == ["llm", "planner", "vision", "stt", "image"], r)
check("LLM: a standard chat request succeeds", by["llm"]["ok"] and by["llm"]["model"] == "fake" and by["llm"].get("reply"), by["llm"])
check("planner: empty = same as the LLM", by["planner"]["ok"] and by["planner"].get("same_as") == "llm", by["planner"])
check("vision: a standard image request succeeds (falls back to the LLM)", by["vision"]["ok"] and by["vision"]["model"] == "fake", by["vision"])
check("speech-to-text: the fake endpoint has none, said plainly", not by["stt"]["ok"] and "speech-to-text" in by["stt"]["error"], by["stt"])
check("image: no image model on the fake endpoint, said plainly", not by["image"]["ok"] and "image" in by["image"]["error"].lower(), by["image"])

# unsaved form values are tested, not the saved ones
r = c.post(B + "/api/settings/test-models", json={"planner_model": "missing-model", "vision_model": "text-only"}, headers=H).json()
by = {x["kind"]: x for x in r["results"]}
check("a planner model that the endpoint lacks is reported", by["planner"]["model"] == "missing-model" and (not by["planner"]["ok"] or by["planner"].get("reply")), by["planner"])
check("a text-only vision model fails the image request", not by["vision"]["ok"] and "image" in by["vision"]["error"].lower(), by["vision"])
check("saved settings untouched by the test", c.get(B + "/api/settings").json()["settings"]["planner_model"] == "")
check("extra request parameters are gone from Settings", "extra_body" not in c.get(B + "/api/settings").json()["settings"])
print("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
