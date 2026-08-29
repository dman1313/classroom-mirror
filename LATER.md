# LATER — postponed ideas (raw material for version 2)

> **Historical V1 backlog.** The accepted V2 direction now lives in
> [V2-DELTA.md](V2-DELTA.md). In particular, Windows is no longer postponed.
> Named face-tagging and emotion/engagement scoring remain rejected; V2 permits
> only local anonymous templates under its explicit adult-beta privacy contract.

Roughly ordered by value. Cut during the interview or discovered during the build — nothing here is lost, only postponed.

- Seated-count for Mode 2 (room-level "how many children are seated" metric — cut from v1 to keep whole-class metrics simple and robust).
- Windows build + install guide (v1 targets Dwayne's Mac).
- Swap the AGPL-licensed pose model (Ultralytics YOLO11) for an Apache-2.0 one (e.g. RTMPose) if this ever becomes a distributed product.
- CSV export of session numbers for spreadsheets.
- Demo mode: run against a sample video file so teachers can try the app with no camera (discovered while verifying the camera-missing path).
- French-language UI.
- Multi-camera / second-angle support for occlusion.
- Per-child tracking of every child via LIMS rows in whole-class mode — **deliberately rejected for v1** (pseudonymised is still personal data of minors; revisit only with a DPIA and school sign-off in hand).
- Original idea (face-tagging named children, attention/engagement scoring) — **rejected permanently**: biometric ID of minors + emotion inference in education are legally prohibited / indefensible.
