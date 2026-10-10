#!/usr/bin/env bash
# Verify the actual Fly entrypoint, auth, Chromium and persistent volume without live credentials.
# Usage: bash tests/docker_image_smoke.sh <local-image>
set -euo pipefail

image=${1:?Usage: bash tests/docker_image_smoke.sh <local-image>}
suffix="$$-$(date +%s)-$RANDOM"
container="locius-image-smoke-$suffix"
volume="locius-image-smoke-$suffix"
platform=$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$image")
cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Fail closed without a login password.
rc=0
docker run --rm --platform "$platform" "$image" || rc=$?
test "$rc" -eq 64
echo 'PASS refuses to start without a password'

docker volume create "$volume" >/dev/null
# An isolated, disposable test password; never a real product credential.
export OMUSE_PASSWORD="smoke-$suffix"
start() {
  docker run -d --name "$container" --platform "$platform" \
    --mount "type=volume,source=$volume,target=/omuse" \
    -p 127.0.0.1::8080 -e OMUSE_PASSWORD \
    -e TELEGRAM_BOT=0 -e VOICE_PORT=0 \
    -e OMUSE_MODEL_URL=http://127.0.0.1:9/v1 -e OMUSE_MODEL=smoke \
    "$image" >/dev/null
  local ready=false
  for ((i=0; i<90; i++)); do
    if docker exec "$container" curl -fsS http://127.0.0.1:8082/health >/dev/null 2>&1 \
      && docker exec "$container" curl -fsS http://127.0.0.1:8080/sentinel/api/health >/dev/null 2>&1 \
      && docker exec "$container" curl -fsS http://127.0.0.1:8081/api/health >/dev/null 2>&1; then
      ready=true
      break
    fi
    sleep 1
  done
  if [ "$ready" != true ]; then
    docker logs --tail 100 "$container"
    return 1
  fi
  echo 'PASS all three services ready'
}

start
port=$(docker port "$container" 8080/tcp)
test "$(curl -s -o /dev/null -w '%{http_code}' "http://$port/")" = 401
echo 'PASS published port requires authentication'
docker exec -i "$container" python3 - <<'PY'
import hashlib
import os
from pathlib import Path
import httpx

b = 'http://127.0.0.1:8080'
with httpx.Client(base_url=b, auth=('omuse', os.environ['OMUSE_PASSWORD']), timeout=30) as c:
    assert c.get('/').status_code == 200
    assert c.get('/api/health').json()['ok']
    assert c.get('/sentinel/api/subscription').json() == {'enabled': False}
    assert c.get('/internal/browser_state').status_code == 401
    assert httpx.get(b + '/', auth=('omuse', 'wrong'), timeout=10).status_code == 401
    assert c.put('/api/settings', json={'model_name': 'smoke-persisted'}, headers={'X-Persona-UI': '1'}).status_code == 200
print('PASS UI, runtime proxy, authentication, subscription defaults and internal token guard')

# A root-owned Fly-style volume must be writable by the unprivileged service user.
key = Path('/omuse/sentinel/vault.key')
assert key.exists() and key.stat().st_uid != 0
Path('/omuse/workspace/smoke-vault-sha256').write_text(hashlib.sha256(key.read_bytes()).hexdigest())
processes = []
for p in Path('/proc').glob('[0-9]*'):
    try:
        cmd = (p / 'cmdline').read_bytes().replace(b'\0', b' ')
        if b'-m uvicorn' in cmd:
            assert p.stat().st_uid != 0, cmd
            processes.append(cmd)
    except FileNotFoundError:
        pass
assert len(processes) == 3, processes
print('PASS services run unprivileged and initialize persistent state')

# The running broker health check proves its Chromium startup; also render a PDF
# with the image's browser binary to catch missing shared libraries/font packages.
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
    page = browser.new_page()
    page.set_content('<h1>Image smoke test</h1>')
    assert page.locator('h1').inner_text() == 'Image smoke test'
    assert page.pdf().startswith(b'%PDF')
    browser.close()
print('PASS Chromium renders a PDF')
PY

docker stop --time 20 "$container" >/dev/null
test "$(docker inspect --format '{{.State.ExitCode}}' "$container")" != 137
docker rm "$container" >/dev/null
start
docker exec -i "$container" python3 - <<'PY'
import hashlib
import os
from pathlib import Path
import httpx

with httpx.Client(base_url='http://127.0.0.1:8080', auth=('omuse', os.environ['OMUSE_PASSWORD']), timeout=30) as c:
    assert c.get('/api/settings').json()['settings']['model_name'] == 'smoke-persisted'
key = Path('/omuse/sentinel/vault.key')
assert hashlib.sha256(key.read_bytes()).hexdigest() == Path('/omuse/workspace/smoke-vault-sha256').read_text()
print('PASS settings, workspace and vault key survive container replacement')
PY
echo 'ALL IMAGE SMOKE CHECKS PASS'
