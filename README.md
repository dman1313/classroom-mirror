# Classroom Mirror

Classroom Mirror V2 is a local-only teacher support tool for **Windows and
macOS teacher-desk laptops with a selectable USB webcam**. The private teacher
dashboard uses anonymous sticky face numbers, High/Low sensitivity chosen
before Start, yellow then red movement/fidget cues, and an end-of-class recap.

Students never see the dashboard, flags, or numbers. Names, stored face images,
stored video, cloud processing, automated consequences, and student trials are
not part of the current implementation work. The first beta is adults only.

## Current implementation status

The accepted V2 plan is reconciled with this repository. Shared camera runtime
(Windows T1 + macOS), YOLO11 pose, sticky anonymous numbers, High/Low
sensitivity, yellow-then-red movement cues, and the teacher-only live/recap
dashboard are implemented. Adult beta only.

The teacher dashboard needs the pose stack from `./install.sh` (ultralytics +
local `yolo11n-pose.pt`). The macOS camera-slice installer
(`./install-v2-mac.sh`) stays camera-only and does not download pose weights.

Start with:

- [V2-DELTA.md](V2-DELTA.md) — contract conflict, repository inventory, exact
  acceptance tests and commands, and the bounded T1 implementation slice.
- [WINDOWS-V2-SMOKE.md](WINDOWS-V2-SMOKE.md) — adult-only Windows USB camera
  smoke checklist.
- [MAC-V2-SMOKE.md](MAC-V2-SMOKE.md) — exact macOS install, permission, camera
  picker, and real-device smoke checklist.

On macOS with Python 3.11:

```sh
./install-v2-mac.sh
./run-v2.command
```

This V2 launcher inventories local cameras, requires an explicit index, reads
frames in memory for a bounded connection check, then opens the teacher-only
dashboard on `127.0.0.1`. YOLO11 pose supplies in-memory body keypoints;
anonymous numbers are local templates, never names. The historical
`run.command` remains V1 evidence.

Double-click `./run-v2.command` (or run it with no flags) opens the teacher
dashboard using `.venv` when that pose install exists. Camera inventory and
`--smoke-test` still use `.venv-mac-v2`.

Run the dependency-free T0 readiness check with Python 3.11:

```sh
python check-v2.py --stage t0
```

On Windows with the project `.venv`:

```bat
.\run.bat --smoke-test --camera-index 1 --seconds 10
.\run.bat
```

The T1 gate requires an enumerated camera index. Camera-free product tests:

```sh
python check-v2.py --stage t0
python -m pytest -q v2_tests
```

## Historical V1 evidence

The current `app/`, `tests/`, Mac launchers, and signed [CONTRACT.md](CONTRACT.md)
implement the cancelled V1 pose-only/no-faces product. They remain in the
repository because their tests are useful historical evidence; they are not
the V2 product path and must not be weakened or silently reinterpreted.

The historical command remains:

```sh
./check
```

It proves only the signed V1 Mac/pose-only criteria. The local `.venv` is not
portable and may need to be recreated before that historical suite can run.

## Retained stack direction

The accepted plan retains Python 3.11, FastAPI/Uvicorn on `127.0.0.1`, OpenCV,
SQLite, and the pose pipeline unless T1 proves a blocker. T1 must lock reviewed
versions and licences before beta release; `requirements.txt` currently gives
lower bounds only.
