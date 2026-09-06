# Classroom Mirror — Audit report

**Date:** 2026-09-06
**Type:** Diagnostic audit (not a rewrite). Code changes were kept to this
single new file.
**Repo state audited:** commit `f381337` ("Add macOS V2 camera runtime"),
branch `main`.

---

## 0. Plain-language diagnosis (read this first)

You said the project is "not doing well" but didn't say why. After reading every
file and running every check that does not need a physical webcam, here is the
most likely reason it *feels* stuck:

**Almost all of the effort so far has gone into rules, contracts, and safety
scaffolding — not into the actual product a teacher would use.** The repository
is unusually disciplined about *what must not be built wrong* (privacy gates,
"fail-closed" test harnesses, byte-for-byte contract preservation), but the
features that make Classroom Mirror V2 *a thing a teacher opens and benefits
from* — anonymous sticky numbers, High/Low sensitivity, yellow/red fidget cues,
the end-of-class recap — **do not exist yet in any form.**

Concretely:

- The only new V2 capability that runs is *"open the selected camera, prove no
  image is saved, then stop."* That is a safety pre-check, not a feature.
- Even that camera slice **only actually works on macOS.** The product is
  officially aimed at **Windows** (see `V2-DELTA.md` and `CONTRACT.md`), yet the
  Windows launcher is a deliberate stub that always exits with a "NOT RUN"
  code.
- Meanwhile there is a *complete, working* older app (V1) sitting in the repo
  that has been declared "not the product." So the thing that works isn't wanted,
  and the thing that's wanted barely exists.

So the project is not broken in a "there's a crashing bug" sense. It is stuck in
a **"scaffolding is 90% of the code, product is ~5% done, and the two versions
create confusion"** sense. The good news: the privacy foundation is genuinely
solid, and there are no signs the tool is doing anything creepy today. The next
moves are about **building one visible teacher feature end-to-end** and
**removing V1/V2 ambiguity** — both bounded and listed in Section 4.

---

## 1. What works today

These were verified by actually running them on this machine (Linux, headless,
no webcam). Commands and raw output are in the Appendix.

| Area | Status | Evidence |
|---|---|---|
| **T0 readiness gate** (`check-v2.py --stage t0`) | ✅ Passes | 3/3 tests; confirms the signed V1 contract is unchanged and the V2 conflict is documented. |
| **macOS/shared camera logic gate** (`check-v2.py --stage t1-mac`) | ✅ Passes | 9/9 tests; camera inventory, single-index open, release-on-failure, loopback-only bind, and "no frame-writing API" all proven with fake devices. |
| **T1 Windows gate** (`check-v2.py --stage t1`) | ✅ Correctly *fails closed* | Reports the 5 missing acceptance tests and exits non-zero, exactly as documented. This is intended behaviour, not a bug. |
| **Implemented V2 Windows safety tests** | ✅ 6/6 pass | `pytest v2_tests/test_windows_runtime.py`: loopback-only bind, outbound-network refusal, allowlisted file writes, `install.ps1` is read-only, gate rejects skips/empty collection. |
| **V1 measurement logic** | ✅ 4/4 pass | `pytest tests/test_heuristics.py`: hand-raise counting, time-at-spot, movement buckets, whole-class aggregates still work on synthetic data. |
| **Windows launcher foundation** | ✅ Behaves as designed | `run.bat`→`v2_runtime.launcher` validates args, enforces `127.0.0.1`, and returns exit code `4` = "NOT RUN (camera increment not built)". |
| **Privacy boundary code** | ✅ Strong | `v2_runtime/policy.py` refuses any non-loopback bind, refuses outbound sockets before the socket call, and refuses any write outside a tiny allowlist of non-media files. |

**Key positive finding for your peace of mind:** *nothing in the current code
performs facial recognition, stores face templates, saves frames/video, or sends
data off the machine.* The camera runtime (`v2_runtime/camera.py`) has no
`imwrite`, `VideoWriter`, or `imencode` calls, and a test enforces that. The
local-only / no-surveillance promise is upheld by the code *as it stands today.*

---

## 2. What is incomplete, broken, or misleading

### 2a. Incomplete — the actual product is essentially unstarted

None of the four headline V2 features exist in code:

- **Anonymous sticky face numbers** — not implemented (only planned in
  `CONTRACT.md` / `V2-DELTA.md`).
- **High/Low sensitivity** — not implemented.
- **Yellow-then-red fidget/movement cues** — not implemented.
- **End-of-class recap** — not implemented.

