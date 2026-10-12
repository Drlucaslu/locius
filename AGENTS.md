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
