"""Servidor WebSocket que envía los frames del simulador al visor three.js en tiempo real.

Mensajes (JSON):
    {"type": "episode", "episode": {...}}   episodio completo hasta ahora (al empezar y al conectarse)
    {"type": "frame", "frame": {...}}       un frame nuevo tras cada paso

El visor solo dibuja estos frames; las reglas siguen viviendo en el simulador.
"""

from __future__ import annotations

import json
import threading
from typing import Any, Callable

from websockets.exceptions import ConnectionClosed
from websockets.sync.server import ServerConnection, serve

DEFAULT_PORT = 8765


class LiveServer:
    def __init__(self, snapshot: Callable[[], dict[str, Any]], host: str = "localhost", port: int = DEFAULT_PORT):
        """``snapshot`` devuelve el episodio actual completo para quien se conecte a mitad de partida."""
        self.snapshot = snapshot
        self.host, self.port = host, port
        self._clients: set[ServerConnection] = set()
        self._lock = threading.Lock()
        self._server = serve(self._handle, host, port)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}"

    @property
    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    def _handle(self, connection: ServerConnection) -> None:
        with self._lock:
            self._clients.add(connection)
        try:
            connection.send(self._episode_message())
            for _ in connection:  # el visor no envía nada; solo se espera al cierre
                pass
        except ConnectionClosed:
            pass
        finally:
            with self._lock:
                self._clients.discard(connection)

    def _episode_message(self) -> str:
        episode = dict(self.snapshot())
        episode["frames"] = list(episode["frames"])
        return json.dumps({"type": "episode", "episode": episode}, ensure_ascii=False)

    def _broadcast(self, message: str) -> None:
        with self._lock:
            clients = list(self._clients)
        for connection in clients:
            try:
                connection.send(message)
            except ConnectionClosed:
                with self._lock:
                    self._clients.discard(connection)

    def send_episode(self) -> None:
        self._broadcast(self._episode_message())

    def send_frame(self, frame: dict[str, Any]) -> None:
        self._broadcast(json.dumps({"type": "frame", "frame": frame}, ensure_ascii=False))

    def close(self) -> None:
        self._server.shutdown()
        self._thread.join(timeout=2)
