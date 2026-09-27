# Classroom Mirror

A private, local teacher dashboard for a **macOS adult trial**. Start a camera
session, see numbered position markers, count visible hand raises, follow
movement cues, and stop to read a recap. A clearly labelled practice mode works
without a camera.

**First beta platform: macOS (decided 2026-09-06). Windows is next — still a
target, not abandoned.**

## Open the app

On this Mac, double-click **Open Classroom Mirror.command**. The dashboard opens
at **http://127.0.0.1:8470**. Leave the Terminal window open while using it.

For a fresh installation, install Python 3.11, then double-click
**Install Classroom Mirror.command** once. Setup downloads the pinned packages
and verified local pose model. Later runs work offline.

1. Choose **Camera → Find cameras**, then select the camera to use.
2. Start with **Low** sensitivity and a **1-minute quick trial**.
3. Confirm that the trial includes consenting adults only, then **Start session**.
4. Use **Hide screen** or **Escape** to cover the whole dashboard.
5. Choose **Stop & see recap**, or let the timer end the session.

Choose **Try a practice session** to explore the interface with six made-up
figures. Practice recaps are always labelled; they do not demonstrate real-camera
accuracy.

The historical V1 `run.command` / `install.sh` refuse to launch and point here.

## What this version does

- Teacher dashboard with camera selection, High/Low sensitivity, and timed sessions.
- Local YOLO11 body pose detection with session-only position numbers.
- Movement cues that progress from yellow to red; High changes the waiting time,
  not the movement threshold. Cues describe movement only.
- Debounced hand-raise counting, current detections, and a room movement timeline.
- Complete privacy cover: the preview and numeric API output are blocked while hidden.
- Server-side auto-stop, release on camera failure, and stop after the dashboard
  disconnects for 30 seconds.
- Saved aggregate recaps, CSV totals, printing, delete-one/delete-all, and 30-day expiry.

Only aggregate recaps and model configuration live in the visible `data/` folder.
Images, video, face templates, names, and individual histories are not saved.
The application serves only `127.0.0.1`, rejects cross-site control requests,
and blocks non-loopback network connections at runtime.

## Design and limits

[SDD-DASHBOARD.md](SDD-DASHBOARD.md) is the product design for this delivery. It
reconciles [V2-DELTA.md](V2-DELTA.md), [AUDIT.md](AUDIT.md), and earlier
dashboard experiments. The signed historical [CONTRACT.md](CONTRACT.md) is
unchanged evidence, not the V2 scoreboard.

Position numbers reset each session and may change when people cross or leave
the frame. This build does **not** implement the older plan's persistent face
matching. Movement and hand-raise counts remain heuristic: crowds, distance,
lighting, camera shake, and occlusion can change results. The project's adult
trial and school-review requirements remain in place.

**Verified:** automated dashboard tests, non-hardware V2 gates (`t0`, `t1-mac`),
browser practice/recap/privacy flow, and real pose-model inference with outbound
connections blocked (on the authoring Mac). A live consenting-adult camera trial
is still required to validate physical camera permissions, framing, and observed
counts. Windows USB webcam smoke is still required per
[WINDOWS-V2-SMOKE.md](WINDOWS-V2-SMOKE.md).

## Development checks

```sh
.venv-mac-v2/bin/python -m pytest -q v2_tests -m 'not camera'
.venv-mac-v2/bin/python check-v2.py --stage t0
.venv-mac-v2/bin/python check-v2.py --stage t1-mac
```

For the original real-camera gate, supply a selected device explicitly:

```sh
./run-v2.command --smoke-test --camera-index 1 --seconds 3
```

The original `app/`, `tests/`, `CONTRACT.md`, and `./check` remain historical V1
evidence. The T1 camera slices remain in `v2_runtime/`. Use **Open Classroom
Mirror.command** or plain `./run-v2.command` for the teacher dashboard.

Runtime dependency versions and hashes are in `requirements-dashboard.txt`;
source/model provenance is in [DEPENDENCIES.md](DEPENDENCIES.md).
