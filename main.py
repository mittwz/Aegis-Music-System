from __future__ import annotations

import logging
import os
import signal
import time
from pathlib import Path

from colorama import Fore, Style, init as colorama_init
from dotenv import load_dotenv

from dota_spotify_director import APP_NAME, APP_REPO, APP_TAGLINE, APP_VERSION
from dota_spotify_director.config_loader import load_config
from dota_spotify_director.director import CinematicStateDirector
from dota_spotify_director.dota_gsi_listener import DotaGSIServer
from dota_spotify_director.mood_engine import MoodEngine
from dota_spotify_director.spotify_controller import SpotifyController
from dota_spotify_director.state_tracker import StateTracker
from dota_spotify_director.volume_manager import VolumeManager


class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA,
    }

    def format(self, record: logging.LogRecord) -> str:
        original_levelname = record.levelname
        color = self.COLORS.get(record.levelno, '')
        record.levelname = f'{color}{original_levelname}{Style.RESET_ALL}'
        try:
            return super().format(record)
        finally:
            record.levelname = original_levelname


STATE_COLORS = {
    'menu': Fore.BLUE,
    'hero_pick': Fore.YELLOW,
    'early_game': Fore.GREEN,
    'calm_lane': Fore.LIGHTGREEN_EX,
    'teamfight': Fore.MAGENTA,
    'low_hp': Fore.LIGHTRED_EX,
    'dead': Fore.RED,
    'late_game': Fore.LIGHTMAGENTA_EX,
    'victory': Fore.LIGHTGREEN_EX,
    'defeat': Fore.LIGHTBLACK_EX,
}


def colored_state(name: str) -> str:
    color = STATE_COLORS.get(name, '')
    return f'{color}{name}{Style.RESET_ALL}' if color else name


