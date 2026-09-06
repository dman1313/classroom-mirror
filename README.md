# Classroom Mirror

Classroom Mirror V2 is a local-only teacher support tool for **Windows and
macOS teacher-desk laptops with a selectable USB webcam**. The private teacher
dashboard will use anonymous sticky face numbers, High/Low sensitivity chosen
before Start, yellow then red movement/fidget cues, and an end-of-class recap.

Students never see the dashboard, flags, or numbers. Names, stored face images,
stored video, cloud processing, automated consequences, and student trials are
not part of the current implementation work. The first beta is adults only.

## Teacher alpha: the movement dashboard

The first teacher-visible V2 slice is now runnable end to end. It is the
"movement foundation" from the accepted plan: pick a camera and a **High/Low**
sensitivity, press **Start**, watch **anonymous position numbers** with a
**calm / yellow / red** movement cue, **Hide** instantly for privacy, press
**Stop**, and read a plain, uncertainty-first **recap**. It is adults only for
this alpha.

Privacy is held by construction: the browser only ever receives abstract marker
positions and a colour — never a camera image — the service binds only to
`127.0.0.1`, frames stay in memory, and the anonymous numbers are screen
positions (nearest-neighbour tracking), **not** faces or biometric templates.

Run it with no camera at all (synthetic movers, works headless):

```sh
python -m v2_runtime.dashboard --no-browser
# then open http://127.0.0.1:8471 and choose "Demo movers (no camera needed)"
```

On a Mac with a USB webcam (adults only), install once then launch and pick the
camera on the Start screen:

```sh
./install-v2-mac.sh
./run-dashboard.command
```

A headless one-shot recap (no server, no browser) is handy for a quick check:

```sh
python -m v2_runtime.dashboard --smoke-test --source synthetic --sensitivity low
```

The movement dashboard deliberately does **not** implement face matching,
persistence, or student use; those remain later, contract-gated slices.

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
