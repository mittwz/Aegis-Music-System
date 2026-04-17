from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FadeState:
    current_volume: int


class VolumeManager:
    def __init__(self, initial_volume: int, fade_step: int, mode: str = 'standard') -> None:
        self.state = FadeState(current_volume=initial_volume)
        self.fade_step = max(1, fade_step)
        self.mode = mode

    def _effective_step(self, current: int, target: int, state_name: str) -> int:
        step = self.fade_step
        if self.mode != 'cinema':
            return step

        intense_states = {'teamfight', 'low_hp', 'dead', 'victory', 'defeat'}
        recovery_states = {'menu', 'hero_pick', 'calm_lane', 'early_game', 'late_game'}

        if current > target:
            if state_name in intense_states:
                return max(step, int(round(step * 1.75)))
            return max(step, int(round(step * 1.35)))

        if current < target:
            if state_name in recovery_states:
                return max(1, int(round(step * 0.5)))
            return max(1, int(round(step * 0.75)))

        return step

    def next_step(self, target_volume: int, state_name: str = '') -> int:
        target_volume = max(0, min(100, int(target_volume)))
        current = self.state.current_volume
        if current == target_volume:
            return current

        step = self._effective_step(current, target_volume, state_name)
        if current < target_volume:
            current = min(current + step, target_volume)
        else:
            current = max(current - step, target_volume)

        self.state.current_volume = current
        return current
