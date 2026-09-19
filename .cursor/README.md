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
| `test.sh` | Runs the camera-free validation battery; `--with-live` adds the model-backed headless smokes. |
| `seed_demo.py` | Populates the DB with demo sessions via the real engines + synthetic fixtures (no camera). |
| `camera_smoke.py` | Runs the real pose model end to end over a generated video (headless, no webcam). |
| `live_session_smoke.py` | Drives the real `CameraService` live-session loop headlessly via the video-file seam. |

## Two virtualenvs

- `.venv` — V1 pose stack (`app/`, `tests/`): ultralytics, torch, opencv, fastapi. Has `pytest`.
- `.venv-mac-v2` — V2 camera runtime (`v2_runtime/`, `v2_tests/`): pinned lightweight deps. Now also has `pytest`.

Both are project-local and git-ignored; `install.sh` recreates them.

## Common commands (from the repo root)

```sh
bash .cursor/install.sh                 # build/refresh the environment (idempotent)
bash .cursor/test.sh                    # fast camera-free test battery
bash .cursor/test.sh --with-live        # ... plus the model-backed headless smokes
./.venv/bin/python .cursor/seed_demo.py --reset      # populate the dashboard with demo data
./.venv/bin/python .cursor/camera_smoke.py           # real-model pipeline smoke, no camera
./.venv/bin/python .cursor/live_session_smoke.py     # real live-session loop, no camera
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
- **The real model + pipeline run headlessly** from a video file: OpenCV here
  has the FFMPEG backend, and the app exposes `VideoFileSource` / `process_video`.
  See `camera_smoke.py`.
- **The real live-session loop runs headlessly too.** `live_session_smoke.py`
  drives the actual `CameraService` lifecycle (start → capture → detect → engine
  → stop → persist → report), swapping only the frame *source* to the existing
  `VideoFileSource` seam in-process (a monkeypatch in the helper — **no product
  code is modified**). It also asserts the runtime wrote no frame files.
- **The only unexercised line is the literal OS device open** —
  `cv2.VideoCapture(0)` inside `WebcamSource` — plus the V2 real-camera smoke.
  `v2_runtime` already injects a `capture_factory` for its own tests. Fully
  validating device open/read/release requires a physical webcam and is
  hardware/human territory by design (`check-v2.py --stage t1` demands an
  enumerated physical index and is excluded from `test.sh`). Per `CONTRACT.md` /
  `V2-DELTA.md`, missing hardware must be reported as NOT RUN, never faked.
- If a *runtime* no-camera demo mode is ever wanted (it is listed in `LATER.md`),
  it would be an explicit product change to `WebcamSource`; the helper above
  already covers the *testing* need without touching product code.

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
