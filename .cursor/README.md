# Cloud Agent environment

This folder configures the Cloud Agent development environment and provides
helper scripts so an agent can build, run, test, and iterate on Classroom
Mirror unattended.

## Layout

| File | Purpose |
| --- | --- |
| `environment.json` | Base image (Dockerfile), install command, auto-started `v1-web` server on `127.0.0.1:8470`. |
| `Dockerfile` | Ubuntu 24.04 + Python 3.11 (deadsnakes) + OpenCV runtime libs. System deps only. |
| `install.sh` | Idempotent bootstrap: builds both venvs, installs deps, fetches the pose model. |
| `requirements-dev.txt` | Dev-only tools (`pytest`, `httpx`) installed into both venvs. Product locks stay untouched. |
| `test.sh` | Runs the full camera-free validation battery with the right interpreter per suite. |
| `seed_demo.py` | Populates the DB with demo sessions via the real engines + synthetic fixtures (no camera). |
| `camera_smoke.py` | Runs the real pose model end to end over a generated video (headless, no webcam). |

## Two virtualenvs

- `.venv` — V1 pose stack (`app/`, `tests/`): ultralytics, torch, opencv, fastapi. Has `pytest`.
- `.venv-mac-v2` — V2 camera runtime (`v2_runtime/`, `v2_tests/`): pinned lightweight deps. Now also has `pytest`.

Both are project-local and git-ignored; `install.sh` recreates them.

## Common commands (from the repo root)

```sh
bash .cursor/install.sh                 # build/refresh the environment (idempotent)
bash .cursor/test.sh                    # full camera-free test battery
./.venv/bin/python .cursor/seed_demo.py --reset   # populate the dashboard with demo data
./.venv/bin/python .cursor/camera_smoke.py        # real-model pipeline smoke, no camera
./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8470   # V1 web app
```

The `v1-web` terminal starts the V1 app automatically on boot, so the dashboard
is reachable at `http://127.0.0.1:8470/` without any manual step. Seed demo data
to see populated reports.

## The camera limitation (important for autonomous testing)

Classroom Mirror is a local, USB-webcam tool for Windows/macOS laptops. The
Cloud Agent VM is headless Linux with **no camera, and no way to create one**:
there are no kernel modules available (`/lib/modules` is absent, `modprobe` is
missing), so `v4l2loopback`-style virtual cameras cannot be loaded and no
`/dev/video*` device can exist.

What this means, and how to test around it:

- **Camera-independent logic runs fully** — detector, heuristics, engines,
  reports, DB, policy, and both web surfaces. This is the large majority of the
  code and is covered by `bash .cursor/test.sh`.
- **The real model + pipeline can still run headlessly** from a video file:
  OpenCV here has the FFMPEG backend, and the app exposes `VideoFileSource` /
  `process_video`. See `camera_smoke.py`.
- **Raw webcam entry points cannot be exercised headlessly.** `v2_runtime`
  already injects a `capture_factory` for its tests, so those are covered. The
  V1 `app.camera.WebcamSource` has no such seam, so a true live `VideoCapture(0)`
  run is the one path that cannot be validated on this VM. If live-capture e2e
  testing is needed, add a small opt-in seam (e.g. a `CLASSROOM_MIRROR_FAKE_CAMERA`
  env var that makes `WebcamSource` read from a video file) — this is product
  code and touches guardrail-sensitive files, so it should be an explicit change.
- `check-v2.py --stage t1` requires an enumerated physical camera index and is
  therefore intentionally excluded from `test.sh`.

## Network egress

Egress is currently unrestricted. If it is later locked down, the environment
needs outbound access to:

- `pypi.org`, `files.pythonhosted.org` — pip installs during `install.sh`.
- `github.com`, `objects.githubusercontent.com` — one-time pose-model download
  (`yolo11n-pose.pt`) from the ultralytics assets release.

The app itself makes **no** outbound calls at runtime (a guardrail test enforces
this); only environment setup needs the network.

## Secrets

None. The product is fully local and integrates with no external services, so
no secrets or test logins are required to build, run, or test it.
