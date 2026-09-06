"""Versioned High/Low fidget sensitivity. Timing changes; privacy floors do not."""

from __future__ import annotations

from dataclasses import dataclass


PROFILE_VERSION = "v2.0"


@dataclass(frozen=True)
class SensitivityProfile:
    key: str
    version: str
    speed_threshold: float  # body-heights (or bbox-heights) per second
    yellow_hold: float  # seconds above threshold before yellow
    red_hold: float  # additional seconds on yellow before red
    recover_hold: float  # seconds below threshold before dropping a band


# High/Low share one speed floor. High only shortens yellow/red/recover timing.
_SPEED_THRESHOLD = 0.09

PROFILES = {
    "low": SensitivityProfile(
        key="low",
        version=PROFILE_VERSION,
        speed_threshold=_SPEED_THRESHOLD,
        yellow_hold=8.0,
        red_hold=16.0,
        recover_hold=4.0,
    ),
    "high": SensitivityProfile(
        key="high",
        version=PROFILE_VERSION,
        speed_threshold=_SPEED_THRESHOLD,
        yellow_hold=3.0,
        red_hold=7.0,
        recover_hold=2.0,
    ),
}


def get_profile(key: str) -> SensitivityProfile:
    normalized = (key or "").strip().lower()
    if normalized not in PROFILES:
        raise ValueError("sensitivity must be 'high' or 'low'")
    return PROFILES[normalized]
