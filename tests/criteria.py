"""The contract's 19 criteria, exactly as signed in CONTRACT.md.

Tests map to criteria with @pytest.mark.criterion(n). The scoreboard prints
every criterion — AUTO ones from test outcomes, HUMAN/INSPECT ones as
pending sign-offs.
"""

CRITERIA = {
    1: ("GUARDRAIL", "AUTO", "No camera frame or video is ever written to disk; all data stays in data/"),
    2: ("GUARDRAIL", "AUTO", "No facial recognition, no biometric template"),
    3: ("GUARDRAIL", "AUTO", "No inference of emotion, attention, or character — anywhere"),
    4: ("GUARDRAIL", "AUTO", "A child's name cannot enter the system"),
    5: ("GUARDRAIL", "AUTO", "No traffic leaves the machine while the app runs"),
    6: ("GUARDRAIL", "AUTO", "Mode 1 refuses to start without recorded consent for that LIMS code"),
    7: ("GUARDRAIL", "AUTO", "Mode 2 is aggregate-only by construction (no per-child column exists)"),
    8: ("GUARDRAIL", "AUTO", "Erasure works: delete a LIMS code or a session and nothing remains"),
    9: ("CORE", "AUTO", "Mode 1 counts hand-raises in the designated zone within ±1 on fixtures"),
    10: ("CORE", "AUTO", "Mode 1 measures time at their spot within ±5% on fixtures"),
    11: ("CORE", "AUTO", "Mode 1 movement level per minute matches fixture truth"),
    12: ("CORE", "AUTO", "Mode 1 before/after report compares baseline vs strategy in neutral plain English"),
    13: ("CORE", "AUTO", "Mode 2 session summary shows class hand-raises, movement timeline, people in view"),
    14: ("CORE", "AUTO", "Any two Mode 2 sessions can be compared side by side"),
    15: ("CORE", "HUMAN", "Live trial (adults only): 3 real hand-raises show as 3; leaving the zone lowers at-spot time"),
    16: ("CORE", "HUMAN", "Zone setup takes under a minute, guided only by on-screen hints"),
    17: ("CORE", "HUMAN", "Any report is readable in under a minute and makes sense to a non-coder"),
    18: ("GENERAL", "INSPECT+HUMAN", "Starts on Dwayne's Mac via double-click (run.command); SETUP.md is non-coder friendly"),
    19: ("GENERAL", "HUMAN", "Dwayne runs ./check himself and sees this scoreboard"),
}

# Filled in by conftest hooks / tests at run time.
OUTCOMES = {}   # num -> list of (passed: bool, test_name: str, failure: str)
EVIDENCE = {}   # num -> one plain-English line of proof


def evidence(num: int, text: str):
    EVIDENCE[num] = text
