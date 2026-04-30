from __future__ import annotations

import importlib
import json
import re
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from ..errors import MinestratorDependencyError, MinestratorWebSocketError
from ..models import MinestratorChatMessage

if TYPE_CHECKING:
    from ..server import Server


class ChatListener:
    """Background websocket listener for chat and system console messages."""

    _CONSOLE_EVENTS = {"console output", "console_output"}
    _ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
    _MC_COLOR_RE = re.compile("\u00A7.")
    _CONSOLE_PREFIX_RE = re.compile(r"^\[[^\]]+\]:\s*(?P<body>.*)$")
    _CHAT_LINE_RE = re.compile(r"(?:\[Not Secure\]\s*)?<(?P<author>[^>]+)>\s(?P<message>.+)")

    def __init__(
        self,
        server: Server,
        *,
        reconnect: bool,
        reconnect_delay: float,
        send_logs_on_auth: bool,
    ) -> None:
        self._server = server
        self._reconnect = reconnect
        self._reconnect_delay = max(0.5, reconnect_delay)
        self._send_logs_on_auth = send_logs_on_auth
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._ws_app: Any | None = None
        self.last_error: Exception | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, *, daemon: bool) -> None:
        if self.is_running:
            return
        _load_websocket_app_class()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_forever, daemon=daemon)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._ws_app is not None:
            try:
                self._ws_app.close()
            except Exception:
                pass

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def _run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._connect_once()
            except Exception as exc:
                self.last_error = exc
                self._server._dispatch("on_listener_error", exc, "chat")

            if self._stop_event.is_set() or not self._reconnect:
                break

            self._stop_event.wait(self._reconnect_delay)

    def _connect_once(self) -> None:
        websocket_app_class = _load_websocket_app_class()
        credentials = self._server.get_websocket_credentials()
        ws_url = credentials.url
        ws_token = credentials.token

        def on_open(ws: Any) -> None:
            ws.send(json.dumps({"event": "auth", "args": [ws_token]}))

        def on_message(ws: Any, raw_message: str) -> None:
            self._handle_message(ws, raw_message)

        def on_error(_ws: Any, error: Exception) -> None:
            self.last_error = error
            self._server._dispatch("on_listener_error", error, "chat")

        def on_close(_ws: Any, _status_code: int, _close_message: str) -> None:
            return

        ws_app = websocket_app_class(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        self._ws_app = ws_app

        run_options: dict[str, Any] = {
            "ping_interval": 25,
            "ping_timeout": 10,
        }
        if self._server.websocket_origin:
            run_options["origin"] = self._server.websocket_origin

        ws_app.run_forever(**run_options)
        self._ws_app = None

    def _handle_message(self, ws: Any, raw_message: str) -> None:
        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            return

        if not isinstance(payload, dict):
            return

        event_name = str(payload.get("event", "")).strip().lower()

        if event_name.startswith("auth") and event_name != "auth success":
            error = MinestratorWebSocketError(f"Websocket auth failed: {payload}")
            self.last_error = error
            self._server._dispatch("on_listener_error", error, "chat")
            return

        if event_name == "auth success":
            if self._send_logs_on_auth:
                try:
                    ws.send(json.dumps({"event": "send logs", "args": []}))
                except Exception as exc:
                    self.last_error = exc
                    self._server._dispatch("on_listener_error", exc, "chat")
            return

        if event_name in {"token expiring", "token expired"}:
            self._reauthenticate(ws)
            return

        if event_name == "status":
            args = payload.get("args")
            if isinstance(args, list) and args and isinstance(args[0], str):
                self._server._handle_status_value(args[0])
            return

        if event_name not in self._CONSOLE_EVENTS:
            return

        for line in self._extract_console_lines(payload):
            parsed = self._parse_console_line(line, payload)
            if parsed is None:
                continue
            callback_name, chat_message = parsed
            self._server._dispatch(callback_name, chat_message)

    def _reauthenticate(self, ws: Any) -> None:
        try:
            fresh_token = self._server.get_websocket_credentials().token
            ws.send(json.dumps({"event": "auth", "args": [fresh_token]}))
        except Exception as exc:
            self.last_error = exc
            self._server._dispatch("on_listener_error", exc, "chat")

    def _extract_console_lines(self, payload: dict[str, Any]) -> list[str]:
        args = payload.get("args")
        chunks: list[str] = []

        if isinstance(args, list):
            for item in args:
                if isinstance(item, str):
                    chunks.append(item)
                elif isinstance(item, dict):
                    for key in ("line", "message", "output", "data"):
                        value = item.get(key)
                        if isinstance(value, str):
                            chunks.append(value)

        if not chunks:
            data_value = payload.get("data")
            if isinstance(data_value, str):
                chunks.append(data_value)

        lines: list[str] = []
        for chunk in chunks:
            for line in chunk.splitlines():
                trimmed = line.strip()
                if trimmed:
                    lines.append(trimmed)
        return lines

    def _parse_console_line(
        self,
        raw_line: str,
        payload: dict[str, Any],
    ) -> tuple[str, MinestratorChatMessage] | None:
        clean_line = self._ANSI_ESCAPE_RE.sub("", raw_line)
        clean_line = self._MC_COLOR_RE.sub("", clean_line).strip()

        prefix_match = self._CONSOLE_PREFIX_RE.match(clean_line)
        content = prefix_match.group("body").strip() if prefix_match else clean_line
        if not content:
            return None

        chat_match = self._CHAT_LINE_RE.search(content)
        if chat_match:
            author_name = chat_match.group("author").strip()
            message = chat_match.group("message").strip()
            if not author_name or not message:
                return None

            author = self._server.get_minecraft_user(
                author_name,
                resolve_uuid=self._server.resolve_player_uuids,
                use_cache=True,
            )
            return (
                "on_chat_message",
                MinestratorChatMessage(
                    author=author,
                    content=message,
                    raw_line=raw_line,
                    received_at=datetime.now(timezone.utc),
                    payload=payload,
                    is_system=False,
                ),
            )

        return (
            "on_system_message",
            MinestratorChatMessage(
                author=self._server.system_user,
                content=content,
                raw_line=raw_line,
                received_at=datetime.now(timezone.utc),
                payload=payload,
                is_system=True,
            ),
        )


def _load_websocket_app_class() -> Any:
    errors: list[str] = []

    for module_name in ("websocket", "websocket._app"):
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            errors.append(f"{module_name}: {exc}")
            continue

        websocket_app_class = getattr(module, "WebSocketApp", None)
        if websocket_app_class is not None:
            return websocket_app_class

        errors.append(f"{module_name}: WebSocketApp missing")

    details = "; ".join(errors) if errors else "no module candidates found"
    raise MinestratorDependencyError(
        "Unable to load WebSocketApp. Install dependency with: pip install websocket-client "
        f"(details: {details})"
    )
