"""Input validation — guardrail 4: a child's name cannot enter the system.

The only identifiers the app accepts are short letter/digit codes. There are
no free-text fields anywhere, so there is nowhere to type a name or a note.
"""
import re

# 1-12 chars, letters/digits/hyphen, must start with a letter or digit.
CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,11}$")

# Mirrors CODE_RE for the browser <input pattern=...> attribute.
CODE_HTML_PATTERN = "[A-Za-z0-9][A-Za-z0-9-]{0,11}"
CODE_MAXLENGTH = 12


def validate_lims(code: str) -> str:
    code = (code or "").strip()
    if not CODE_RE.match(code):
        raise ValueError(
            "A LIMS code must be 1-12 letters, digits or hyphens — "
            "never a name or a sentence."
        )
    return code


def validate_class_code(code: str) -> str:
    code = (code or "").strip()
    if not CODE_RE.match(code):
        raise ValueError(
            "A class code must be 1-12 letters, digits or hyphens (like 6B or Y4-RED)."
        )
    return code
