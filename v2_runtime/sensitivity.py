"""Versioned High / Low sensitivity profiles for the movement dashboard.

Per the accepted V2 plan (V2-DELTA.md, "sensitivity-alerts"):

* High and Low share one versioned configuration and the same privacy floors.
* High changes *timing only* - it flags sustained movement sooner. It never
  lowers a movement threshold or changes what counts as movement.
* Yellow always precedes red.
* Brief movement resolves (levels step back down when movement settles).

The profile is chosen before Start and is locked for the whole session.
"""

from __future__ import annotations

from dataclasses import dataclass


PROFILE_VERSION = "2026.09-movement-1"

# Thresholds are per-frame movement (how far an anonymous number travels on
# screen, in normalised 0..1 units), smoothed over recent frames. They describe
# *amount of movement*, never contrast, identity, or meaning.
CALM_ENERGY = 0.004
YELLOW_ENERGY = 0.010
RED_ENERGY = 0.025


@dataclass(frozen=True)
class SensitivityProfile:
    """Shared thresholds; only the sustain/resolve *timing* differs by name."""

    name: str
    version: str
    calm_energy: float
    yellow_energy: float
    red_energy: float
    yellow_sustain_frames: int
    red_sustain_frames: int
    resolve_frames: int

    @property
    def key(self) -> str:
        return self.name.lower()


_HIGH = SensitivityProfile(
    name="High",
    version=PROFILE_VERSION,
    calm_energy=CALM_ENERGY,
    yellow_energy=YELLOW_ENERGY,
    red_energy=RED_ENERGY,
    yellow_sustain_frames=3,
    red_sustain_frames=4,
    resolve_frames=6,
)

_LOW = SensitivityProfile(
    name="Low",
    version=PROFILE_VERSION,
    calm_energy=CALM_ENERGY,
    yellow_energy=YELLOW_ENERGY,
    red_energy=RED_ENERGY,
    yellow_sustain_frames=9,
    red_sustain_frames=12,
    resolve_frames=14,
)

PROFILES: dict[str, SensitivityProfile] = {_HIGH.key: _HIGH, _LOW.key: _LOW}


def profile_for(name: str) -> SensitivityProfile:
    """Return the versioned profile for 'high' or 'low' (case-insensitive)."""
    try:
        key = name.strip().lower()
    except AttributeError as exc:
        raise ValueError("sensitivity name must be a string") from exc
    if key not in PROFILES:
        raise ValueError("sensitivity must be 'High' or 'Low'")
    return PROFILES[key]
