"""Newline-delimited JSON events for the chat browser client."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from typing import Any


class EventWriter:
    def __init__(self, handler: BaseHTTPRequestHandler) -> None:
        self.handler = handler
        self.started = False
        self.connected = True

    def send(self, kind: str, **payload: Any) -> None:
        if not self.connected:
            return
        if not self.started:
            self.handler.send_response(200)
            self.handler.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.handler.send_header("Cache-Control", "no-cache, no-transform")
            self.handler.send_header("X-Accel-Buffering", "no")
            self.handler.send_header("Connection", "close")
            self.handler.end_headers()
            self.handler.close_connection = True
            self.started = True
        data = (json.dumps({"type": kind, **payload}, ensure_ascii=False) + "\n").encode("utf-8")
        try:
            self.handler.wfile.write(data)
            self.handler.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            self.connected = False
