from __future__ import annotations

import logging
import os
import time
from typing import Optional

import spotipy
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

logger = logging.getLogger(__name__)

SCOPES = [
    'user-read-playback-state',
    'user-modify-playback-state',
    'user-read-currently-playing',
]


class SpotifyController:
    def __init__(
        self,
        cooldown_seconds: int = 18,
        enable_shuffle: bool = True,
        random_start: bool = False,
    ) -> None:
        self.cooldown_seconds = cooldown_seconds
        self.enable_shuffle = enable_shuffle
        self.random_start = random_start
        self._last_playlist_uri: Optional[str] = None
        self._last_playlist_switch_ts = 0.0
        self._last_volume_sent: Optional[int] = None
        self._warned_no_device = False
        self._sp: Spotify = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=os.getenv('SPOTIFY_CLIENT_ID') or os.getenv('SPOTIPY_CLIENT_ID'),
                client_secret=os.getenv('SPOTIFY_CLIENT_SECRET') or os.getenv('SPOTIPY_CLIENT_SECRET'),
                redirect_uri=os.getenv('SPOTIFY_REDIRECT_URI') or os.getenv('SPOTIPY_REDIRECT_URI'),
                scope=' '.join(SCOPES),
                open_browser=True,
            )
        )

    def get_active_device_id(self) -> Optional[str]:
        devices = self._sp.devices().get('devices', [])
        if not devices:
            if not self._warned_no_device:
                logger.warning('No active Spotify device found.')
                self._warned_no_device = True
            return None
        active = next((d for d in devices if d.get('is_active')), None)
        chosen = active or devices[0]
        self._warned_no_device = False
        return chosen.get('id')

    def set_volume(self, target_volume: int) -> bool:
        target_volume = max(0, min(100, int(target_volume)))
        if self._last_volume_sent == target_volume:
            return False
        try:
            self._sp.volume(target_volume)
            self._last_volume_sent = target_volume
            return True
        except Exception as exc:
            logger.warning('Failed to set Spotify volume: %s', exc)
            return False

    def _current_context_uri(self) -> Optional[str]:
        try:
            data = self._sp.current_playback() or {}
            context = data.get('context') or {}
            return context.get('uri')
        except Exception:
            return None

    def start_playlist(self, playlist_uri: str) -> bool:
        if not playlist_uri:
            return False

        now = time.time()
        current_context = self._current_context_uri()
        if current_context == playlist_uri:
            self._last_playlist_uri = playlist_uri
            return False
        if self._last_playlist_uri == playlist_uri and (now - self._last_playlist_switch_ts) < self.cooldown_seconds:
            return False

        try:
            device_id = self.get_active_device_id()
            if not device_id:
                return False
            if self.enable_shuffle:
                try:
                    self._sp.shuffle(True, device_id=device_id)
                except Exception:
                    pass
            self._sp.start_playback(device_id=device_id, context_uri=playlist_uri)
            self._last_playlist_uri = playlist_uri
            self._last_playlist_switch_ts = now
            logger.info('Playlist switched -> %s%s', playlist_uri, ' | shuffle=on' if self.enable_shuffle else '')
            return True
        except Exception as exc:
            logger.warning('Failed to switch playlist: %s', exc)
            return False

    def add_to_queue(self, track_uri: str) -> None:
        try:
            self._sp.add_to_queue(track_uri)
        except Exception as exc:
            logger.warning('Failed to add track to queue: %s', exc)

    def pause(self) -> None:
        try:
            self._sp.pause_playback()
        except Exception as exc:
            logger.warning('Failed to pause playback: %s', exc)

    def resume(self) -> None:
        try:
            device_id = self.get_active_device_id()
            if not device_id:
                return
            self._sp.start_playback(device_id=device_id)
        except Exception as exc:
            logger.warning('Failed to resume playback: %s', exc)
