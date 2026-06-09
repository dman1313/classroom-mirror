# Classroom Mirror

A local-only webcam tool for teachers: classroom moments become **numbers,
never video**. Built privacy-first for a French/EU school context.

- **Mode 1 — strategy tracking.** Is a support strategy working for a
  designated child? Consent-gated, pseudonymous (LIMS codes, never names),
  zone-based (no facial recognition). Baseline vs strategy sessions produce a
  neutral before/after report.
- **Mode 2 — whole-class reflection.** Aggregate-only room patterns
  (hand-raises, movement, people in view) as a mirror for the teacher's own
  practice. No per-child data exists in this mode — the database table has no
  column for it.

## The contract

This project was built with the [Loop Generator](https://github.com/dman1313/agent-ready-coding-loop)
method: [CONTRACT.md](CONTRACT.md) holds 19 binary criteria signed before any
code was written. **`./check` proves them all** — a plain-English scoreboard
anyone can run, guardrails first:

no video stored · no facial recognition · no emotion/attention inference ·
names cannot enter the system · zero network traffic at runtime · consent
required for Mode 1 · Mode 2 aggregate-only by schema · full erasure.

## Run it

```
bash install.sh        # once, needs internet once
double-click run.command
./check                # the scoreboard, any time
```

See [SETUP.md](SETUP.md) for the non-coder version, and
[HUMAN-CHECKS.md](HUMAN-CHECKS.md) for the five human sign-offs.

## Honesty clause

Fixtures prove the mechanism, not classroom-grade accuracy — pose detection
in a crowded room is noisy. Real-classroom use requires the homework in
SETUP.md first: DPIA, parental consent (Mode 1), school sign-off, CNIL check.

## Stack

Python 3.11 · Ultralytics YOLO11n-pose (AGPL — see LATER.md before any
distribution) · OpenCV · FastAPI on 127.0.0.1 · SQLite · no JS frameworks.
