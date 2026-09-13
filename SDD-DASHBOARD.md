# Classroom Mirror — usable dashboard design

Date: 2026-09-13. Target for this delivery: this macOS computer, with a private
teacher interface and consenting-adult trials. This document describes the
implementation; it does not amend the signed historical V1 contract.

## Source review and decisions

The repository's design sources were `CONTRACT.md`, `V2-DELTA.md`, `AUDIT.md`,
`MAC-V2-SMOKE.md`, and the unmerged `cursor/v2-teacher-product`,
`cursor/v2-teacher-yolo-ae72`, `cursor/live-view-mac-ready-990b`, and
`cursor/v2-movement-dashboard-85f2` branches. There was no standalone SDD file.

Main contained a camera connection page, while dashboard experiments were
unmerged. This implementation builds a coherent teacher path on main's runtime
foundation and retains the historical evidence and camera checks.

The experimental face-template path used cosine similarity over downsampled
face pixels. Its “wrap” added an HMAC but left the template plaintext. It also
allowed multiple detections to match the same number. That path is not included.
The new engine matches body positions one-to-one within a session, with a
1.5-second disappearance window and no cross-session recognition. Position
numbers are explicitly not stable personal identities.

## Teacher workflow

Open → choose Camera or Practice → select camera/sensitivity/duration → confirm
adult trial for real camera → Start → live view → Hide/Show or Stop → recap.

Camera access never starts on page load. The explicit Find cameras control
probes and releases indexes 0–5. Start captures only the selected device and
never falls back to a different camera. The practice source generates six
synthetic keypoint streams, with movement and periodic hand raises.

Low sensitivity waits 8 seconds before yellow and another 16 before red. High
waits 3 and 7 seconds. Both use the same 0.12 body-heights-per-second movement
threshold and the same pose confidence floor. Time is measured in seconds,
not frames. Returning from an observation gap resets cue timing. Missing
keypoints are not treated as evidence of a personal trait or mental state.

## Components

- `v2_app/server.py`: FastAPI routes, strict request validation, host/origin
  checks, same-site request header, no-store/CSP headers, lifecycle cleanup.
- `v2_app/session.py`: serialized session state, camera worker, timers,
  heartbeat, stop/error/release handling, preview held in memory only.
- `v2_app/engine.py`: one-to-one position tracking, timed movement cues,
  debounced hand raises, aggregate timeline and recap.
- `v2_app/vision.py`: local YOLO11 pose weights, body keypoints, confidence
  filtering; no face crop or template path. No download at runtime.
- `v2_app/store.py`: local SQLite aggregate recaps with secure deletion and
  expiry. No per-person geometry is persisted.
- `v2_app/static/`: offline HTML/CSS/JavaScript dashboard, responsive layout,
  full privacy cover, camera canvas, synthetic practice rendering, recap export.
- `scripts/setup_model.py`: install-only upstream model fetch with SHA-256 check.

## Lifecycle and recovery

Exactly one session worker may run. Starting another returns a conflict.
Start is asynchronous so model loading is visible in the UI. The worker owns
camera release in `finally`; Stop waits briefly and leaves a Stopping state
until release completes. Another session cannot take the device during that
interval. Shutdown requests stop and waits for cleanup.

The worker checks the session deadline even if the browser is hidden. A dashboard
heartbeat that is absent for 30 seconds stops capture. A partial session with
observations produces a recap marked with its failure/disconnection reason.
A failure before any observations produces an error, not a successful recap.

Hide immediately covers the page in JavaScript. While hidden, the server returns
no preview, no live counters, and no recap history. Show requires a successful
request before removing the cover. Sensitivity is immutable during a session.

## Data and network boundaries

- All frames/JPEG bytes remain in process/browser memory; no camera snapshots
  are taken during development or saved by the app.
- `data/dashboard/recaps.sqlite3` stores start time, duration, source, profile,
  frame count, peak concurrent detections, hand-raise total, yellow/red episodes,
  end reason, and a room-level 10-second timeline.
- `data/model-config/` stores third-party model settings and font caches only.
- Recaps expire after 30 days and are removable individually or all at once.
- Explicit CSV export contains totals only; printing uses the displayed recap.
- Runtime binds only the literal `127.0.0.1`. A process audit hook refuses
  external socket connects/binds/sends and DNS lookups. Model offline mode and
  auto-install suppression are configured before loading the dependency.
- Host/origin validation prevents DNS rebinding and cross-site camera-control
  requests. No external scripts, fonts, analytics, or image resources are used.

## Verification and remaining limits

Automated tests cover start/stop/history, persistence/expiry/deletion, strict
validation, adult gating, duplicate start, one-to-one matching, occlusion,
hand-raise fixtures, yellow-before-red/recovery, privacy APIs, server-side timer,
disconnect stop, camera failure/release, in-memory JPEG output, and network guard.
The existing non-hardware V2 tests remain intact. Browser verification exercises
practice start, hide/show, stop-to-recap, responsive layout, and export.
Recap deletion and expiry are covered by API tests.
Real YOLO11 inference was run on a blank in-memory frame with network guard active;
after warm-up, four-frame timing was approximately 0.1 seconds per frame on this Mac.

Not claimed: validated classroom accuracy, completed live adult camera trial,
Windows device verification, persistent face identity, school approval, or
completion of every item in the older V2 plan. These are visible limitations,
not silently passed acceptance tests.
