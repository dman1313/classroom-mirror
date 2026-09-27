# Classroom Mirror — Setup Guide

> **Historical V1 instructions.** This Mac/LIMS/pose-only setup is preserved as
> test evidence and is not the accepted product path. The current app is the
> teacher dashboard in [README.md](README.md) and [SDD-DASHBOARD.md](SDD-DASHBOARD.md).
> `run.command` and `install.sh` now refuse to launch V1 and redirect you there.
> Do not use this setup for a student trial.

A local webcam tool that turns classroom moments into **numbers, never video**.
Whole-class numbers are anonymous; individual tracking exists only for a
designated child with recorded consent, identified by a LIMS code — never a name.

Everything runs on this Mac. Nothing is sent anywhere, ever.

## One-time install (needs the internet once)

1. Open the **Terminal** app (press Cmd+Space, type "Terminal", press Return).
2. Type `cd ` (with a space after it), then **drag this folder** from Finder
   into the Terminal window, and press Return.
3. Type `bash install.sh` and press Return. Wait — the slow part takes a few
   minutes. It ends with "Done."

After this, the app never touches the internet again (and a test proves it —
see "Checking the app's promises" below).

## Starting the app

Double-click **run.command** in this folder.

- The first time, macOS may say it's from an unidentified developer:
  right-click the file, choose **Open**, then **Open** again.
- macOS will ask permission to use the **camera** — click Allow.
- Your web browser opens the app at `http://127.0.0.1:8470`.
- Leave the black Terminal window open; closing it stops the app.

V1 does **not** ship seeded demo data. The "L-7" examples live only in the
historical test fixtures under `tests/`. After a fresh V1 install the reports
are empty until you run a session (adults only during development).

## Using it

**Whole-class session (Mode 2):** type a class code (like `6B`), click
"Start a whole-class session". The camera counts room-level things only —
total hand-raises, movement level, people in view. Click Stop to get the
session summary. No child is ever identified.

**Individual session (Mode 1):** click "Start an individual session". Drag a
box over the designated child's usual spot, type their LIMS code, tick the
consent box **only if consent is really recorded**, pick *baseline* (before
the strategy) or *strategy* (strategy in use), and Start. After several
sessions of each kind, the child's strategy report shows before vs after.

## Checking the app's promises

In Terminal, in this folder, run:

    ./check

You'll get a scoreboard: every promise in `CONTRACT.md`, each marked YES or
NO with proof. The guardrails (no video stored, no names, no faces, no
internet, consent required, anonymous whole-class mode, erasure works) are
listed first. Run it any time — today or in six months.

## If it ever breaks

1. Run `./check` and copy the scoreboard.
2. Copy the newest error message from the Terminal window.
3. Paste both, plus the file `CONTRACT.md`, into a fresh AI-agent chat
   (Claude Code or similar). That is everything it needs to fix the app.

## Before using it in a real classroom — required homework

- A **DPIA** (data-protection impact assessment) with your school's data
  protection officer. Required for Mode 1; strongly advised for everything.
- **Parental consent** for any Mode 1 child. The app only records that
  consent exists — collecting it is human work.
- School leadership sign-off, and a check against current **CNIL** guidance
  (France is the strictest country for cameras in schools).