def configure_logging() -> None:
    colorama_init(autoreset=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s'))
    root.addHandler(handler)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('spotipy').setLevel(logging.WARNING)


def validate_env() -> None:
    required = ['SPOTIFY_CLIENT_ID', 'SPOTIFY_CLIENT_SECRET', 'SPOTIFY_REDIRECT_URI']
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError('Missing variables in .env: ' + ', '.join(missing))


def format_hp_text(hp_ratio: float | None) -> str:
    if hp_ratio is None:
        return 'n/a'
    return f'{round(hp_ratio * 100)}%'


def hp_bucket_from_ratio(hp_ratio: float | None) -> str | None:
    if hp_ratio is None:
        return None
    if hp_ratio <= 0:
        return 'dead'
    if hp_ratio <= 0.14:
        return 'critical'
    if hp_ratio <= 0.28:
        return 'low'
    return 'healthy'


def clamp_volume(value: int) -> int:
    return max(0, min(100, int(value)))


def apply_master_gain(base_target_volume: int, audio_cfg: dict) -> tuple[int, int]:
    master_gain_percent = int(audio_cfg.get('master_gain_percent', 100))
    scaled = clamp_volume(round((base_target_volume * master_gain_percent) / 100))
    return scaled, master_gain_percent


def should_log_state(
    state_name: str,
    state_changed: bool,
    detail_changed: bool,
    target_volume_changed: bool,
    hp_bucket_changed: bool,
    playlist_changed: bool,
) -> bool:
    if playlist_changed or state_changed or target_volume_changed:
        return True
    if state_name == 'hero_pick' and detail_changed:
        return True
    if state_name == 'low_hp' and hp_bucket_changed:
        return True
    if state_name in {'victory', 'defeat'} and detail_changed:
        return True
    return False


def main() -> int:
    configure_logging()
    logger = logging.getLogger('main')

    base_dir = Path(__file__).resolve().parent
    load_dotenv(base_dir / '.env')
    validate_env()

    config = load_config(base_dir)
    branding = config.get('branding', {})
    server_cfg = config['server']
    spotify_cfg = config['spotify']
    audio_cfg = config['audio']
    active_profile_name = str(config.get('active_profile', 'default'))
    profile = config['profiles'].get(active_profile_name, config['profiles']['default'])

    tracker = StateTracker(
        low_hp_threshold=float(audio_cfg.get('low_hp_threshold', 0.28)),
        critical_hp_threshold=float(audio_cfg.get('critical_hp_threshold', 0.14)),
    )
    base_volume = int(audio_cfg.get('base_volume', 45))
    mood_engine = MoodEngine(profile=profile, base_volume=base_volume)
    mode = str(audio_cfg.get('mode', 'cinema')).lower()
    volume_manager = VolumeManager(
        initial_volume=base_volume,
        fade_step=int(audio_cfg.get('fade_step', 4)),
        mode=mode,
    )
    spotify = SpotifyController(
        cooldown_seconds=int(spotify_cfg.get('cooldown_seconds', 18)),
        enable_shuffle=bool(spotify_cfg.get('shuffle', True)),
        random_start=bool(spotify_cfg.get('random_start', False)),
    )
    cinema_director = CinematicStateDirector(
        enabled=mode == 'cinema',
        hold_seconds=audio_cfg.get('cinema_hold_seconds', {}),
    )

    server = DotaGSIServer(
        host=server_cfg.get('host', '127.0.0.1'),
        port=int(server_cfg.get('port', 3000)),
        auth_token=str(server_cfg.get('auth_token', 'aegis_music_system')),
    )
    server.start()

    running = True

    def _stop(*_: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    tick_interval = float(audio_cfg.get('tick_interval_seconds', 1.0))
    playlist_switching_enabled = bool(spotify_cfg.get('playlist_switching_enabled', True))
    payload_warning_interval = float(audio_cfg.get('payload_warning_interval_seconds', 60.0))

    last_state_name = None
    last_detail = None
    last_target_volume = None
    last_hp_bucket = None
    last_payload_seen = False
    boot_menu_started = False
    payload_warning_count = 0
    last_payload_warning_ts = 0.0

    logger.info('%s %s started.', branding.get('name', APP_NAME), APP_VERSION)
    logger.info(
        '%s | profile=%s | mode=%s | master_gain=%s%% | repo=%s',
        branding.get('tagline', APP_TAGLINE),
        active_profile_name,
        mode,
        int(audio_cfg.get('master_gain_percent', 100)),
        branding.get('repo', APP_REPO),
    )
    logger.info('Spotify ready. Waiting for Dota...')

    while running:
        payload = server.get_latest_payload()
        stats = server.get_stats()
        payload_count = int(stats.get('update_count', 0))

        if payload_count == 0 and not boot_menu_started:
            menu_state = cinema_director.apply(tracker.infer({}), time.time())
            menu_decision = mood_engine.decide(menu_state)
            target_volume, master_gain = apply_master_gain(menu_decision.target_volume, audio_cfg)
            stepped = volume_manager.next_step(target_volume, menu_state.state_name)
            playlist_started = False
            if playlist_switching_enabled and menu_decision.playlist_uri:
                playlist_started = spotify.start_playlist(menu_decision.playlist_uri)
            spotify.set_volume(stepped)
            logger.info(
                'Boot | state=%s | target=%s%% | applied=%s%% | gain=%s%% | playlist=%s | detail=%s',
                colored_state('menu'),
                target_volume,
                stepped,
                master_gain,
                menu_decision.playlist_name if playlist_started else 'kept current',
                menu_decision.reason,
            )
            boot_menu_started = True

        now = time.time()
        if payload_count > 0 and not last_payload_seen:
            logger.info('First GSI payload received | total=%s', payload_count)
            last_payload_seen = True

        if payload_count == 0:
            if payload_warning_count == 0:
                logger.warning('Still no Dota payload. Check the gamestate_integration_*.cfg file, the auth token, then restart Dota.')
                payload_warning_count = 1
                last_payload_warning_ts = now
            elif now - last_payload_warning_ts >= payload_warning_interval:
                logger.warning('Still waiting for Dota payload...')
                payload_warning_count += 1
                last_payload_warning_ts = now
            time.sleep(1.0)
            continue

        inferred = tracker.infer(payload)
        directed = cinema_director.apply(inferred, now)
        decision = mood_engine.decide(directed)
        target_volume, master_gain = apply_master_gain(decision.target_volume, audio_cfg)
        stepped_volume = volume_manager.next_step(target_volume, directed.state_name)

        state_changed = directed.state_name != last_state_name
        detail_changed = decision.reason != last_detail
        target_volume_changed = target_volume != last_target_volume
        hp_bucket = hp_bucket_from_ratio(directed.hp_ratio)
        hp_bucket_changed = hp_bucket != last_hp_bucket

        playlist_changed = False
        playlist_status = 'kept current'
        if playlist_switching_enabled and decision.playlist_uri:
            playlist_changed = spotify.start_playlist(decision.playlist_uri)
            playlist_status = decision.playlist_name if playlist_changed else 'kept current'
        elif decision.playlist_name:
            playlist_status = decision.playlist_name

        spotify.set_volume(stepped_volume)

        if should_log_state(
            directed.state_name,
            state_changed,
            detail_changed,
            target_volume_changed,
            hp_bucket_changed,
            playlist_changed,
        ):
            logger.info(
                'State=%s | time=%ss | hp=%s | target=%s%% | applied=%s%% | gain=%s%% | playlist=%s | detail=%s',
                colored_state(directed.state_name),
                directed.game_time_seconds,
                format_hp_text(directed.hp_ratio),
                target_volume,
                stepped_volume,
                master_gain,
                playlist_status,
                decision.reason,
            )
            last_state_name = directed.state_name
            last_detail = decision.reason
            last_target_volume = target_volume
            last_hp_bucket = hp_bucket

        time.sleep(tick_interval)

    logger.info('Shutting down...')
    server.stop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
