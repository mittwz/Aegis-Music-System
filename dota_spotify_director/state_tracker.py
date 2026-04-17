from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class InferredState:
    state_name: str
    game_time_seconds: int = 0
    hp_ratio: Optional[float] = None
    in_game: bool = False
    details: str = ""


class StateTracker:
    """Infer a small set of music-oriented game states from the latest Dota 2 GSI payload."""

    def __init__(self, low_hp_threshold: float, critical_hp_threshold: float) -> None:
        self.low_hp_threshold = low_hp_threshold
        self.critical_hp_threshold = critical_hp_threshold
        self._teamfight_hold_until = 0.0

    def infer(self, payload: Dict[str, Any]) -> InferredState:
        if not payload:
            return InferredState(state_name='menu', in_game=False, details='Waiting for Dota payload')

        map_data = payload.get('map', {}) or {}
        player_data = payload.get('player', {}) or {}
        hero_data = payload.get('hero', {}) or {}
        draft_data = payload.get('draft', {}) or {}

        map_game_state = str(map_data.get('game_state') or '')
        activity_state = str(player_data.get('activity') or '')
        combined_state = ' '.join([map_game_state, activity_state]).strip()
        combined_lower = combined_state.lower()

        game_time = int(map_data.get('clock_time') or 0)
        hp_ratio = self._hp_ratio(hero_data)
        alive = self._is_alive(hero_data, player_data)

        if self._is_menu(combined_lower, map_data, player_data, hero_data):
            return InferredState(
                state_name='menu',
                in_game=False,
                details=self._label_for_state(combined_state, 'Dota menu'),
            )

        if self._is_hero_pick(combined_lower, draft_data, game_time):
            return InferredState(
                state_name='hero_pick',
                game_time_seconds=game_time,
                hp_ratio=hp_ratio,
                in_game=True,
                details=self._label_for_state(combined_state, 'Pre-game'),
            )

        if self._is_victory(combined_lower, map_data, game_time):
            return InferredState(
                state_name='victory',
                game_time_seconds=game_time,
                hp_ratio=hp_ratio,
                in_game=False,
                details=self._label_for_state(combined_state, 'Victory confirmed'),
            )

        if self._is_defeat(combined_lower, map_data, game_time):
            return InferredState(
                state_name='defeat',
                game_time_seconds=game_time,
                hp_ratio=hp_ratio,
                in_game=False,
                details=self._label_for_state(combined_state, 'Defeat confirmed'),
            )

        if not alive:
            return InferredState(
                state_name='dead',
                game_time_seconds=game_time,
                hp_ratio=hp_ratio,
                in_game=True,
                details='Hero is dead',
            )

        if hp_ratio is not None and hp_ratio <= self.critical_hp_threshold:
            return InferredState(
                state_name='low_hp',
                game_time_seconds=game_time,
                hp_ratio=hp_ratio,
                in_game=True,
                details='Critical HP',
            )

        if self._is_teamfight(payload, hp_ratio):
            return InferredState(
                state_name='teamfight',
                game_time_seconds=game_time,
                hp_ratio=hp_ratio,
                in_game=True,
                details='Teamfight inferred',
            )

        if hp_ratio is not None and hp_ratio <= self.low_hp_threshold:
            return InferredState(
                state_name='low_hp',
                game_time_seconds=game_time,
                hp_ratio=hp_ratio,
                in_game=True,
                details='Low HP',
            )

        if game_time >= 2400:
            return InferredState(
                state_name='late_game',
                game_time_seconds=game_time,
                hp_ratio=hp_ratio,
                in_game=True,
                details='Late game',
            )

        if 0 <= game_time <= 600:
            return InferredState(
                state_name='early_game',
                game_time_seconds=game_time,
                hp_ratio=hp_ratio,
                in_game=True,
                details='Early game',
            )

        return InferredState(
            state_name='calm_lane',
            game_time_seconds=game_time,
            hp_ratio=hp_ratio,
            in_game=True,
            details='Stable lane phase',
        )

    def _is_teamfight(self, payload: Dict[str, Any], hp_ratio: Optional[float]) -> bool:
        """Use conservative heuristics plus a short hold window for cinematic stability."""
        now = time.time()
        player_data = payload.get('player', {}) or {}
        hero_data = payload.get('hero', {}) or {}
        abilities = payload.get('abilities', {}) or {}

        kill_list = player_data.get('kill_list') or {}
        recently_damaged = bool(kill_list)
        silenced = bool(hero_data.get('silenced'))
        stunned = bool(hero_data.get('stunned'))

        mana = hero_data.get('mana')
        max_mana = hero_data.get('max_mana')
        mana_spent = (
            isinstance(mana, (int, float))
            and isinstance(max_mana, (int, float))
            and max_mana > 0
            and mana < 0.35 * max_mana
        )
        ability_on_cooldown = any(
            isinstance(v, dict) and v.get('cooldown') not in (None, 0)
            for v in abilities.values()
        ) if isinstance(abilities, dict) else False

        active_combat = recently_damaged or silenced or stunned or (mana_spent and ability_on_cooldown)
        hp_not_healthy = hp_ratio is None or hp_ratio <= 0.65

        if active_combat and hp_not_healthy:
            self._teamfight_hold_until = now + 6.0
            return True

        return now < self._teamfight_hold_until

    @staticmethod
    def _label_for_state(raw_state: str, fallback: str) -> str:
        mapping = {
            'DOTA_GAMERULES_STATE_HERO_SELECTION': 'Hero selection',
            'DOTA_GAMERULES_STATE_STRATEGY_TIME': 'Strategy time',
            'DOTA_GAMERULES_STATE_TEAM_SHOWCASE': 'Team showcase',
            'DOTA_GAMERULES_STATE_PRE_GAME': 'Pre-game',
            'DOTA_GAMERULES_STATE_POST_GAME': 'Post-game',
            'DOTA_GAMERULES_STATE_GAME_IN_PROGRESS': 'Game in progress',
        }
        for key, label in mapping.items():
            if key in raw_state:
                return label
        cleaned = raw_state.replace('playing', '').strip()
        return cleaned or fallback

    @staticmethod
    def _hp_ratio(hero_data: Dict[str, Any]) -> Optional[float]:
        health = hero_data.get('health')
        max_health = hero_data.get('max_health')
        if not isinstance(health, (int, float)) or not isinstance(max_health, (int, float)) or max_health <= 0:
            return None
        return max(0.0, min(1.0, float(health) / float(max_health)))

    @staticmethod
    def _is_alive(hero_data: Dict[str, Any], player_data: Dict[str, Any]) -> bool:
        if 'alive' in hero_data:
            return bool(hero_data.get('alive'))
        if 'kill_list' in player_data:
            return True
        return hero_data.get('health', 1) not in (0, None)

    @staticmethod
    def _is_hero_pick(game_state_lower: str, draft_data: Dict[str, Any], game_time: int) -> bool:
        pick_words = ('hero_selection', 'strategy_time', 'pre_game', 'team_showcase', 'starting')
        if any(word in game_state_lower for word in pick_words):
            return True
        if draft_data:
            return True
        if game_time < 0:
            return True
        return False

    @staticmethod
    def _is_menu(
        game_state_lower: str,
        map_data: Dict[str, Any],
        player_data: Dict[str, Any],
        hero_data: Dict[str, Any],
    ) -> bool:
        if not map_data and not player_data and not hero_data:
            return True
        menu_words = ('menu', 'idle', 'post_game', 'dashboard')
        return any(word in game_state_lower for word in menu_words)

    @staticmethod
    def _is_victory(game_state_lower: str, map_data: Dict[str, Any], game_time: int) -> bool:
        if game_time <= 0:
            return False
        if 'victory' in game_state_lower:
            return True
        win_team = map_data.get('win_team')
        team_name = map_data.get('team_name')
        return win_team is not None and team_name is not None and str(win_team) == str(team_name)

    @staticmethod
    def _is_defeat(game_state_lower: str, map_data: Dict[str, Any], game_time: int) -> bool:
        if game_time <= 0:
            return False
        if any(word in game_state_lower for word in ('defeat', 'lose', 'loss')):
            return True
        win_team = map_data.get('win_team')
        team_name = map_data.get('team_name')
        return win_team is not None and team_name is not None and str(win_team) != str(team_name)