What exists on the V2 path is *only* the camera-open/close safety slice ("T1")
and, on Windows, not even that (see 2b). The teacher dashboard, the Start
configuration screen, the live private flags, and Stop→recap are all absent.

### 2b. The stated target platform is the least-finished one

`CONTRACT.md` and `V2-DELTA.md` say V2 targets **Windows 10/11 x64**. But:

- `v2_runtime/launcher.py` (the Windows entry point behind `run.bat`) is an
  explicit foundation stub. It prints *"NOT RUN: physical-camera
  open/read/release is owned by the next T1 increment."* and returns exit code
  `4`. It never opens a camera.
- The **only** working camera runtime is `v2_runtime/mac_launcher.py` (macOS),
  which does open the selected camera, read frames in memory, and serve a
  loopback page.

So the platform you intend to ship first (Windows) is behind the platform you're
not prioritising (macOS). This is worth an explicit decision (Section 4).

### 2c. `check-v2.py --stage t1` can never pass yet, by construction

The gate requires ten acceptance tests `V2-T1-01`…`V2-T1-10` to exist in
`v2_tests/test_windows_runtime.py`. Only five exist (01, 06, 07, 09, 10). The
five that actually prove a *real camera works* (02 inventory selects a non-default
device, 03 missing/denied camera diagnostics, 04 selected camera reads frames,
05 no-frame-write proof, 08 `run.bat` smoke) are **not written**. This is
documented and intended ("fails closed"), but it means: *there is currently no
path by which the Windows product can be declared working.* That is the single
biggest blocker to shipping.

### 2d. Misleading documentation

- **`SETUP.md` claims demo data ships:** *"The app comes with a little made-up
  demo data (a pretend child 'L-7')…"* There is **no seeding code** anywhere in
  `app/` — `L-7` exists only inside `tests/fixtures.py`. A teacher who installs
  V1 and opens it will see **empty reports**, contradicting the guide. (Minor,
  and V1 is historical, but it will confuse anyone who follows `SETUP.md`.)
- **`.claude/launch.json`** hard-codes a personal absolute path
  (`/Volumes/M2 Media/Coding Dwayne/Claude/classroom-mirror/.venv/bin/python`).
  It launches the **V1** app (`app.main`) and won't work on any other machine.
  It's dev cruft that also points a new contributor at the wrong (V1) entry
  point.
- **Version pins are unverified.** `requirements-v2-runtime.txt` pins exact
  versions (e.g. `opencv-python==4.14.0.94`, `fastapi==0.141.1`) but there is no
  lockfile hash and no CI proving they resolve/install; `MAC-V2-SMOKE.md` records
  a *single* manual macOS install. `requirements.txt` (V1) still uses lower
  bounds only (`ultralytics>=8.3`, `opencv-python>=4.9`), which the contract
  itself flags as a pre-beta blocker.

### 2e. Nothing runs "out of the box" for a non-expert

- There is no `.venv`, no `.venv-mac-v2`, and no pose model (`*.pt`) checked in
  (correctly git-ignored). So both `./check` (V1) and `./run.command` (V1) print
  "not installed", and `./run-v2.command` (macOS V2) needs `./install-v2-mac.sh`
  + Python 3.11 first. On Windows, `run.bat` needs a `.venv` that no committed
  script creates (`install.ps1` is `-CheckOnly` and refuses to install). **There
  is currently no committed way to get a runnable Windows environment.**

---

## 3. V1 vs V2 confusion risks

The repository holds two products side by side, and a non-expert can easily run
or trust the wrong one.

| Confusion | Where it bites |
|---|---|
| **Two of everything.** `app/camera.py` vs `v2_runtime/camera.py`; `run.command` (V1) vs `run-v2.command` (V2); `install.sh` (V1) vs `install-v2-mac.sh`/`install.ps1` (V2); `requirements.txt` vs `requirements-v2-runtime.txt`; `check` vs `check-v2.py`. | A teacher double-clicking `run.command` launches the **cancelled V1** pose app, not V2. |
| **The default double-click is V1.** `run.command` → `app.main` (LIMS/zones/pose). `.claude/launch.json` also points at V1. | The "obvious" way to start the app is the wrong product. |
| **The working demo is V1.** V1 has real reports, a real UI, and passing measurement logic. V2 has a camera pre-check. A quick look could give a false impression that "the app works" when the *V2 product* does not. | Progress can be over-estimated. |
| **A real contract conflict is unresolved on paper only.** V1 criterion 2 bans biometric templates; V2 *requires* local anonymous face templates. `V2-DELTA.md` names this clearly, but it is not yet reconciled in code (because no template code exists). When someone starts the anonymous-ID slice, they must not "make V1 green" or silently reinterpret the signed contract. | Future privacy regression risk. |

