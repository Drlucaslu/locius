#!/bin/bash
# Run the local e2e suites (integration.py, *_e2e.py, *_ui.py, ...) inside a container of the Docker image, so they
# need nothing on the host but Docker. Each suite gets a freshly started stack (tests/run_local.sh: fake LLM + all
# services), because several suites expect a fresh install.
#   bash tests/run_in_docker.sh                 # every suite (about 15 minutes)
#   bash tests/run_in_docker.sh e2e_027 mcp_e2e # only these
# OMUSE_IMAGE picks the image (default: omuse, built from the Dockerfile when missing). Exit code 1 if a suite fails.
# OMUSE_TEST_OFFLINE=1 skips the apt/pip step inside the container (no network: the mail suites then have no IMAP server).
# docker_browser_e2e.py is not part of this: it needs a real model (see its docstring).
set -u
if [ "${1:-}" != "--inside" ]; then
  cd "$(dirname "$0")/.."
  IMAGE="${OMUSE_IMAGE:-omuse}"
  docker image inspect "$IMAGE" >/dev/null 2>&1 || docker build -t "$IMAGE" . || exit 1
  # root: apt installs Dovecot. Empty OMUSE_MODEL*: the image defaults would override the stack's fake model.
  # shop.test / opentable.test: the hostnames the test pages are served under.
  exec docker run --rm --user 0 -e OMUSE_MODEL_URL= -e OMUSE_MODEL= -e VOICE_PORT= -e OMUSE_TEST_OFFLINE \
    --add-host shop.test:127.0.0.1 --add-host opentable.test:127.0.0.1 \
    -v "$PWD":/repo:ro --entrypoint bash "$IMAGE" /repo/tests/run_in_docker.sh --inside "$@"
fi
shift

cp -r /repo /src && cd /src && rm -rf dist
# test-only dependencies (not in requirements.txt): IMAP server for the mail suites, form parsing for the fake services
mkdir -p /tmp/claude-0 /srv/dove/run /srv/dove/mail
if [ -z "${OMUSE_TEST_OFFLINE:-}" ]; then
  (apt-get update -qq && apt-get install -y -qq dovecot-imapd psmisc) >/dev/null 2>&1 || echo "WARNING: could not install dovecot"
  pip install -q --break-system-packages pytest aiosmtpd python-multipart >/dev/null 2>&1 || echo "WARNING: pip install failed"
  cp tests/dovecot.conf /srv/dove/; cp tests/dovecot-oauth2.conf /srv/dove/oauth2.conf
  echo "tester@example.com:{PLAIN}secretpass123" > /srv/dove/users; chown -R nobody:nogroup /srv/dove/mail
  dovecot -c /srv/dove/dovecot.conf || echo "WARNING: dovecot did not start"
fi
export PYTHONPATH=/src

if [ $# -gt 0 ]; then
  SUITES="$*"
else
  SUITES="integration $(ls tests | grep -E '(_e2e|_ui)\.py$|^e2e_0|^browser_parallel|^popup_takeover|^takeover_burst|^i18n_check' | sed 's/\.py$//' | grep -v docker_browser_e2e)"
fi
failed=""
for f in $SUITES; do
  f="${f%.py}"
  bash tests/stop_local.sh >/dev/null 2>&1; pkill -f "uvicorn|http.server|chrome" >/dev/null 2>&1; sleep 1
  bash tests/run_local.sh > /tmp/up.log 2>&1 < /dev/null
  for i in $(seq 1 20); do
    curl -s -o /dev/null http://127.0.0.1:8082/ && curl -sf -o /dev/null http://127.0.0.1:8080/sentinel/api/health && break
    sleep 1
  done
  t0=$(date +%s)
  timeout 420 python3 "tests/$f.py" > "/tmp/out-$f.log" 2>&1; rc=$?
  echo "SUITE $f rc=$rc $(( $(date +%s) - t0 ))s pass=$(grep -c '^PASS' "/tmp/out-$f.log") fail=$(grep -c '^FAIL' "/tmp/out-$f.log")"
  if [ $rc -ne 0 ]; then
    failed="$failed $f"
    echo "  stack: $(tr '\n' ' ' < /tmp/up.log)"
    grep -E '^FAIL|Error|Traceback' "/tmp/out-$f.log" | head -8 | cut -c1-300 | sed 's/^/  /'
    tail -2 "/tmp/out-$f.log" | cut -c1-300 | sed 's/^/  /'
  fi
done
[ -z "$failed" ] && echo "ALL SUITES PASS" || { echo "FAILED SUITES:$failed"; exit 1; }
