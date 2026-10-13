# Notes for coding agents working on this repo

## Releasing (tag `locius-vX.Y.Z`)

The version shown in the app comes from the release tag: the release workflow
(`.github/workflows/release-image.yml`) passes the tag as the `OMUSE_VERSION`
build argument and `locius-v0.3.1` is shown as `v0.3.1`. Source checkouts and
untagged builds show the literal `VERSION` in `app/common/util.py`.

When asked to release `locius-vX.Y.Z`, do it in this order so that the source
literal, the tagged commit and the image all agree:

1. On `main`, set `VERSION = "X.Y.Z"` in `app/common/util.py`.
2. Commit that change (`Release X.Y.Z`) and push `main`.
3. Tag that commit `locius-vX.Y.Z` and push the tag. The tag push builds, smoke
   tests (including a check that the app reports `X.Y.Z`) and publishes
   `ghcr.io/drlucaslu/locius:locius-vX.Y.Z`.
4. Report the run result and the image digest from the `image-import.json`
   artifact.

Do not move or re-publish an existing release tag; use a new version instead.

## Web UI assets

The page shell depends on nothing but this server: no CDN `<link>` or `<script>`,
no web fonts; `marked` and `DOMPurify` are vendored in `app/web/`. The sentinel
serves `app/web` from memory (`app/sentinel/assets.py`): `index.html` stamps every
asset URL with `?v=<digest>`, a stamped URL is immutable for a year, anything else
is `no-cache` with an ETag, and text assets are gzip-compressed once at load. A
unit test fails on an off-site asset; `tests/assets_e2e.py` checks the headers.

## Model settings

The system's endpoint, key and model names come from the environment
(`OMUSE_MODEL_URL`, `OMUSE_MODEL_API_KEY`, `OMUSE_MODEL`, ...). A user can switch
`model_override` on in Settings → Models and use their own endpoint, key and
models (`app/runtime/store.py`, `effective_model`): the saved `model_*` values
and `model_api_key` count only while the toggle is on, and the endpoint, key and
LLM name are required then. With it off they are ignored, never mixed with the
system's. The API never returns the key, only `model_api_key_set`, and the audit
log gets `(set)`. A test that changes the model must send `model_override: true`
with those three fields and switch it off afterwards (`tests/models_e2e.py`,
`tests/models_ui.py`).

## Login gate (Docker / Fly)

`deploy/docker/gate.py` wraps Sentinel for standalone installs. Browsers sign in
on `/login` and get a signed cookie (`omuse_session`, 180 days, invalid after a
password change; the key is `$SENTINEL_DATA/session.key` on the volume, so
sessions survive restarts). Browser navigations without a session are
redirected to `/login`, browser fetches get `401 {"detail": "login required"}`
(the web app then goes to `/login`), and non-browser clients (no
`Sec-Fetch-Mode`) still get the HTTP Basic challenge. The local e2e stack runs
Sentinel without the gate; the gate is covered by unit tests and
`tests/docker_image_smoke.sh`.

## Pull requests

Open a PR and report it; merge only when the user explicitly says to merge
that PR. Never commit API keys, passwords or other credentials, and keep the
local e2e environment file outside the repository.

## Tests

- Unit tests: `tests/test_units.py`, `tests/test_027.py` (run inside the
  `omuse` image, see README).
- Full local suite: `tests/run_in_docker.sh` (fresh stack per suite).
- Image smoke test: `tests/docker_image_smoke.sh <image>`; set `OMUSE_VERSION`
  to the tag to also check the reported version.
- `python3 tests/i18n_check.py` must report no missing or stale translations
  after any UI string change.
