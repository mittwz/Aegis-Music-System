from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SharedGameState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: Dict[str, Any] = {}
        self._update_count = 0

    def update(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._data = payload
            self._update_count += 1

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {"update_count": self._update_count}


class _GSIHandler(BaseHTTPRequestHandler):
    shared_state: SharedGameState
    auth_token: Optional[str] = None

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"invalid json")
            return

        if self.auth_token:
            token = payload.get("auth", {}).get("token")
            if token != self.auth_token:
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"forbidden")
                return

        self.shared_state.update(payload)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


class DotaGSIServer:
    def __init__(self, host: str, port: int, auth_token: Optional[str] = None) -> None:
        self.shared_state = SharedGameState()
        handler = type(
            "ConfiguredGSIHandler",
            (_GSIHandler,),
            {"shared_state": self.shared_state, "auth_token": auth_token},
        )
        self._server = ThreadingHTTPServer((host, port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> None:
        logger.info("GSI ouvindo em http://%s:%s/", *self._server.server_address)
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)

    def get_latest_payload(self) -> Dict[str, Any]:
        return self.shared_state.snapshot()

    def get_stats(self) -> Dict[str, Any]:
        return self.shared_state.stats()
