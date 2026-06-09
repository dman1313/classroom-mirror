"""`./check` — runs every test and prints the plain-English scoreboard.

This is the human's independent proof: it can be run today or in six months,
after any change, without the agent present.
"""
import os
import sys


def main():
    import pytest

    here = os.path.dirname(os.path.abspath(__file__))
    print("Running every check — this takes a minute the first time...\n")
    pytest.main(["-q", "--no-header", "-p", "no:cacheprovider", here])

    from tests.criteria import CRITERIA, OUTCOMES, EVIDENCE

    bar = "=" * 74
    print()
    print(bar)
    print(" CLASSROOM MIRROR — SCOREBOARD            (the contract: CONTRACT.md)")
    print(bar)

    auto_total = auto_yes = human_pending = 0
    current_group = None
    failed_guardrail = False

    for num in sorted(CRITERIA):
        group, tag, text = CRITERIA[num]
        if group != current_group:
            current_group = group
            label = {
                "GUARDRAIL": "HARD GUARDRAILS — a NO here outranks everything",
                "CORE": "CORE FEATURES",
                "GENERAL": "GENERAL",
            }[group]
            print(f"\n {label}")

        if "AUTO" in tag and tag == "AUTO":
            auto_total += 1
            outcomes = OUTCOMES.get(num, [])
            passed = bool(outcomes) and all(ok for ok, _, _ in outcomes)
            if passed:
                auto_yes += 1
                print(f"  {num:>2}. YES  {text}")
                if num in EVIDENCE:
                    print(f"       proof: {EVIDENCE[num]}")
            else:
                if group == "GUARDRAIL":
                    failed_guardrail = True
                print(f"  {num:>2}. NO   {text}")
                if not outcomes:
                    print("       reason: no test ran for this criterion")
                else:
                    for ok, name, fail in outcomes:
                        if not ok:
                            print(f"       reason: {fail or name}")
        else:
            human_pending += 1
            who = "your sign-off" if "HUMAN" in tag else "inspection"
            print(f"  {num:>2}. PENDING ({who})  {text}")

    print()
    print("-" * 74)
    print(f" {auto_yes} of {auto_total} automatic criteria are YES."
          f" {human_pending} human checks await sign-off (see HUMAN-CHECKS.md).")
    if failed_guardrail:
        print(" A GUARDRAIL IS FAILING. Nothing else matters until it is YES.")
    print("-" * 74)

    sys.exit(0 if auto_yes == auto_total else 1)


if __name__ == "__main__":
    main()
