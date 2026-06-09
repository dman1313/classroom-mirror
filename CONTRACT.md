# CONTRACT — Classroom Mirror

**Signed:** 2026-06-09 (plan approved by Dwayne — the signing moment)
**Check command:** `./check` (run from this folder; prints the plain-English scoreboard, guardrails first)
**Rule:** Nothing ships unless every line is YES. The agent may never weaken, remove, or reinterpret a criterion. Only Dwayne amends this contract; every amendment is recorded at the bottom with a date and reason.

The tool: a local-only webcam app for a teacher's Mac with two modes —
**Mode 1** tracks agreed behaviours for designated, consented children (pseudonymous LIMS codes, zone-based, no faces) to see whether a support strategy is working.
**Mode 2** shows whole-class, aggregate-only patterns as a mirror for the teacher's own practice.

---

## A. Hard guardrails — tested FIRST every loop; a NO here outranks everything

1. **[AUTO] No camera frame or video is ever written to disk, and all data stays in one visible local folder.**
   How we'll prove it: full pipeline run on a generated test video → `data/` contains only `.sqlite` / `.html` files; no image or video files anywhere; all writes land inside `data/`.
2. **[AUTO] No facial recognition, no biometric template.**
   How we'll prove it: dependency list checked against an allowlist (no face-recognition libraries); database schema-lock test proves no embedding/template column exists.
3. **[AUTO] No inference of emotion, attention, or character — anywhere.**
   How we'll prove it: schema-lock test (there is nowhere to store such a thing) + report templates are fixed neutral strings scanned against a banned-terms list.
4. **[AUTO] A child's name cannot enter the system.**
   How we'll prove it: zero free-text fields; LIMS and class codes validated to short letter/digit patterns; schema has no name column.
5. **[AUTO] No traffic leaves the machine while the app runs.**
   How we'll prove it: integration test runs a session with all non-loopback network connections blocked — completes without a single attempt. (UI is localhost-only; the one-time pose-model download happens at install, never at runtime.)
6. **[AUTO] Mode 1 refuses to start without recorded consent for that specific LIMS code.**
   How we'll prove it: start-without-consent test → refused with a plain-English message.
7. **[AUTO] Mode 2 is aggregate-only by construction.**
   How we'll prove it: schema-lock — whole-class tables have no LIMS/per-child column at all.
8. **[AUTO] Erasure works.**
   How we'll prove it: "delete everything for LIMS X" and "delete session" tests — insert, delete, full scan finds nothing.

## B. Core features

9. **[AUTO] Mode 1 counts hand-raises in the designated zone within ±1** on every test fixture (synthetic keypoint streams with known truth).
10. **[AUTO] Mode 1 measures "time at their spot" within ±5%** on fixtures.
11. **[AUTO] Mode 1 movement level (low/medium/high per minute) matches fixture truth.**
12. **[AUTO] Mode 1 before/after report** compares baseline vs strategy sessions for one LIMS code in neutral plain English — numbers and changes, no judgments.
13. **[AUTO] Mode 2 session summary** shows class hand-raise total, movement timeline, and bodies-detected count from fixture input.
14. **[AUTO] Any two Mode 2 sessions can be compared side by side.**
15. **[HUMAN] Live trial (adults only):** Dwayne sits in front of the camera, raises his hand 3 times → the app shows 3; he leaves his zone for about a minute → at-spot time drops accordingly.
16. **[HUMAN] Zone setup takes under a minute:** draw a box, type a LIMS code, confirm consent — guided only by on-screen hints.
17. **[HUMAN] Any report is readable in under a minute** and makes sense to a non-coder.

## C. General

18. **[INSPECT + HUMAN] Starts on Dwayne's Mac** via double-click (`run.command`) or one pasted command; `SETUP.md` written for a non-coder.
19. **[HUMAN] Dwayne runs `./check` himself** and sees the plain-English scoreboard (guardrails first).

---

## Honesty clause

Fixtures prove the mechanism, not classroom-grade accuracy. Pose detection in a crowded room is noisy (occlusion, distance, lighting). The live adult trial validates end-to-end behaviour; real-classroom tuning happens after handover, after the DPIA, and only with the school's sign-off. **Build and test with made-up data only — no real children's data, ever, during development.**

## Real-world homework (not code — travels with the project)

- DPIA (data-protection impact assessment) before any real classroom use; school DPO/leadership sign-off.
- Parental consent process for any Mode 1 child — the app only records that consent exists; obtaining it is human work.
- CNIL guidance check (France is the strictest jurisdiction for cameras in schools).

## Amendments

_None yet. Format: date — what changed — one-line reason — approved by Dwayne._
