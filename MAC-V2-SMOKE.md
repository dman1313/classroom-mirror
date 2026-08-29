# macOS V2 USB camera smoke — adult beta only

This checklist is for a consenting adult on the named Mac. Do not aim any
camera at students and do not begin a student trial. The V2 launcher is
separate from the historical V1 `run.command` and never opens the LIMS/mode UI.

## Preconditions

- Plug in the physical USB camera and close FaceTime, Zoom, Teams, Photo Booth,
  and any other app that may hold a camera.
- Keep the teacher-only page off projectors and screen sharing.
- Open Terminal in the repository root.
- Record `git status --short` before and after the smoke.

## Install and automated gate

```sh
./install-v2-mac.sh --check-only
./install-v2-mac.sh
.venv-mac-v2/bin/python check-v2.py --stage t1-mac
```

The installer uses Python 3.11, creates `.venv-mac-v2` without `sudo`, and
installs only the pinned shared V2 camera runtime. It does not download the
historical pose model.

## Camera permission and picker

Run the picker from Terminal so macOS can associate camera permission with the
terminal process:

```sh
./run-v2.command --list-cameras --max-index 5
```

On first use, accept the camera prompt. If the prompt does not appear or access
was denied, open System Settings > Privacy & Security > Camera, enable Terminal,
quit Terminal, reopen it, and rerun the command. Apple documents this control at
https://support.apple.com/guide/mac-help/control-access-to-your-camera-mchlf6d108da/mac.

OpenCV reports stable numeric indexes and capture backends, not reliable USB
product names on every Mac. Identify the USB camera by running the inventory
once unplugged and once plugged in; select the newly appearing index. Do not
record device serial numbers or frames.

## Real camera smoke

Replace `1` with the enumerated physical USB camera index:

```sh
./run-v2.command --smoke-test --camera-index 1 --seconds 10
```

For this Mac proof only, if no USB camera is attached, the built-in camera may
be used as a hardware fallback by explicitly selecting its listed index. Record
that outcome as `PASS (built-in fallback; USB NOT RUN)`, never as USB PASS. The
runtime itself never falls back silently: it opens only the selected index.

## Pass/fail checklist

- [ ] PASS / FAIL — preflight reports macOS, arm64 or x86_64, Python 3.11,
      no administrator requirement, and `127.0.0.1` only.
- [ ] PASS / FAIL / NOT RUN — inventory lists the physical USB camera and the
      chosen numeric index. If only the built-in camera is available, say so.
- [ ] PASS / FAIL — the explicit selected camera opens, returns one or more
      in-memory frames, prints only index/backend/count/elapsed text, and releases.
- [ ] PASS / FAIL — a missing, busy, or denied selected camera returns nonzero
      with Privacy & Security > Camera guidance and no silent fallback.
- [ ] PASS / FAIL — the app rejects `0.0.0.0`, `::`, `localhost`, and LAN hosts;
      the normal service address is `127.0.0.1` only.
- [ ] PASS / FAIL — No image or video files, face crops, thumbnails,
      screenshots, or encoded frame bytes are written by the V2 runtime.
- [ ] PASS / FAIL — `git status --short` gains no runtime file after smoke.

## Evidence retained for this Mac run

Retain text only: date/time, macOS version, architecture, Python version, camera
index and backend, whether USB or built-in fallback, frame count, elapsed time,
loopback host, exit codes, and filesystem-delta filenames. Do not retain frames,
screenshots, serial numbers, account names, or paths containing a person's name.

The issue comment is the run-specific scoreboard; this document remains the
reusable exact procedure.

## This Mac proof — 2026-08-29

Machine-readable text evidence from the adult-beta Mac used for this slice:

| Check | Result | Evidence |
|---|---|---|
| Preflight | PASS | macOS 27.0, arm64, Python 3.11.15, project-local environment, no elevation, `127.0.0.1` policy |
| Clean V2 install | PASS | Exact runtime lock installed; OpenCV 4.14.0.94, FastAPI 0.141.1, and Uvicorn 0.52.4 imported; `pip check` reported no broken requirements |
| Automated Mac/shared gate | PASS | 9 tests passed with `.venv-mac-v2/bin/python check-v2.py --stage t1-mac` |
| USB camera inventory | NOT RUN | macOS/OpenCV returned `not authorized to capture video (status 0)` for every bounded probe, so no USB index could be enumerated honestly |
| Built-in fallback | NOT RUN | The same macOS permission denial prevented a built-in-camera smoke; index 0 was used only to prove the selected-device failure path, not recorded as a built-in camera |
| Permission diagnostic | PASS | Selected index 0 returned exit 2, named System Settings > Privacy & Security > Camera, and stated that no fallback was attempted |
| Loopback fail-closed | PASS | `--host 0.0.0.0` was refused before camera access and returned exit 2; only literal `127.0.0.1` is accepted |
| No frame/media writes | PASS | Media-file snapshot delta was empty before/after the real permission-denied smoke |
| No runtime worktree writes | PASS | `git status --short` was identical before/after both smoke commands |

Because macOS camera authorization was unavailable to this terminal run, this
is a clear hardware/permission skip, not a successful USB or built-in camera
capture claim. The fake-device acceptance tests still prove that a chosen
non-default index is the only index opened and that release occurs on both
success and failure.