**Mitigation direction (see Section 4):** either archive V1 into a clearly-named
subfolder/branch, or make the V1 entry points refuse to launch and redirect to
V2, so there is exactly one "obvious" thing to run.

---

## 4. Highest-leverage next fixes (prioritized and bounded)

Ordered by "most product value / least risk" first. Each is scoped to be small.

### P1 — Decide and state the platform for the first beta *(decision, ~0 code)*
Windows is the contractual target but the least-built. Either (a) commit to
Windows and prioritise the Windows camera increment (P2), or (b) make macOS the
first beta since its camera slice already runs, and downgrade Windows to
"next." Write the decision in `README.md`. Everything below depends on it.

**Decided 2026-09-06 — option (b): macOS is the first beta; Windows is next
(deprioritised, not abandoned).** Rationale: the macOS camera slice already
runs, so it is the fastest path to a real beta. The decision is now stated in
`README.md` ("Current implementation status") and `V2-DELTA.md` (dated update
note). P2 below now targets the Windows increment as the follow-on work.

### P2 — Finish one real camera increment on the chosen platform *(bounded)*
Implement the five missing acceptance tests and the code they cover:
`V2-T1-02/03/04/05/08` (device inventory selects a non-default index; clear
missing/denied diagnostics; selected camera reads in-memory frames and releases;
no image/video/frame bytes written; `run.bat`/launcher smoke uses the selected
index and exits cleanly). On macOS the runtime already does most of this —
porting to Windows is mostly the OpenCV backend + `run.bat` wiring. **Outcome:**
`check-v2.py --stage t1` can pass for the first time, giving you a defensible
"the camera part works" milestone.

### P3 — Make the environment installable on the target platform *(bounded)*
Today `install.ps1` is `-CheckOnly` and refuses to create the `.venv` that
`run.bat` needs. Add a real per-user install path (still no admin, still
documented network use at install only), or clearly document the manual
`py -m venv .venv && .venv\Scripts\pip install -r requirements-v2-runtime.txt`
steps. Without this, no one but the author can run the Windows product.

### P4 — Collapse the V1/V2 confusion *(bounded, high clarity payoff)*
Move the V1-only files (`app/`, `tests/`, `run.command`, `install.sh`, `check`,
`SETUP.md`, `HUMAN-CHECKS.md`) into an `archive/v1/` folder **or** make
`run.command`/`install.sh` print
"This is the retired V1 build — see README" and exit. Delete or fix
`.claude/launch.json`. Keep the signed `CONTRACT.md` where it is. **Outcome:**
exactly one obvious way to install and run the current product.

### P5 — Fix the misleading docs *(tiny)*
- Remove/correct the "ships with demo data L-7" claim in `SETUP.md` (or add a
  one-line seeder if you want V1 demos to actually exist).
- Note in `README.md` that Windows currently has no committed installer.

### P6 — Then, and only then, build the first *teacher-visible* V2 feature *(larger)*
Per `V2-DELTA.md`'s own ordering, the "movement foundation" slice: Start screen
(pick camera + High/Low), a private live view showing anonymous numbers with
yellow→red movement cues, Stop, and a plain recap. This is the first thing that
will make the project *feel* like it's working. It is deliberately last here
because it should sit on top of a camera slice that actually runs (P2) and an
installable environment (P3).

**Suggested "definition of not-stuck":** a teacher on the target OS can run one
command, pick a camera, see anonymous numbers with a yellow/red cue for ~1
minute, press Stop, and read a recap — with the existing privacy tests still
green.

---

## 5. Security & privacy assessment (vs the local-only / no-surveillance contract)

**Overall: the contract is being honoured by the current code.** This is the
strongest part of the project. Findings, from reassuring to watch-items:

### Upheld today
- **No off-machine traffic at runtime.** `v2_runtime/policy.py`
  `RuntimeNetworkPolicy` records and refuses any non-loopback destination
  *before* calling the socket connector; `validate_bind_host` accepts only the
  literal `127.0.0.1` (rejects `0.0.0.0`, `::`, `::1`, `localhost`, LAN IPs).
  Verified by tests.
- **No frames/video/crops written.** `v2_runtime/camera.py` reads frames into
  RAM only; a test forbids `imwrite`/`VideoWriter`/`imencode` in that module.
  `RuntimeFilePolicy` allows writes to only six non-media files under
  `%LOCALAPPDATA%\ClassroomMirror` and blocks traversal, absolute paths, and
  symlink escapes.
