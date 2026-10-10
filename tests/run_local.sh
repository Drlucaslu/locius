#!/bin/bash
# Start fake LLM, test pages, browser broker, runtime, sentinel locally.
set -e
cd "$(dirname "$0")/.."
T=/tmp/claude-0/persona-test
rm -rf $T; mkdir -p $T/{sdata,data,workspace,bprofile}
export RUNTIME_TOKEN=rt-test BROWSER_TOKEN=bt-test WORKSPACE=$T/workspace
export PYTHONPATH=$PWD
(cd tests/pages && env -u HTTPS_PROXY -u HTTP_PROXY python3 -m http.server 8099 >$T/pages.log 2>&1 &)
TEST_PAGE=http://shop.test:8099/page.html python3 -m uvicorn tests.fake_llm:app --port 8090 >$T/llm.log 2>&1 &
env -u HTTPS_PROXY -u HTTP_PROXY -u https_proxy -u http_proxy BROWSER_PROFILE=$T/bprofile SEARCH_ENGINES=empty=http://shop.test:8094/emptysearch?q=,duckduckgo=http://shop.test:8094/ddg?q= python3 -m uvicorn app.browser.main:app --port 8082 >$T/browser.log 2>&1 &
RUNTIME_DATA=$T/data PERSONA_MODEL_URL=http://127.0.0.1:8090/v1 PERSONA_MODEL=fake python3 -m uvicorn app.runtime.main:app --port 8081 >$T/runtime.log 2>&1 &
python3 -m uvicorn tests.fake_telegram:app --port 8091 >$T/tg.log 2>&1 &
python3 -m uvicorn tests.fake_mcp:app --port 8093 >$T/mcp.log 2>&1 &
python3 -m uvicorn tests.fake_apps:app --port 8094 >$T/apps.log 2>&1 &
python3 -m uvicorn tests.fake_dial:app --port 8096 >$T/dial.log 2>&1 &
env -u HTTPS_PROXY -u HTTP_PROXY -u https_proxy -u http_proxy python3 -m uvicorn tests.fake_voice:app --port 8095 >$T/voice.log 2>&1 &
DIALMCP_URL=http://127.0.0.1:8096/mcp TELNYX_API=http://127.0.0.1:8095 OPENAI_API=http://127.0.0.1:8095 OPENAI_REALTIME_URL=ws://127.0.0.1:8095/v1/realtime VOICE_PORT=8083 VOICE_ALLOW_HTTP=1 NOTION_API=http://127.0.0.1:8094 SLACK_API=http://127.0.0.1:8094/api GOOGLE_AUTH_URL=http://127.0.0.1:8094/g/auth GOOGLE_TOKEN_URL=http://127.0.0.1:8094/g/token GOOGLE_USERINFO_URL=http://127.0.0.1:8094/g/userinfo GCAL_API=http://127.0.0.1:8094/cal TELEGRAM_API=http://127.0.0.1:8091 MARKET_DATA_HOSTS=http://127.0.0.1:8094/yahoo1,http://127.0.0.1:8094/yahoo2 GOOGLE_RELAY_URL=http://127.0.0.1:8094/relay/callback GOOGLE_MANAGED_FILE=$T/google_managed.json ICAL_ALLOW_HTTP=1 OMUSE_PASSWORD=local-test STRIPE_API=http://127.0.0.1:8094/stripe OMUSE_STRIPE_API_KEY=sk_test_fake_omuse OMUSE_STRIPE_CUSTOMER_ID=cus_test123 OMUSE_STRIPE_SUBSCRIPTION_ID=sub_test123 SENTINEL_DATA=$T/sdata python3 -m uvicorn app.sentinel.main:app --port 8080 >$T/sentinel.log 2>&1 &
sleep 6
for p in 8080 8081 8082 8090 8091 8093 8094; do curl -s --noproxy '*' -o /dev/null -w "$p %{http_code}\n" http://127.0.0.1:$p/ ; done
