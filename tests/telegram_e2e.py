"""End-to-end: two-way Telegram control against the local stack + fake Telegram API (tests/run_local.sh)."""
import sys, time, httpx
B, TG = "http://127.0.0.1:8080", "http://127.0.0.1:8091"
H = {"X-Persona-UI": "1"}
c = httpx.Client(timeout=60, trust_env=False)
fails = []
def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name, "" if cond else str(info)[:400]); (None if cond else fails.append(name))
def log(): return c.get(TG + "/_log").json()
def texts(): return [m["text"] for m in log()["sent"]]
def say(text, chat=555):
    c.post(TG + "/_push", json={"message": {"message_id": 1, "chat": {"id": chat, "type": "private", "first_name": "Lucas"}, "text": text}})
def wait_for(pred, timeout=40):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred(): return True
        time.sleep(0.5)
    return False

# chat id detection + configure
say("/start")
d = c.post(B + "/sentinel/api/connections/telegram/detect", json={"bot_token": "123:ABC"}, headers=H).json()
check("detect chat id from /start", d.get("chats") and d["chats"][0]["chat_id"] == "555", d)
r = c.post(B + "/sentinel/api/connections/telegram/credential", json={"bot_token": "123:ABC", "chat_id": "555"}, headers=H)
check("telegram credential saved + welcome sent", r.status_code == 200 and any("已连接 Telegram" in t for t in texts()), r.text)
check("/start answered with help", wait_for(lambda: any("/new" in t and "/tasks" in t for t in texts())), texts()[-3:])
st = c.get(B + "/sentinel/api/telegram/status").json()
check("bot polling", st.get("running") and st.get("configured"), st)

n_tasks = len(c.get(B + "/api/tasks").json()["tasks"])
say("SEND hi from a stranger", chat=999)
time.sleep(4)
check("stranger ignored (no task)", len(c.get(B + "/api/tasks").json()["tasks"]) == n_tasks)

say("你好")
check("plain message -> task -> result sent back", wait_for(lambda: any("这是一个普通回答" in t for t in texts())), texts()[-4:])
check("progress message edited", len(log()["edits"]) >= 1)
convs = c.get(B + "/api/conversations").json()["conversations"]
check("telegram conversation visible in web UI", any("你好" in x["title"] for x in convs))   # titled after the chat since 0.2.77

say("/new")  # fresh conversation so the fake LLM sees BROWSE as the goal
time.sleep(2)
say("打开购物网站帮我下单 BROWSE")
ok = wait_for(lambda: any(m.get("reply_markup") and "ap:" in str(m["reply_markup"]) for m in log()["sent"]), 60)
check("approval pushed with inline buttons", ok, texts()[-3:])
appr = [m for m in log()["sent"] if m.get("reply_markup") and "ap:" in str(m["reply_markup"])]
if appr:
    m = appr[-1]
    cb = m["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    c.post(TG + "/_push", json={"callback_query": {"id": "cb1", "data": cb, "message": {"message_id": m["message_id"], "chat": {"id": 555}, "text": m["text"]}}})
    check("callback answered", wait_for(lambda: any(a.get("callback_query_id") == "cb1" for a in log()["answers"])), log()["answers"])
    aid = cb.split(":")[1]
    ap = [a for a in c.get(B + "/sentinel/api/approvals").json()["approvals"] if a["id"] == aid]
    check("approval resolved via telegram", ap and ap[0]["status"] == "approved", ap and ap[0]["status"])
    ev = c.get(B + "/sentinel/api/audit?limit=50").json()["events"]
    check("audit records via=telegram", any(e["action"] == "approval.approve" and '"via": "telegram"' in str(e.get("detail")) or
                                            (e["action"] == "approval.approve" and (e.get("detail") or {}).get("via") == "telegram") for e in ev))
    # a second click (e.g. from the web at the same time) must not execute twice
    c.post(TG + "/_push", json={"callback_query": {"id": "cb2", "data": cb, "message": {"message_id": m["message_id"], "chat": {"id": 555}, "text": m["text"]}}})
    check("double approve rejected", wait_for(lambda: any(a.get("callback_query_id") == "cb2" and "already" in a.get("text", "") for a in log()["answers"])), log()["answers"][-1:])

say("/tasks")
check("/tasks lists tasks", wait_for(lambda: any("最近任务" in t for t in texts())))
say("/new")
check("/new resets conversation", wait_for(lambda: any("新对话" in t for t in texts())))
say("/stop")
check("/stop answered", wait_for(lambda: any("停止" in t or "没有正在执行" in t for t in texts())))
print(f"\n{len(fails)} failures", fails)
sys.exit(1 if fails else 0)