- **No facial recognition / biometric templates exist yet.** The contractual
  conflict about anonymous templates is *documented but not yet built*, so there
  is no biometric data path in the code today.
- **Adult-only smoke discipline.** Both smoke checklists
  (`WINDOWS-V2-SMOKE.md`, `MAC-V2-SMOKE.md`) are explicit: adults only, no
  students, retain text metadata only (index/backend/frame-count), never frames,
  serial numbers, or names.
- **No elevation / policy tampering on Windows.** `install.ps1` is read-only and
  tests forbid `Set-ExecutionPolicy`, `pip install`, `winget`, `choco`, and file
  writes in it.

### Watch-items (not violations today, but flagged for the roadmap)
1. **The anonymous-template slice is the real privacy cliff.** When P6/anonymous
   IDs are built, "anonymous" face templates are still biometric data. The plan
   already specifies the right controls (Windows DPAPI *current-user* scope, a
   match-confidence floor, 30-day expiry, delete-one/all, key stored away from
   the DB, no names/crops). **Do not implement templates without those controls
   landing in the same slice, and do not weaken the signed `CONTRACT.md` to make
   a scoreboard green.** This is the single most important future guardrail.
2. **Dependency provenance is unproven.** Pinned versions in
   `requirements-v2-runtime.txt` have no hash lock and no CI-verified install;
   `requirements.txt` (V1) pulls **AGPL-licensed** Ultralytics YOLO (already
   noted in `LATER.md` as needing an Apache-2.0 replacement before distribution).
   A dependency that changes behaviour or "phones home" would undercut the
   local-only promise. Lock exact versions + hashes and add an install/import
   check to CI before beta.
3. **The dashboard is sensitive even on loopback.** `mac_launcher.py` sets good
   headers (`CSP default-src 'none'`, `no-store`, `X-Frame-Options: DENY`). Keep
   that discipline for every future page; the recap/live views must never be
   projectable or screen-shareable by default (the smoke docs already say so).
4. **No automated CI.** All the guarantees above are enforced by tests that only
   run when someone remembers to run them. A tiny GitHub Actions workflow running
   `check-v2.py --stage t0`, `--stage t1-mac`, and `pytest v2_tests` on every
   push would make the privacy guarantees continuous rather than manual.

---

## 6. Bottom line

- **Working and trustworthy:** the privacy/safety foundation, the V1 measurement
  logic, and the macOS camera pre-check. No surveillance behaviour exists in the
  code.
- **The reason it feels stuck:** the product features that justify V2 are
  unstarted, the target platform (Windows) is the least-built, there's no
  installable Windows environment, and two overlapping product versions create
  confusion.
- **Fastest way to feel progress:** pick the platform (P1), make one camera
  increment actually pass the gate (P2), make it installable (P3), remove the
  V1/V2 ambiguity (P4), then build the first teacher-visible feature (P6).

---

## Appendix — checks run for this audit

Run on Linux, headless, no webcam. `python3` = 3.12; the project prefers 3.11,
but every check below is dependency-light and ran unchanged.

```
$ python check-v2.py --stage t0
Ran 3 tests ... OK            (exit 0)

$ python check-v2.py --stage t1-mac
Ran 9 tests ... OK            (exit 0)

$ python check-v2.py --stage t1 --camera-index 1
T1 acceptance suite is incomplete; missing required criteria:
- V2-T1-02: test_camera_inventory_can_select_non_default_device
- V2-T1-03: test_missing_or_denied_camera_fails_clearly
- V2-T1-04: test_selected_camera_reads_frames_in_memory_and_releases
- V2-T1-05: test_camera_smoke_writes_no_frame_image_or_video
- V2-T1-08: test_run_bat_smoke_uses_selected_camera_and_exits
                              (exit 1 — intended fail-closed)

$ python -m pytest -q v2_tests/test_windows_runtime.py
6 passed                      (exit 0)

$ python -m pytest -q tests/test_heuristics.py
4 passed                      (exit 0)

$ LOCALAPPDATA=/tmp/localappdata python -m v2_runtime.launcher \
      --smoke-test --camera-index 1 --seconds 10
NOT RUN: physical-camera open/read/release is owned by the next T1 increment.
                              (exit 4 — intended foundation stub)
```

Not run (require a physical webcam or heavy/AGPL model downloads, out of scope
for a headless audit): the real-device smoke in `WINDOWS-V2-SMOKE.md` /
`MAC-V2-SMOKE.md`, and the full V1 `./check` scoreboard (needs OpenCV +
Ultralytics + the pose model).
