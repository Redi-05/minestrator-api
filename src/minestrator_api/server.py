from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Iterator, Mapping, Sequence

import requests

from ._http import HttpClient
from ._utils import format_stats_timestamp, normalize_remote_path, parse_bool, parse_float, parse_int
from .errors import MinestratorApiError, MinestratorDependencyError
from .models import (
    MinecraftUser,
    MinestratorAddon,
    MinestratorAddonResult,
    MinestratorConsoleLine,
    MinestratorFileEntry,
    MinestratorLiveSnapshot,
    MinestratorSftpCredentials,
    MinestratorStatPoint,
    MinestratorWebsocketCredentials,
)

_CONSOLE_EVENTS = {"console output", "console_output"}
_ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
_MC_COLOR_RE = re.compile("\u00A7.")
_CONSOLE_PREFIX_RE = re.compile(r"^\[[^\]]+\]:\s*(?P<body>.*)$")
_CHAT_LINE_RE = re.compile(r"(?:\[Not Secure\]\s*)?<(?P<author>[^>]+)>\s(?P<message>.+)")


class Server:
    """Object-oriented API client bound to one Minestrator server id."""

    def __init__(
        self,
        http_client: HttpClient,
        server_id: str | int,
        *,
        user_id: str | int | None = None,
        resolve_player_uuids: bool,
    ) -> None:
        """Create a server client.

        Args:
            http_client (HttpClient): Shared HTTP client used by the library.
            server_id (str | int): Server identifier.
            user_id (str | int | None): Optional user identifier for websocket credentials.
            resolve_player_uuids (bool): Resolve player UUIDs when fetching players.

        Raises:
            ValueError: If server_id is empty.

        Returns:
            None
        """
        normalized_id = str(server_id).strip()
        if not normalized_id:
            raise ValueError("server_id is required")

        self._http = http_client
        self._server_id = normalized_id
        self._user_id = str(user_id).strip() if user_id is not None else None
        self._resolve_player_uuids = bool(resolve_player_uuids)
        self._minecraft_user_cache: dict[str, MinecraftUser] = {}

    @property
    def id(self) -> str:
        """Server identifier."""
        return self._server_id

    @property
    def user_id(self) -> str | None:
        """User identifier bound to this server client."""
        return self._user_id

    @property
    def resolve_player_uuids(self) -> bool:
        """Whether player UUIDs are resolved by default."""
        return self._resolve_player_uuids

    def __enter__(self) -> Server:
        """Enter context manager and return self.

        Returns:
            Server: This server instance.
        """
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        """Exit context manager and close resources.

        Args:
            exc_type (type | None): Exception type, if any.
            exc (BaseException | None): Exception instance, if any.
            traceback (TracebackType | None): Traceback, if any.

        Returns:
            None
        """
        self.close()

    def close(self) -> None:
        """Close server client resources.

        This is a no-op for the server instance, but kept for symmetry
        with the top-level client.

        Returns:
            None
        """
        return

    def _route(self, suffix: str = "") -> str:
        normalized_suffix = suffix.lstrip("/")
        if not normalized_suffix:
            return f"/server/{self._server_id}"
        return f"/server/{self._server_id}/{normalized_suffix}"

    def request_server_raw(
        self,
        method: str,
        suffix: str = "",
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a raw request scoped to the server.

        Args:
            method (str): HTTP method.
            suffix (str): Route suffix after /server/{id}.
            params (Mapping[str, Any] | None): Query parameters.
            json_body (Mapping[str, Any] | None): JSON body.

        Returns:
            dict[str, Any]: Raw JSON payload.

        Raises:
            MinestratorApiError: When the API returns an error payload.
        """
        return self._http.request_raw(
            method,
            self._route(suffix),
            params=params,
            json_body=json_body,
        )

    def request_server_api(
        self,
        method: str,
        suffix: str = "",
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        allow_api_error: bool = False,
    ) -> dict[str, Any]:
        """Send a request and return the api section.

        Args:
            method (str): HTTP method.
            suffix (str): Route suffix after /server/{id}.
            params (Mapping[str, Any] | None): Query parameters.
            json_body (Mapping[str, Any] | None): JSON body.
            allow_api_error (bool): Allow non-success api codes.

        Returns:
            dict[str, Any]: api section of the response.

        Raises:
            MinestratorApiError: When the API returns an error payload.
        """
        return self._http.request_api(
            method,
            self._route(suffix),
            params=params,
            json_body=json_body,
            allow_api_error=allow_api_error,
        )

    def request_server_data(
        self,
        method: str,
        suffix: str = "",
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        allow_api_error: bool = False,
    ) -> dict[str, Any]:
        """Send a request and return the data section.

        Args:
            method (str): HTTP method.
            suffix (str): Route suffix after /server/{id}.
            params (Mapping[str, Any] | None): Query parameters.
            json_body (Mapping[str, Any] | None): JSON body.
            allow_api_error (bool): Allow non-success api codes.

        Returns:
            dict[str, Any]: data section of the response.

        Raises:
            MinestratorApiError: When the API returns an error payload.
        """
        return self._http.request_data(
            method,
            self._route(suffix),
            params=params,
            json_body=json_body,
            allow_api_error=allow_api_error,
        )

    def _resolve_minecraft_uuid(self, username: str) -> str | None:
        url = f"https://api.mojang.com/users/profiles/minecraft/{username}"

        try:
            response = requests.get(url, timeout=self._http.timeout)
        except requests.RequestException as exc:
            raise MinestratorApiError(
                f"Network error while resolving Mojang UUID for {username}: {exc}"
            ) from exc

        if response.status_code in (204, 404):
            return None

        if response.status_code >= 400:
            raise MinestratorApiError(
                f"Mojang API error {response.status_code} while resolving UUID for {username}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise MinestratorApiError(
                f"Invalid Mojang response while resolving UUID for {username}"
            ) from exc

        if not isinstance(payload, dict):
            raise MinestratorApiError(
                f"Unexpected Mojang payload type for {username}: {type(payload).__name__}"
            )

        uuid = payload.get("id")
        if isinstance(uuid, str) and uuid.strip():
            return uuid.strip()
        return None

    def get_minecraft_user(
        self,
        username: str,
        *,
        resolve_uuid: bool | None = None,
        use_cache: bool = True,
    ) -> MinecraftUser:
        """Build a MinecraftUser from a username.

        Args:
            username (str): Minecraft username.
            resolve_uuid (bool | None): Resolve UUID when True. Defaults to client setting.
            use_cache (bool): Use cached user data when available.

        Returns:
            MinecraftUser: Player identity object.

        Raises:
            ValueError: If username is empty.
            MinestratorApiError: If Mojang API lookup fails.
        """
        if not isinstance(username, str) or not username.strip():
            raise ValueError("username is required")

        normalized_username = username.strip()
        resolve = self._resolve_player_uuids if resolve_uuid is None else bool(resolve_uuid)
        cache_key = normalized_username.lower()

        cached_user = self._minecraft_user_cache.get(cache_key)
        if use_cache and cached_user is not None:
            if resolve and not cached_user.uuid:
                resolved_user = MinecraftUser(
                    username=cached_user.username,
                    uuid=self._resolve_minecraft_uuid(cached_user.username),
                )
                self._minecraft_user_cache[cache_key] = resolved_user
                return resolved_user
            return cached_user

        uuid = self._resolve_minecraft_uuid(normalized_username) if resolve else None
        user = MinecraftUser(username=normalized_username, uuid=uuid)

        if use_cache:
            self._minecraft_user_cache[cache_key] = user

        return user

    def get_live_snapshot(
        self,
        *,
        resolve_uuid: bool | None = None,
        use_cache: bool = True,
    ) -> MinestratorLiveSnapshot:
        """Fetch current live server data.

        Args:
            resolve_uuid (bool | None): Resolve player UUIDs when True.
            use_cache (bool): Use cached player data when available.

        Returns:
            MinestratorLiveSnapshot: Snapshot of live server status.

        Raises:
            MinestratorApiError: If the response payload is missing expected data.
        """
        data = self.request_server_data("GET", "live")

        stats = data.get("stats")
        if not isinstance(stats, dict):
            raise MinestratorApiError('Missing "stats" object in live snapshot payload')
        players_data = stats.get("players") if isinstance(stats.get("players"), dict) else {}
        raw_player_list = players_data.get("list") if isinstance(players_data, dict) else []

        player_names: list[str] = []
        if isinstance(raw_player_list, list):
            for item in raw_player_list:
                if isinstance(item, str) and item.strip():
                    player_names.append(item.strip())

        resolve = self._resolve_player_uuids if resolve_uuid is None else bool(resolve_uuid)
        players = [
            self.get_minecraft_user(name, resolve_uuid=resolve, use_cache=use_cache)
            for name in player_names
        ]

        cpu_data = stats.get("cpu") if isinstance(stats.get("cpu"), dict) else {}
        disk_data = stats.get("disk") if isinstance(stats.get("disk"), dict) else {}
        memory_data = stats.get("memory") if isinstance(stats.get("memory"), dict) else {}

        status_raw = data.get("status")
        state_raw = data.get("state") # "online" | "offline"
        version_raw = stats.get("version")
        hostname_raw = stats.get("hostname")

        try:
            return MinestratorLiveSnapshot(
                status=status_raw.strip() if isinstance(status_raw, str) and status_raw.strip() else None,
                state=state_raw.strip() if isinstance(state_raw, str) and state_raw.strip() else None,
                version=version_raw.strip() if isinstance(version_raw, str) and version_raw.strip() else None,
                hostname=hostname_raw.strip() if isinstance(hostname_raw, str) and hostname_raw.strip() else None,
                cpu_current=parse_int(cpu_data.get("current"), 0), # type: ignore
                cpu_dedicated=parse_int(cpu_data.get("dedicated"), 0), # type: ignore
                cpu_flexcore=parse_int(cpu_data.get("flexcore"), 0), # type: ignore
                cpu_limit=parse_int(cpu_data.get("limit"), 0), # type: ignore
                cpu_percent=parse_float(cpu_data.get("percent"), 0.0), # type: ignore
                cpu_is_bursting=parse_bool(cpu_data.get("is_bursting"), False), # type: ignore
                memory_current_mb=parse_int(memory_data.get("current"), 0), # type: ignore
                memory_limit_mb=parse_int(memory_data.get("limit"), 0), # type: ignore
                memory_percent=parse_float(memory_data.get("percent"), 0.0), # type: ignore
                disk_current_mb=parse_int(disk_data.get("current"), 0), # type: ignore
                disk_limit_mb=parse_int(disk_data.get("limit"), 0), # type: ignore
                disk_percent=parse_float(disk_data.get("percent"), 0.0), # type: ignore
                network_received_bytes=parse_int(data.get("network", {}).get("received"), 0), # type: ignore
                network_transmitted_bytes=parse_int(data.get("network", {}).get("transmitted"), 0), # type: ignore
                uptime_seconds=parse_int(data.get("uptime"), 0), # type: ignore
                players_current=parse_int(players_data.get("current"), 0), # type: ignore
                players_limit=parse_int(players_data.get("limit"), 0), # type: ignore
                players=players,
            )
        except KeyError as exc:
            raise MinestratorApiError(f"Missing expected key in live snapshot: {exc}") from exc

    @property
    def status(self) -> str | None:
        """Current server status value.
        Status can be null (operational), "installing", "install_failed", or "suspended".
        """
        return self.get_live_snapshot().status

    @property
    def state(self) -> str | None:
        """Current server state value.
        State can be "online", or "offline".
        """
        return self.get_live_snapshot().state

    @property
    def version(self) -> str | None:
        """Minecraft version installed on the server."""
        return self.get_live_snapshot().version

    @property
    def hostname(self) -> str | None:
        """Server hostname or MOTD."""
        return self.get_live_snapshot().hostname

    @property
    def motd(self) -> str | None:
        """Alias for hostname."""
        return self.hostname

    @property
    def players_online_count(self) -> int:
        """Number of currently online players."""
        return self.get_live_snapshot().players_current

    @property
    def players_max_count(self) -> int:
        """Maximum player slots."""
        return self.get_live_snapshot().players_limit

    @property
    def players_online(self) -> list[MinecraftUser]:
        """List of currently online players"""
        return self.get_live_snapshot(resolve_uuid=self._resolve_player_uuids).players

    def get_online_players(
        self,
        *,
        resolve_uuid: bool | None = None,
        use_cache: bool = True,
    ) -> list[MinecraftUser]:
        """Return online players as MinecraftUser objects.

        Args:
            resolve_uuid (bool | None): Resolve UUIDs when True.
            use_cache (bool): Use cached player data when available.

        Returns:
            list[MinecraftUser]: List of online players.

        Raises:
            MinestratorApiError: When the API returns an error payload.
        """
        return self.get_live_snapshot(resolve_uuid=resolve_uuid, use_cache=use_cache).players

    def is_player_online(self, player: str | MinecraftUser, *, case_sensitive: bool = False) -> bool:
        """Check whether a player is currently online.

        Args:
            player (str | MinecraftUser): Player name or object.
            case_sensitive (bool): Match case when True.

        Returns:
            bool: True if the player is online.

        Raises:
            MinestratorApiError: When the API returns an error payload.
        """
        username = player.username if isinstance(player, MinecraftUser) else str(player)
        if not username.strip():
            return False
        needle = username.strip()

        for online_user in self.get_online_players(resolve_uuid=False, use_cache=True):
            if case_sensitive:
                if online_user.username == needle:
                    return True
            else:
                if online_user.username.lower() == needle.lower():
                    return True
        return False

    def get_server_data(self) -> dict[str, Any]:
        """Fetch the server metadata payload.

        Returns:
            dict[str, Any]: Server data payload.

        Raises:
            MinestratorApiError: When the API returns an error payload.
        """
        return self.request_server_data("GET", "")

    @property
    def server_name(self) -> str | None:
        """Server display name."""
        server_data = self.get_server_data().get("server")
        if not isinstance(server_data, dict):
            return None
        name = server_data.get("name")
        return name.strip() if isinstance(name, str) and name.strip() else None

    @property
    def dns(self) -> str | None:
        """Server DNS value. (known as "server ip" by most minecraft users)"""
        server_data = self.get_server_data().get("server")
        if not isinstance(server_data, dict):
            return None
        dns_value = server_data.get("dns")
        return dns_value.strip() if isinstance(dns_value, str) and dns_value.strip() else None

    @property
    def server_ip(self) -> str | None:
        """Server IP address."""
        server_data = self.get_server_data().get("server")
        if not isinstance(server_data, dict):
            return None
        ip_value = server_data.get("ip")
        return ip_value.strip() if isinstance(ip_value, str) and ip_value.strip() else None

    @property
    def server_port(self) -> int | None:
        """Server game port."""
        server_data = self.get_server_data().get("server")
        if not isinstance(server_data, dict):
            return None
        port_raw = server_data.get("port")
        parsed = parse_int(port_raw, -1)
        return parsed if parsed >= 0 else None

    def get_server_websocket_credentials(self) -> MinestratorWebsocketCredentials:
        """Read websocket credentials from the server endpoint.

        Returns:
            MinestratorWebsocketCredentials: Websocket URL and token.

        Raises:
            MinestratorApiError: When credentials are missing.
        """
        data = self.get_server_data()
        websocket_data = data.get("websocket")
        if not isinstance(websocket_data, dict):
            raise MinestratorApiError('Missing "websocket" object in server payload')

        url = websocket_data.get("url") or websocket_data.get("socket")
        token = websocket_data.get("token")

        if not isinstance(url, str) or not url.strip():
            raise MinestratorApiError('Missing websocket "url" in server payload')
        if not isinstance(token, str) or not token.strip():
            raise MinestratorApiError('Missing websocket "token" in server payload')

        return MinestratorWebsocketCredentials(url=url.strip(), token=token.strip())

    def _get_user_websocket_data(self, user_id: str | int | None = None) -> dict[str, Any]:
        resolved_user_id = str(user_id).strip() if user_id is not None else self._user_id
        if not resolved_user_id:
            raise MinestratorApiError("user_id is required for /user/{id}/servers/websocket")

        return self._http.request_data("GET", f"/user/{resolved_user_id}/servers/websocket")

    def get_websocket_credentials(self) -> MinestratorWebsocketCredentials:
        """Fetch best websocket credentials for this server.

        Returns:
            MinestratorWebsocketCredentials: Websocket URL and token.

        Raises:
            MinestratorApiError: When credentials are missing.
        """
        if self._user_id:
            try:
                user_ws_data = self._get_user_websocket_data(self._user_id)
            except MinestratorApiError:
                user_ws_data = {}

            servers_data = user_ws_data.get("servers")
            if isinstance(servers_data, list):
                for item in servers_data:
                    if not isinstance(item, dict):
                        continue
                    if str(item.get("id", "")).strip() != self._server_id:
                        continue

                    socket_url = item.get("socket") or item.get("url")
                    token = item.get("token")
                    if isinstance(socket_url, str) and socket_url.strip() and isinstance(token, str) and token.strip():
                        return MinestratorWebsocketCredentials(
                            url=socket_url.strip(),
                            token=token.strip(),
                        )

        return self.get_server_websocket_credentials()

    def iter_console_lines(
        self,
        *,
        send_logs: bool = False,
        include_system: bool = True,
        resolve_uuid: bool | None = None,
        use_cache: bool = True,
    ) -> Iterator[MinestratorConsoleLine]:
        """Stream console lines from the server websocket.

        Args:
            send_logs (bool): Request historical logs before streaming new lines.
            include_system (bool): Include non-chat console lines.
            resolve_uuid (bool | None): Resolve player UUIDs when True.
            use_cache (bool): Use cached player data when available.

        Yields:
            MinestratorConsoleLine: Parsed console or chat lines.

        Returns:
            Iterator[MinestratorConsoleLine]: Iterator over console lines.

        Raises:
            MinestratorDependencyError: If websocket-client is not installed.
            MinestratorApiError: When websocket auth fails.
        """
        websocket_module = self._load_websocket_module()
        credentials = self.get_websocket_credentials()
        ws = websocket_module.create_connection(credentials.url, timeout=self._http.timeout)

        try:
            self._send_ws_auth(ws, credentials.token)
            send_logs_pending = send_logs

            while True:
                raw_message = ws.recv()
                if raw_message is None:
                    break

                payload = self._parse_ws_payload(raw_message)
                if payload is None:
                    continue

                event_name = str(payload.get("event", "")).strip().lower()

                if event_name.startswith("auth") and event_name != "auth success":
                    raise MinestratorApiError(f"Websocket auth failed: {payload}")

                if event_name == "auth success":
                    if send_logs_pending:
                        ws.send(json.dumps({"event": "send logs", "args": []}))
                        send_logs_pending = False
                    continue

                if event_name in {"token expiring", "token expired"}:
                    self._send_ws_auth(ws, None)
                    continue

                if event_name not in _CONSOLE_EVENTS:
                    continue

                for line in self._extract_console_lines(payload):
                    parsed = self._parse_console_line(
                        line,
                        resolve_uuid=resolve_uuid,
                        use_cache=use_cache,
                    )
                    if parsed is None:
                        continue
                    if not include_system and not parsed.is_chat:
                        continue
                    yield parsed
        finally:
            try:
                ws.close()
            except Exception:
                pass

    def iter_chat_messages(
        self,
        *,
        send_logs: bool = False,
        resolve_uuid: bool | None = None,
        use_cache: bool = True,
    ) -> Iterator[MinestratorConsoleLine]:
        """Stream chat messages from the server websocket.

        Args:
            send_logs (bool): Request historical logs before streaming new lines.
            resolve_uuid (bool | None): Resolve player UUIDs when True.
            use_cache (bool): Use cached player data when available.

        Yields:
            MinestratorConsoleLine: Parsed chat lines.

        Returns:
            Iterator[MinestratorConsoleLine]: Iterator over chat lines.

        Raises:
            MinestratorDependencyError: If websocket-client is not installed.
            MinestratorApiError: When websocket auth fails.
        """
        for line in self.iter_console_lines(
            send_logs=send_logs,
            include_system=False,
            resolve_uuid=resolve_uuid,
            use_cache=use_cache,
        ):
            if line.is_chat:
                yield line

    @staticmethod
    def _load_websocket_module() -> Any:
        try:
            import websocket  # type: ignore
        except ModuleNotFoundError as exc:
            raise MinestratorDependencyError(
                "Chat access requires websocket-client. Install with: pip install minestrator-api[realtime]"
            ) from exc
        return websocket

    def _send_ws_auth(self, ws: Any, token: str | None) -> None:
        if not token:
            token = self.get_websocket_credentials().token
        ws.send(json.dumps({"event": "auth", "args": [token]}))

    @staticmethod
    def _parse_ws_payload(raw_message: Any) -> dict[str, Any] | None:
        if not isinstance(raw_message, str):
            try:
                raw_message = raw_message.decode("utf-8")
            except Exception:
                return None
        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    @staticmethod
    def _extract_console_lines(payload: dict[str, Any]) -> list[str]:
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
        *,
        resolve_uuid: bool | None,
        use_cache: bool,
    ) -> MinestratorConsoleLine | None:
        clean_line = _ANSI_ESCAPE_RE.sub("", raw_line)
        clean_line = _MC_COLOR_RE.sub("", clean_line).strip()

        prefix_match = _CONSOLE_PREFIX_RE.match(clean_line)
        content = prefix_match.group("body").strip() if prefix_match else clean_line
        if not content:
            return None

        match = _CHAT_LINE_RE.search(content)
        if match:
            author_name = match.group("author").strip()
            message = match.group("message").strip()
            if not author_name or not message:
                return None

            author = self.get_minecraft_user(
                author_name,
                resolve_uuid=resolve_uuid,
                use_cache=use_cache,
            )
            return MinestratorConsoleLine(
                content=message,
                raw_line=raw_line,
                received_at=datetime.now(timezone.utc),
                author=author,
                is_chat=True,
            )

        return MinestratorConsoleLine(
            content=content,
            raw_line=raw_line,
            received_at=datetime.now(timezone.utc),
            author=None,
            is_chat=False,
        )

    def get_sftp_credentials(self, *, required: bool = False) -> MinestratorSftpCredentials | None:
        """Fetch SFTP credentials for the server.

        Args:
            required (bool): Raise when credentials are missing.

        Returns:
            MinestratorSftpCredentials | None: Credentials or None.

        Raises:
            MinestratorApiError: When required is True and credentials are missing.
        """
        sftp_data = self.get_server_data().get("sftp")
        if not isinstance(sftp_data, dict):
            if required:
                raise MinestratorApiError('Missing "sftp" object in server payload')
            return None

        host = sftp_data.get("host")
        username = sftp_data.get("user")
        password = sftp_data.get("password")
        protocol = sftp_data.get("protocol")
        port = parse_int(sftp_data.get("port"), 22)

        if not isinstance(host, str) or not host.strip():
            if required:
                raise MinestratorApiError('Missing sftp "host" in server payload')
            return None
        if not isinstance(username, str) or not username.strip():
            if required:
                raise MinestratorApiError('Missing sftp "user" in server payload')
            return None
        if not isinstance(password, str) or not password.strip():
            if required:
                raise MinestratorApiError('Missing sftp "password" in server payload')
            return None

        protocol_text = protocol.strip() if isinstance(protocol, str) and protocol.strip() else "sftp"
        return MinestratorSftpCredentials(
            protocol=protocol_text,
            host=host.strip(),
            port=port,
            username=username.strip(),
            password=password.strip(),
        )

    def list_files(self, path: str = "") -> list[MinestratorFileEntry]:
        """List files and folders for a path.

        Args:
            path (str): Remote path inside the server file system.

        Returns:
            list[MinestratorFileEntry]: File and folder entries.

        Raises:
            MinestratorApiError: When the API returns an error payload.
        """
        normalized_path = normalize_remote_path(path)
        suffix = "files/list/"
        if normalized_path:
            suffix = f"{suffix}{normalized_path}"

        data = self.request_server_data("GET", suffix)
        raw_files = data.get("files")
        if not isinstance(raw_files, list):
            return []

        result: list[MinestratorFileEntry] = []
        for item in raw_files:
            if not isinstance(item, dict):
                continue

            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                continue

            size_text = item.get("size") if isinstance(item.get("size"), str) else None
            created = item.get("created") if isinstance(item.get("created"), str) else None
            modified = item.get("modified") if isinstance(item.get("modified"), str) else None

            result.append(
                MinestratorFileEntry(
                    name=name.strip(),
                    is_folder=bool(parse_int(item.get("folder"), 0)),
                    size_text=size_text.strip() if isinstance(size_text, str) else None,
                    size_bytes=parse_int(item.get("size_bytes"), 0),
                    created_at=created,
                    modified_at=modified,
                )
            )

        return result

    def get_file_content(self, path: str) -> str:
        """Fetch file content as text.

        Args:
            path (str): Remote file path.

        Returns:
            str: File content.

        Raises:
            ValueError: If path is empty.
            MinestratorApiError: When the API returns an error payload.
        """
        normalized_path = normalize_remote_path(path)
        if not normalized_path:
            raise ValueError("path is required")

        data = self.request_server_data("GET", f"files/content/{normalized_path}")
        content = data.get("content")
        if not isinstance(content, str):
            raise MinestratorApiError(f"Missing file content for path: {path}")
        return content

    def get_file_json(self, path: str) -> Any:
        """Fetch file content and parse JSON.

        Args:
            path (str): Remote file path.

        Returns:
            Any: Parsed JSON content.

        Raises:
            ValueError: If path is empty.
            MinestratorApiError: When the API returns invalid JSON.
        """
        content = self.get_file_content(path)
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise MinestratorApiError(f"Invalid JSON in remote file: {path}") from exc

    def check_files_exist(self, file_paths: Sequence[str], *, prefer_post: bool = True) -> dict[str, bool]:
        """Check existence for multiple file paths.

        Args:
            file_paths (Sequence[str]): Paths to check.
            prefer_post (bool): Try POST before GET when True.

        Returns:
            dict[str, bool]: Map of path to existence flag.

        Raises:
            MinestratorApiError: When the API call fails.
        """
        normalized_paths = [normalize_remote_path(path) for path in file_paths if str(path).strip()]
        normalized_paths = [path for path in normalized_paths if path]
        if not normalized_paths:
            return {}

        attempts: list[tuple[str, Mapping[str, Any] | None, Mapping[str, Any] | None]] = []
        if prefer_post:
            attempts.append(("POST", None, {"files": normalized_paths}))
            attempts.append(("POST", None, {"paths": normalized_paths}))
        attempts.append(("GET", {"files": ",".join(normalized_paths)}, None))

        last_error: Exception | None = None
        for method, params, body in attempts:
            try:
                data = self.request_server_data(
                    method,
                    "files/exists",
                    params=params,
                    json_body=body,
                )
            except Exception as exc:
                last_error = exc
                continue

            exists_data = data.get("exists")
            if isinstance(exists_data, dict):
                result: dict[str, bool] = {}
                for key, value in exists_data.items():
                    if isinstance(key, str):
                        result[key] = bool(value)
                return result

        if last_error is not None:
            raise MinestratorApiError(f"Unable to call files/exists endpoint: {last_error}")
        raise MinestratorApiError("Unable to parse files/exists response")

    def file_exists(self, path: str) -> bool:
        """Check existence for a single file path.

        Args:
            path (str): Path to check.

        Returns:
            bool: True when the path exists.

        Raises:
            MinestratorApiError: When the API call fails.
        """
        normalized = normalize_remote_path(path)
        if not normalized:
            return False

        result = self.check_files_exist([normalized])
        if normalized in result:
            return result[normalized]

        for key, exists in result.items():
            if normalize_remote_path(key) == normalized:
                return exists

        return False

    def get_properties_data(self) -> dict[str, Any]:
        """Fetch raw server properties payload.

        Returns:
            dict[str, Any]: Raw properties data.

        Raises:
            MinestratorApiError: When the API returns an error payload.
        """
        return self.request_server_data("GET", "properties")

    def get_server_properties(self) -> dict[str, str]:
        """Fetch server.properties as a key/value map.

        Returns:
            dict[str, str]: Properties map.

        Raises:
            MinestratorApiError: When the API returns an error payload.
        """
        properties_data = self.get_properties_data().get("properties")
        if not isinstance(properties_data, dict):
            return {}

        parsed: dict[str, str] = {}
        for key, value in properties_data.items():
            if isinstance(key, str):
                parsed[key] = str(value)
        return parsed

    def get_property(self, key: str, default: str | None = None) -> str | None:
        """Read a server.properties value.

        Args:
            key (str): Property name.
            default (str | None): Default when missing.

        Returns:
            str | None: Property value or default.
        """
        if not isinstance(key, str) or not key.strip():
            return default
        return self.get_server_properties().get(key.strip(), default)

    @staticmethod
    def _parse_addon_result(api_section: Mapping[str, Any], *, key: str) -> MinestratorAddonResult:
        api_code = HttpClient.extract_api_code(api_section)
        error = api_section.get("error") if isinstance(api_section.get("error"), str) else None
        data_obj = api_section.get("data")
        data = data_obj if isinstance(data_obj, dict) else {}
        raw_items = data.get(key) if isinstance(data.get(key), list) else []

        items: list[MinestratorAddon] = []
        for raw_item in raw_items: # type: ignore
            if not isinstance(raw_item, dict):
                continue
            name = raw_item.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            items.append(
                MinestratorAddon(
                    name=name.strip(),
                    filename=raw_item.get("filename") if isinstance(raw_item.get("filename"), str) else None,
                    version=raw_item.get("version") if isinstance(raw_item.get("version"), str) else None,
                    enabled=bool(raw_item.get("enabled")) if "enabled" in raw_item else None,
                )
            )

        return MinestratorAddonResult(items=items, api_code=api_code, error=error)

    def get_plugins(self) -> MinestratorAddonResult:
        """List plugins installed on the server.

        Returns:
            MinestratorAddonResult: Plugin entries and metadata.

        Raises:
            MinestratorApiError: When the API returns an error payload.
        """
        api_section = self.request_server_api("GET", "plugins", allow_api_error=True)
        return self._parse_addon_result(api_section, key="plugins")

    def get_mods(self) -> MinestratorAddonResult:
        """List mods installed on the server.

        Returns:
            MinestratorAddonResult: Mod entries and metadata.

        Raises:
            MinestratorApiError: When the API returns an error payload.
        """
        api_section = self.request_server_api("GET", "mods", allow_api_error=True)
        return self._parse_addon_result(api_section, key="mods")

    def get_stats(self, start: str | datetime, end: str | datetime) -> list[MinestratorStatPoint]:
        """Fetch server stats for a time range.

        Args:
            start (str | datetime): Start timestamp.
            end (str | datetime): End timestamp.

        Returns:
            list[MinestratorStatPoint]: Timeline points.

        Raises:
            ValueError: If start or end is empty.
            MinestratorApiError: When the API returns an error payload.
        """
        start_text = format_stats_timestamp(start)
        end_text = format_stats_timestamp(end)
        if not start_text or not end_text:
            raise ValueError("start and end are required")

        data = self.request_server_data("GET", f"stats/{start_text}/{end_text}")
        raw_stats = data.get("stats")
        if not isinstance(raw_stats, list):
            return []

        result: list[MinestratorStatPoint] = []
        for item in raw_stats:
            if not isinstance(item, dict):
                continue
            date_value = item.get("date")
            if not isinstance(date_value, str) or not date_value.strip():
                continue
            result.append(
                MinestratorStatPoint(
                    date=date_value.strip(),
                    cpu=parse_int(item.get("cpu"), 0),
                    ram=parse_int(item.get("ram"), 0),
                    disk=parse_int(item.get("disk"), 0),
                    players=parse_int(item.get("players"), 0),
                )
            )
        return result

    def send_command(self, command: str) -> dict[str, Any]:
        """Send a console command to the server.

        Args:
            command (str): Command text.

        Returns:
            dict[str, Any]: API response section.

        Raises:
            ValueError: If command is empty.
            MinestratorApiError: When the API returns a non-success code.
        """
        if not isinstance(command, str) or not command.strip():
            raise ValueError("command is required")

        api_section = self._http.request_api(
            "PUT",
            f"/server/{self._server_id}/command",
            json_body={"command": command.strip()},
        )
        code = HttpClient.extract_api_code(api_section)
        if code != 200:
            raise MinestratorApiError(f"Command failed with code {code}: {api_section}")

        return api_section