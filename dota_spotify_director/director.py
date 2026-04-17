from __future__ import annotations

from dataclasses import replace
from typing import Dict, Optional

from .state_tracker import InferredState

PRIORITY = {
    'menu': 0,
    'hero_pick': 1,
    'calm_lane': 2,
    'early_game': 3,
    'late_game': 4,
    'teamfight': 5,
    'low_hp': 6,
    'dead': 7,
    'victory': 8,
    'defeat': 8,
}


class CinematicStateDirector:
    """Keep dramatic states on screen a little longer to avoid rapid oscillation."""

    def __init__(self, enabled: bool, hold_seconds: Dict[str, float] | None = None) -> None:
        self.enabled = enabled
        self.hold_seconds = hold_seconds or {
            'teamfight': 6.0,
            'low_hp': 3.5,
            'dead': 4.0,
        }
        self._held_state: Optional[str] = None
        self._held_until: float = 0.0

    def _priority(self, state_name: str) -> int:
        return PRIORITY.get(state_name, 0)

    def apply(self, state: InferredState, now_ts: float) -> InferredState:
        if not self.enabled:
            return state

        candidate = state.state_name
        hold_for = float(self.hold_seconds.get(candidate, 0.0))

        if hold_for > 0:
            self._held_state = candidate
            self._held_until = now_ts + hold_for
            return state

        if self._held_state and now_ts < self._held_until:
            held_priority = self._priority(self._held_state)
            candidate_priority = self._priority(candidate)
            if candidate_priority < held_priority:
                label_map = {
                    'teamfight': 'Cinema hold: teamfight',
                    'low_hp': 'Cinema hold: survival pressure',
                    'dead': 'Cinema hold: respawn window',
                }
                return replace(
                    state,
                    state_name=self._held_state,
                    details=label_map.get(self._held_state, state.details or 'Cinema hold'),
                )

        if self._held_state and now_ts >= self._held_until:
            self._held_state = None

        return state
