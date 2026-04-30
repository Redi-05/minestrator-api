from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..server import Server


class PresenceListener:
    """Background poller that emits join/leave/status events."""

    def __init__(
        self,
        server: Server,
        *,
        poll_interval: float,
        resolve_uuid: bool | None,
        use_cache: bool,
        emit_initial: bool,
    ) -> None:
        self._server = server
        self._poll_interval = max(1.0, poll_interval)
        self._resolve_uuid = resolve_uuid
        self._use_cache = use_cache
        self._emit_initial = emit_initial
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._known_usernames: set[str] = set()
        self._known_display_names: dict[str, str] = {}
        self.last_error: Exception | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, *, daemon: bool) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_forever, daemon=daemon)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def update_settings(
        self,
        *,
        poll_interval: float,
        resolve_uuid: bool | None,
        use_cache: bool,
        emit_initial: bool,
    ) -> None:
        self._poll_interval = max(1.0, poll_interval)
        self._resolve_uuid = resolve_uuid
        self._use_cache = use_cache
        self._emit_initial = emit_initial

    def _run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._poll_once()
            except Exception as exc:
                self.last_error = exc
                self._server._dispatch("on_listener_error", exc, "presence")

            self._stop_event.wait(self._poll_interval)

    def _poll_once(self) -> None:
        snapshot = self._server.get_live_snapshot(
            resolve_uuid=self._resolve_uuid,
            use_cache=self._use_cache,
        )

        current_names = {user.username.lower() for user in snapshot.players}
        current_display = {user.username.lower(): user.username for user in snapshot.players}

        if not self._known_usernames:
            if self._emit_initial:
                for user in sorted(snapshot.players, key=lambda item: item.username.lower()):
                    self._server._dispatch("on_player_join", user)
        else:
            joined_keys = sorted(current_names - self._known_usernames)
            left_keys = sorted(self._known_usernames - current_names)

            for key in joined_keys:
                display_name = current_display[key]
                user = self._server.get_minecraft_user(
                    display_name,
                    resolve_uuid=self._resolve_uuid,
                    use_cache=self._use_cache,
                )
                self._server._dispatch("on_player_join", user)

            for key in left_keys:
                display_name = self._known_display_names.get(key, key)
                user = self._server.get_minecraft_user(
                    display_name,
                    resolve_uuid=self._resolve_uuid,
                    use_cache=self._use_cache,
                )
                self._server._dispatch("on_player_leave", user)

        self._server._handle_status_value(snapshot.status)
        self._known_usernames = current_names
        self._known_display_names = current_display
