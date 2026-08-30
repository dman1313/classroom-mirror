"""Yellow always precedes red. Brief movement does not stick."""

from __future__ import annotations

from dataclasses import dataclass

from .sensitivity import SensitivityProfile

BAND_NONE = "none"
BAND_YELLOW = "yellow"
BAND_RED = "red"


@dataclass
class AlertState:
    band: str = BAND_NONE
    above_since: float | None = None
    below_since: float | None = None
    yellow_since: float | None = None
    label: str = ""


SUPPORT_YELLOW = "possible support needed — more movement than usual (uncertain)"
SUPPORT_RED = "possible support needed — sustained movement (uncertain)"


def update_alert(
    state: AlertState,
    t: float,
    speed: float | None,
    profile: SensitivityProfile,
) -> AlertState:
    moving = speed is not None and speed >= profile.speed_threshold
    if moving:
        state.below_since = None
        if state.above_since is None:
            state.above_since = t
        held = t - state.above_since
        if state.band == BAND_NONE and held >= profile.yellow_hold:
            state.band = BAND_YELLOW
            state.yellow_since = t
            state.label = SUPPORT_YELLOW
        elif state.band == BAND_YELLOW:
            if state.yellow_since is None:
                state.yellow_since = t
            if t - state.yellow_since >= profile.red_hold:
                state.band = BAND_RED
                state.label = SUPPORT_RED
        elif state.band == BAND_RED:
            state.label = SUPPORT_RED
        return state

    state.above_since = None
    if state.band == BAND_NONE:
        state.below_since = None
        state.label = ""
        return state
    if state.below_since is None:
        state.below_since = t
    if t - state.below_since >= profile.recover_hold:
        if state.band == BAND_RED:
            state.band = BAND_YELLOW
            state.yellow_since = t
            state.label = SUPPORT_YELLOW
            state.below_since = None
        else:
            state.band = BAND_NONE
            state.yellow_since = None
            state.label = ""
            state.below_since = None
    return state
