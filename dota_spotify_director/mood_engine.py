from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .state_tracker import InferredState


@dataclass
class MoodDecision:
    state_name: str
    target_volume: int
    playlist_uri: Optional[str]
    playlist_name: str
    reason: str


class MoodEngine:
    def __init__(self, profile: Dict[str, Any], base_volume: int) -> None:
        self.profile = profile
        self.base_volume = base_volume

    def decide(self, state: InferredState) -> MoodDecision:
        entry = self.profile.get(state.state_name, {})
        target_volume = int(entry.get('volume', self.base_volume))
        playlist_uri = entry.get('playlist_uri')
        playlist_name = str(entry.get('playlist_name') or self._default_playlist_name(state.state_name))
        reason = str(entry.get('reason') or state.details or self._default_reason(state.state_name))

        if state.hp_ratio is not None and state.state_name == 'low_hp':
            if state.hp_ratio <= 0.14:
                target_volume = min(target_volume, 8)
                reason = 'Critical HP'
            elif state.hp_ratio <= 0.22:
                target_volume = min(target_volume, 10)
                reason = 'Low HP under pressure'

        return MoodDecision(
            state_name=state.state_name,
            target_volume=target_volume,
            playlist_uri=playlist_uri,
            playlist_name=playlist_name,
            reason=reason,
        )

    @staticmethod
    def _default_playlist_name(state_name: str) -> str:
        defaults = {
            'menu': 'Menu',
            'hero_pick': 'Draft',
            'early_game': 'Early Game',
            'calm_lane': 'Calm Lane',
            'teamfight': 'Teamfight',
            'low_hp': 'Tension',
            'dead': 'Respawn',
            'late_game': 'Late Game',
            'victory': 'Victory',
            'defeat': 'Defeat',
        }
        return defaults.get(state_name, 'Playlist')

    @staticmethod
    def _default_reason(state_name: str) -> str:
        defaults = {
            'menu': 'Dota menu',
            'hero_pick': 'Draft phase',
            'early_game': 'Game opening',
            'calm_lane': 'Map under control',
            'teamfight': 'Heavy combat inferred',
            'low_hp': 'Survival pressure',
            'dead': 'Hero is dead',
            'late_game': 'High-pressure late game',
            'victory': 'Victory confirmed',
            'defeat': 'Defeat confirmed',
        }
        return defaults.get(state_name, 'Game state change')
