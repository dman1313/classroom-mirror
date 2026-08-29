# Windows V2 USB camera smoke — adult beta only

This checklist is for a consenting adult on the named Windows 10/11 x64 beta
laptop. Do not aim the USB webcam at students and do not begin a student trial.

## Preconditions

- One physical USB webcam is plugged in and aimed down the centre aisle only
  after the room is clear of students.
- The teacher laptop is on a standard account without administrator rights.
- The dashboard is visible only to the adult tester; projection/screen sharing
  is off.
- The repository is in a fresh working directory. Record `git status --short`
  before and after the smoke.
- The expected USB device index has been identified by the T1 inventory output.

## Commands

From a normal, non-elevated `cmd.exe` in the repository root, replace `1` with
the enumerated USB webcam index:

```bat
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -CheckOnly
.\.venv\Scripts\python.exe check-v2.py --stage t1 --camera-index 1
.\run.bat --smoke-test --camera-index 1 --seconds 10
```

If school Group Policy blocks the PowerShell script, stop. The preflight must
report the policy and affected command; it must not change policy or request
elevation. If camera access is denied, the diagnostic must name Windows
Privacy & security > Camera and `ms-settings:privacy-webcam`.

## Required evidence

Check each item; any unchecked item is NOT RUN or FAIL, never PASS.

- [ ] Preflight confirms Windows 10/11 x64 and that the process runs without
      administrator rights.
- [ ] Preflight identifies a writable per-user app-data directory and does not
      write into Program Files, Windows, the desktop, or the repository.
- [ ] Inventory lists the USB webcam; the smoke names the selected index and
      OpenCV backend.
- [ ] The selected camera opens, returns non-empty frames for 10 seconds, and
      releases cleanly.
- [ ] The app binds only to `127.0.0.1`; a local health request succeeds and no
      LAN/wildcard listener appears.
- [ ] Runtime succeeds with outbound network blocked and reports zero outbound
      connection attempts.
- [ ] No image or video files, face crops, screenshots, or frame bytes appear
      in the repository, per-user data directory, working directory, or temp
      directory. Only explicitly allowlisted non-media runtime files may exist.
- [ ] `run.bat --smoke-test` shuts the service down and returns exit code 0.
- [ ] Unplugging the USB webcam or denying camera permission produces a
      plain-language nonzero result and never falls back silently to another
      camera.
- [ ] `git status --short` has no new runtime file after the smoke.

## Evidence to retain

Retain text only: timestamp, Windows version/build, standard-user/admin=false,
camera index, backend name, frame count (not pixels), elapsed seconds, loopback
address, outbound-attempt count, filesystem-delta filenames, command exit codes,
and PASS/FAIL/NOT RUN. Do not retain frames, thumbnails, screenshots, device
serial numbers, account names, or paths containing a person’s name.
