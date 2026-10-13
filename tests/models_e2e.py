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

# unsaved form values are tested, not the saved ones (own-model values count only with the toggle on)
SYS_URL = c.get(B + "/api/settings", headers=H).json()["settings"]["model_base_url"]
r = c.post(B + "/api/settings/test-models", json={"model_override": True, "model_base_url": SYS_URL, "model_api_key": "k", "model_name": "fake",
                                                  "planner_model": "missing-model", "vision_model": "text-only"}, headers=H).json()
by = {x["kind"]: x for x in r["results"]}
check("a planner model that the endpoint lacks is reported", by["planner"]["model"] == "missing-model" and (not by["planner"]["ok"] or by["planner"].get("reply")), by["planner"])
check("a text-only vision model fails the image request", not by["vision"]["ok"] and "image" in by["vision"]["error"].lower(), by["vision"])
g = c.get(B + "/api/settings").json()
check("saved settings untouched by the test", g["settings"]["planner_model"] == "" and g["settings"]["model_override"] is False and not g["settings"]["model_api_key_set"], g["settings"])
check("extra request parameters are gone from Settings", "extra_body" not in c.get(B + "/api/settings").json()["settings"])

# ---------------------------------------------------------------- Settings → Models → "use my own model"
LLM = "http://127.0.0.1:8090"
g = c.get(B + "/api/settings", headers=H).json()
check("the key never leaves the runtime: only whether one is set", "model_api_key" not in g["settings"] and g["settings"]["model_api_key_set"] is False, g["settings"])
check("the system model names are listed without the endpoint", g["system_model"].get("model_name") == "fake" and "model_base_url" not in g["system_model"], g.get("system_model"))
check("own-model form starts empty", g["model_user"] == {"model_base_url": "", "model_name": "", "planner_model": "", "vision_model": "", "stt_model": "", "image_model": "", "api_key_set": False}, g["model_user"])
sys_url = g["settings"]["model_base_url"]
for body, what in (({"model_override": True}, "nothing filled"),
                   ({"model_override": True, "model_base_url": sys_url, "model_name": "fake"}, "no key"),
                   ({"model_override": True, "model_base_url": sys_url, "model_api_key": "user-key-1"}, "no LLM"),
                   ({"model_override": True, "model_base_url": "router/v1", "model_api_key": "user-key-1", "model_name": "fake"}, "not a URL")):
    r = c.put(B + "/api/settings", json=body, headers=H)
    check(f"own model with {what} is refused", r.status_code == 400 and "(" in r.text, (r.status_code, r.text[:200]))
check("...and nothing was switched on", c.get(B + "/api/settings", headers=H).json()["settings"]["model_override"] is False)
r = c.put(B + "/api/settings", json={"model_override": True, "model_base_url": sys_url + "/", "model_api_key": " user-key-1 ", "model_name": "missing-model",
                                     "planner_model": "fake"}, headers=H)
check("own model saved with the three required fields", r.status_code == 200 and r.json()["settings"]["model_override"] is True
      and r.json()["settings"]["model_name"] == "missing-model" and r.json()["settings"]["model_api_key_set"], r.text[:300])
g = c.get(B + "/api/settings", headers=H).json()
check("the own values are in force, trimmed", g["settings"]["model_base_url"] == sys_url and g["settings"]["model_name"] == "missing-model"
      and g["settings"]["planner_model"] == "fake", g["settings"])
check("the form shows the saved values, the key only as set", g["model_user"]["model_name"] == "missing-model" and g["model_user"]["api_key_set"] is True
      and "model_api_key" not in g["model_user"], g["model_user"])
r = c.post(B + "/api/settings/test-models", json={}, headers=H).json()
by = {x["kind"]: x for x in r["results"]}
check("test-models uses the own model (a stand-in answers while the endpoint lacks it)", by["llm"]["model"] == "missing-model", by["llm"])
check("...with the user's key as the bearer token", c.get(LLM + "/last_auth").json()["authorization"] == "Bearer user-key-1", c.get(LLM + "/last_auth").json())
r = c.put(B + "/api/settings", json={"model_override": True, "model_name": "fake", "model_api_key": ""}, headers=H)
check("an empty key field keeps the saved key", r.status_code == 200 and r.json()["settings"]["model_api_key_set"], r.text[:200])
c.post(B + "/api/settings/test-models", json={}, headers=H)
check("...still sent", c.get(LLM + "/last_auth").json()["authorization"] == "Bearer user-key-1")
r = c.post(B + "/api/settings/test-models", json={"model_override": False}, headers=H).json()
check("the form can test the system model while the toggle is off (unsaved)", {x["kind"]: x for x in r["results"]}["llm"]["model"] == "fake", r)
check("...without the user's key", c.get(LLM + "/last_auth").json()["authorization"] == "")
# audit: the key is never logged
ev = c.get(B + "/sentinel/api/audit", headers=H).json()
ev = ev.get("events") or ev.get("entries") or ev
txt = str(ev)
check("the key is not in the audit log", "user-key-1" not in txt and "(set)" in txt, txt[:300])
r = c.put(B + "/api/settings", json={"model_override": False}, headers=H).json()["settings"]
check("toggle off: back to the system model, the saved values ignored", r["model_override"] is False and r["model_name"] == "fake" and r["planner_model"] == "", r)
g = c.get(B + "/api/settings", headers=H).json()
check("...but kept for next time", g["model_user"]["model_name"] == "fake" and g["model_user"]["planner_model"] == "fake" and g["model_user"]["api_key_set"], g["model_user"])
c.post(B + "/api/settings/test-models", json={}, headers=H)
check("the user's key is not sent to the system endpoint", c.get(LLM + "/last_auth").json()["authorization"] == "")
print("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
