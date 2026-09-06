# Classroom Mirror

Classroom Mirror V2 is a local-only teacher support tool for **Windows and
macOS teacher-desk laptops with a selectable USB webcam**. The private teacher
dashboard will use anonymous sticky face numbers, High/Low sensitivity chosen
before Start, yellow then red movement/fidget cues, and an end-of-class recap.

Students never see the dashboard, flags, or numbers. Names, stored face images,
stored video, cloud processing, automated consequences, and student trials are
not part of the current implementation work. The first beta is adults only.

## Current implementation status

The accepted V2 plan is reconciled with this repository. The first shared V2
camera runtime and macOS install/run path are implemented; later anonymous-ID,
sensitivity, alert, and recap slices are not yet implemented. Start with:

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
frames in memory for a bounded connection check, and serves only on
`127.0.0.1`. The historical `run.command` remains V1 evidence.

### What the teacher does on the Mac

1. Run `./install-v2-mac.sh` once (creates a project-local Python environment,
   no admin rights).
2. Run `./run-v2.command`. When prompted, type the USB camera index it lists.
3. The teacher dashboard opens automatically. If it does not, open
   **http://127.0.0.1:8470** in Safari or Chrome after Start.
4. On the setup page pick the camera, sensitivity, and a **1-minute quick test**,
   then press **Start class**.
5. Watch the live view: **green boxes mark whoever is moving right now**, with a
   people-seen / moving-now count and a countdown. Press **Stop & see recap** (or
   let the quick test auto-stop) to reach the recap.

If the camera does not appear or stays black, follow the on-screen macOS
permission steps (System Settings → Privacy & Security → Camera → enable
Terminal, then reopen Terminal). Frames are shown only to the teacher and are
never written to disk.

Run the dependency-free T0 readiness check with Python 3.11:

```sh
python check-v2.py --stage t0
```

The T1 gate intentionally fails closed until the Windows runtime suite exists:

```sh
python check-v2.py --stage t1 --camera-index 1
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
