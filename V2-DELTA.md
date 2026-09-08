# Classroom Mirror V2 contract and command delta

**Accepted product source:** [MKI-5 plan](/MKI/issues/MKI-5#document-plan)

**T0 reconciliation:** [MKI-7](/MKI/issues/MKI-7)

**Date:** 2026-08-29

**Status:** T0 handoff for T1; this document does not implement the V2 runtime.

**2026-09-08 update:** the `V2-T1-01`…`V2-T1-10` acceptance suite is now
complete in `v2_tests/test_windows_runtime.py`, and `check-v2.py --stage t1`
passes end to end against a real selected camera. The camera-hardware-dependent
tests (`V2-T1-02/04/05/08`) are marked `@pytest.mark.camera` and fail closed,
never skip, without an explicitly selected real device — see the T1 focused
development loop below. This has so far only been run against a real webcam on
macOS as a stand-in; it has not yet been run on real Windows 10/11 x64 with a
USB webcam per `WINDOWS-V2-SMOKE.md`, which remains the actual T1 acceptance
evidence for the contractual target platform.

## Decision

V2 is the product path: a Windows 10/11 teacher-desk app using a selectable
USB webcam, a private teacher-only dashboard, anonymous sticky face numbers,
High/Low sensitivity selected before Start, yellow then red movement/fidget
flags, and an end-of-class recap. Runtime is local only. Frames and face crops
remain in RAM. Names, stored image/video, cloud processing, automated
consequences, and student trials are out of scope.

The signed V1 `CONTRACT.md` is historical evidence, not the V2 contract. It is
preserved byte-for-byte at SHA-256
`512212808758c2a82b8e14e5a776d7fcc8526e7ed5720e9dd6565c47398ca4b9`.
Only Dwayne may amend that school-facing document. V2 work must not weaken it
silently or claim that its old scoreboard proves the new product.

## The explicit contract conflict

V1 criterion 2 says **no facial recognition and no biometric template**. The
accepted V2 product requires **anonymous sticky face numbers** backed by local
face templates. Anonymous templates are still biometric data. Those statements
cannot both be true in one scoreboard.

Other material conflicts are:

| V1 evidence retained | Why it cannot remain a V2 acceptance claim | V2 replacement |
|---|---|---|
| Criterion 2 bans face-capable dependencies and template columns | V2 needs local face-template matching | Permit only the reviewed matching component; prove no names/crops, user-bound encryption, match-confidence floor, expiry, and deletion |
| Criterion 3 bans the text `on-task` | V2 later includes a possible sitting/on-task support cue | Ban claims of fact, judgment, emotion, discipline, grading, diagnosis, and automated consequences; require uncertainty/support wording |
| Criteria 4, 6, 8 use LIMS codes and per-child consent records | V2 has anonymous IDs and an adult-beta gate, not LIMS entry | Prove no name-entry field and no external identifier; prove delete-one-ID, delete-session, delete-all, and expiry |
| Criterion 7 makes whole-class mode aggregate-only | V2 live flags are per anonymous ID | Prove the dashboard is teacher-only and stored rows use anonymous IDs only |
| Criteria 9–14 exercise V1 zone/mode reports | V2 order is movement foundation, hand raising, recap, then later support cues | Add deterministic sticky-ID, sensitivity, yellow/red, hand-raise, and recap tests |
| Criterion 18 targets a Mac launcher | V2 targets Windows 10/11 x64 without elevation | Replace with PowerShell preflight, per-user install, `run.bat`, and real USB camera smoke |

`tests/`, `CONTRACT.md`, `run.command`, and the V1 reports remain intact as
historical implementation evidence. They are not collected by the V2 runner.
If a future, explicitly approved contract amendment retires them, move them to
an archive commit; never delete them merely to get V2 green.

## Repository inventory against V2

| Area | Present repository | V2 gap / reuse decision |
|---|---|---|
| Runtime | Python app, FastAPI, Uvicorn, OpenCV, SQLite | Reuse Python architecture after version/licence lock; add Windows per-user preflight/install and launcher |
| Camera | `WebcamSource(index=0)` and in-memory MJPEG preview | Add device enumeration/selection, explicit Windows backend diagnostics, selected index, permission-denied guidance, and release smoke |
| Network | App constant binds `127.0.0.1`; old test blocks outbound sockets | Reuse and extend into V2; fail on any non-loopback bind or outbound attempt |
| Frame storage | Runtime uses `cv2.imencode` to RAM; old fixture writes a temporary synthetic video | Reuse runtime pattern; V2 tests must distinguish test-fixture writes from runtime writes and watch the whole allowed runtime tree |
| Identity | Zone + LIMS code; schema explicitly bans embeddings/templates | Replace in later slice with anonymous ID + encrypted template storage; no name or external ID fields |
| Alerts | Low/medium/high per-minute movement bucket | Replace with versioned High/Low sensitivity profiles and yellow-before-red state transitions |
| UI | Server-rendered local pages with camera preview | Replace V1 modes with Start configuration, private live flags, immediate privacy hide, Stop, and recap |
| Reports | V1 before/after and aggregate reports | Replace with uncertainty-first event recap; no ranking or punitive score |
| Packaging | `install.sh`, `run.command`, Mac instructions | Add `install.ps1` and `run.bat`; no silent elevation; plain-language IT diagnostic |
| Dependencies | Lower bounds only; no lockfile | T1 must select exact supported versions, review licences/provenance, and commit one reproducible lock before beta release |

Observed during T0:

- Commit `116d579` records the V1 result “Scoreboard 14/14 AUTO YES.”
- The workspace `./check` currently stops before test collection because
  `.venv/bin/python3` points into a deleted prior-run scratch directory.
- A clean wheel-only resolution of the unpinned requirements on 2026-08-29
  selected Python 3.11.15, Ultralytics 8.4.133, OpenCV 5.0.0.93, FastAPI
  0.141.1, Uvicorn 0.52.4, pytest 9.1.1, and httpx 0.28.1. On this macOS
  runner, OpenCV then failed collection because the downloaded native library
  was rejected by system code-signing policy. This is environment/dependency
  evidence, not a failed V2 behaviour test.

## Command delta

### Historical V1 evidence — unchanged

```sh
./check
```

This command continues to mean only “run the signed V1 Mac/pose-only
scoreboard.” It must never be renamed to V2 or used as V2 release evidence.

### T0 delta readiness — implemented here

```sh
python check-v2.py --stage t0
```

This is dependency-free. It proves the signed V1 contract is unchanged, the
conflict is explicit, and the Windows adult-beta smoke contract exists.

### T1 Windows automated gate — must be made green by T1

The stage interface is `python check-v2.py --stage t1 --camera-index <n>`;
Windows uses the project interpreter explicitly as shown below.

Run from a normal, non-elevated `cmd.exe` in the repository root:

```bat
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -CheckOnly
.\.venv\Scripts\python.exe check-v2.py --stage t1 --camera-index 1
.\run.bat --smoke-test --camera-index 1 --seconds 10
```

`1` is an example. The tester supplies the enumerated index for the physical
USB webcam. The check must print the selected device index and capture backend
without printing or storing frames.

PowerShell `-ExecutionPolicy Bypass` applies to that process and does not
override school Group Policy. `install.ps1 -CheckOnly` must report a policy
block instead of changing machine or user policy, requesting elevation, or
silently falling back.

### T1 focused development loop

```bat
.\.venv\Scripts\python.exe -m pytest -q v2_tests\test_windows_runtime.py -m "not camera"
.\.venv\Scripts\python.exe -m pytest -q v2_tests\test_windows_runtime.py -m camera --camera-index 1
```

The non-camera group uses fakes and temporary directories. The camera group is
Windows/adult-beta only and requires an explicitly selected real USB webcam.
No V2 runtime test may be skipped, xfailed, or converted into a warning in a
release result. Missing hardware is a clear NOT RUN result, never a PASS.

## What `check-v2 --stage t1` must prove

T1 creates `v2_tests/test_windows_runtime.py` with these exact externally
observable tests. Names are stable acceptance IDs, not implementation hints.

| ID and required test name | Proof |
|---|---|
| `V2-T1-01 test_preflight_runs_without_admin_or_installing` | `install.ps1 -CheckOnly` exits deterministically as a standard user, writes nothing outside run scratch, never invokes elevation, and reports OS/architecture/Python/camera/model/data-policy status |
| `V2-T1-02 test_camera_inventory_can_select_non_default_device` | Inventory returns stable display rows and opens the requested index rather than always using camera 0 |
| `V2-T1-03 test_missing_or_denied_camera_fails_clearly` | Absent, busy, or privacy-denied camera produces distinct plain-language diagnostics, with `ms-settings:privacy-webcam` guidance for denial |
| `V2-T1-04 test_selected_camera_reads_frames_in_memory_and_releases` | Selected camera produces non-empty frames for the bounded smoke interval and is released on success and failure |
| `V2-T1-05 test_camera_smoke_writes_no_frame_image_or_video` | Snapshot + write-spy across repo, data directory, user data directory, and process working directory finds no image/video/crop file or encoded frame bytes after real-camera smoke |
| `V2-T1-06 test_service_refuses_non_loopback_bind` | Only `127.0.0.1` is accepted; `0.0.0.0`, LAN addresses, and `::` fail closed |
| `V2-T1-07 test_runtime_completes_with_outbound_network_blocked` | Preflight after local install, camera open/read/release, and local health request make zero non-loopback connection attempts |
| `V2-T1-08 test_run_bat_smoke_uses_selected_camera_and_exits` | `run.bat --smoke-test` uses the selected index, starts loopback service, reports health, shuts down, and returns nonzero for failures |
| `V2-T1-09 test_runtime_file_writes_are_allowlisted` | Runtime writes only documented SQLite/log/config files under the per-user app directory; no repo, temp, desktop, or roaming writes |
| `V2-T1-10 test_t1_result_rejects_skips_and_empty_collection` | The stage runner returns nonzero for missing tests, zero collected tests, skipped/xfail tests, or any failure |

The real-device smoke checklist is in `WINDOWS-V2-SMOKE.md`.

## Later V2 acceptance list (not T1 scope)

These tests belong to their accepted plan modules and must not be pulled into
the Windows camera slice:

- `anonymous-tracking`: sticky anonymous ID across temporary occlusion and a
  later adult session; match-confidence floor; 30-day expiry; delete one/all;
  Windows-current-user encrypted templates; no names/images/crops.
- `sensitivity-alerts`: High and Low use one versioned configuration; same
  privacy/match floors; High changes timing only; brief movement resolves;
  yellow always precedes red; profile locks after Start.
- `hand-raising`: deterministic anonymous-ID and room-level event counts using
  synthetic keypoints or consenting adult fixtures only.
- `session-recap`: live teacher-only state, immediate hide, Stop-to-recap,
  uncertainty/support wording, no punitive ranking, deletion controls.
- `seated-support` and `off-seat`: start only after the adult beta gates in the
  accepted plan; never represent a heuristic as fact.

## Privacy threat model for the first slice

### Trust boundaries and assets

- USB camera/driver into the process: untrusted device frames and metadata.
- Browser into loopback FastAPI: untrusted local requests; dashboard contents
  are sensitive even though they are not public on the network.
- Process into filesystem: frames are sensitive biometric source material;
  runtime configuration and future templates/events need strict allowlists.
- Dependency/install boundary: unpinned native wheels and model licences can
  change behaviour, network activity, and redistribution rights.

### Abuse cases and mandatory controls

- A wrong camera or virtual camera is opened: enumerate, show selection, require
  an explicit index, and record only device index/backend in smoke evidence.
- A frame leaks through debug/crash/cache code: prohibit `imwrite`,
  `VideoWriter`, screenshots, face crops, temp media, and frame-bearing logs;
  assert filesystem deltas and write calls.
- A local service is exposed to the LAN: hard-code and test `127.0.0.1`; reject
  wildcard and LAN binds.
- A dependency phones home: install may use the network only when documented;
  runtime checks execute with outbound sockets blocked.
- A student is used for testing: stage T1 and this checklist are adult beta
  only; fixtures are synthetic or consenting adults.
- Future anonymous templates are copied: use Windows current-user DPAPI (do not
  use machine-wide scope), expiry/deletion, and never store the key beside the
  database. Template implementation is later than T1.

## T1 first implementation slice

T1 implements only this vertical path:

1. A no-admin `install.ps1 -CheckOnly` preflight and per-user environment path.
2. Camera inventory plus explicit USB camera index selection.
3. A bounded in-memory open/read/release adapter with permission diagnostics.
4. `run.bat --smoke-test` starting only `127.0.0.1`, checking health, and
   shutting down cleanly.
5. The ten `V2-T1-*` tests above, including real-device no-frame-write proof.

T1 must not implement face matching, persistence, sensitivity, alerts, hand
raising, recap, or student use. The first passing slice ends after Windows +
USB camera + loopback-only + zero frame writes.

## Official sources used for this delta

- Python 3.11 virtual environments: Windows environments use `Scripts`, can be
  invoked by full interpreter path without activation, and are inherently
  non-portable: https://docs.python.org/3.11/library/venv.html
- OpenCV 4.9 `VideoCapture`: camera index and preferred backend are explicit;
  `isOpened`, `read`, `getBackendName`, and `release` provide the smoke surface:
  https://docs.opencv.org/4.9.0/d8/dfe/classcv_1_1VideoCapture.html
- Windows camera privacy: denial must be distinguished and can direct the user
  to `ms-settings:privacy-webcam`:
  https://learn.microsoft.com/en-us/windows/apps/develop/camera/camera-privacy-setting
- PowerShell execution policy: Process scope is transient and Group Policy has
  higher precedence:
  https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies
- Uvicorn binding: default is `127.0.0.1`; `0.0.0.0` exposes the app on the
  local network: https://www.uvicorn.org/settings/
- Windows DPAPI: absent `CRYPTPROTECT_LOCAL_MACHINE`, protected data is normally
  decryptable only by the same logged-on user on the same computer:
  https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata
- pytest exit codes: pass, failure, interruption, internal error, usage error,
  no-tests-collected, and warning overflow are distinct outcomes:
  https://docs.pytest.org/en/stable/reference/exit-codes.html
