from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence

import requests

from ._http import HttpClient
from ._utils import format_stats_timestamp, normalize_remote_path, parse_int
from .errors import MinestratorApiError
from .listeners import ChatListener, PresenceListener
from .models import (
    MinecraftUser,
    MinestratorAddon,
    MinestratorAddonResult,
    MinestratorChatMessage,
    MinestratorFileEntry,
    MinestratorLiveSnapshot,
    MinestratorSftpCredentials,
    MinestratorStatPoint,
    MinestratorWebsocketCredentials,
)

ChatCallback = Callable[[MinestratorChatMessage], None]
UserCallback = Callable[[MinecraftUser], None]
StatusCallback = Callable[[str | None, str | None], None]
ErrorCallback = Callable[[Exception, str], None]


class Server:
    """Object-oriented API client bound to one Minestrator server id."""

    _EVENT_NAMES = {
        "on_chat_message",
        "on_system_message",
        "on_player_join",
        "on_player_leave",
        "on_status_update",
        "on_listener_error",
    }

    def __init__(
        self,
        http_client: HttpClient,
        server_id: str | int,
        *,
        user_id: str | int | None = None,
        websocket_origin: str | None,
        resolve_player_uuids: bool,
        presence_poll_interval: float,
    ) -> None:
        normalized_id = str(server_id).strip()
        if not normalized_id:
            raise ValueError("server_id is required")

        self._http = http_client
        self._server_id = normalized_id
        self._user_id = str(user_id).strip() if user_id is not None else None
        self._websocket_origin = websocket_origin.strip() if isinstance(websocket_origin, str) and websocket_origin.strip() else None
        self._resolve_player_uuids = bool(resolve_player_uuids)
        self._presence_poll_interval = max(1.0, float(presence_poll_interval))

        self._minecraft_user_cache: dict[str, MinecraftUser] = {}
        self._chat_listener: ChatListener | None = None
        self._presence_listener: PresenceListener | None = None
        self._last_status: str | None = None

        self._event_handlers: dict[str, list[Callable[..., None]]] = {
            "on_chat_message": [],
            "on_system_message": [],
            "on_player_join": [],
            "on_player_leave": [],
            "on_status_update": [],
            "on_listener_error": [],
        }

    @property
    def id(self) -> str:
        return self._server_id

    @property
    def user_id(self) -> str | None:
        return self._user_id

    @property
    def websocket_origin(self) -> str | None:
        return self._websocket_origin

    @property
    def resolve_player_uuids(self) -> bool:
        return self._resolve_player_uuids

    @property
    def system_user(self) -> MinecraftUser:
        return MinecraftUser(username="SYSTEM")

    def __enter__(self) -> Server:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def close(self) -> None:
        self.stop_listeners()

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

        status_raw = data.get("status") # null : serveur operationel, "installing" : serveur en cours d'installation, "install_failed" : échec de l'installation, "suspended" : serveur suspendu
        state = data.get("state") # "online" | "offline"
        version_raw = stats.get("version")
        hostname_raw = stats.get("hostname")

        try:
            return MinestratorLiveSnapshot(
                status=status_raw.strip() if isinstance(status_raw, str) and status_raw.strip() else None,
                state=state.strip() if isinstance(state, str) and state.strip() else None,
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
        return self.get_live_snapshot().status

    @property
    def state(self) -> str | None:
        return self.get_live_snapshot().state
    
    @property
    def version(self) -> str | None:
        return self.get_live_snapshot().version

    @property
    def hostname(self) -> str | None:
        return self.get_live_snapshot().hostname

    @property
    def motd(self) -> str | None:
        return self.hostname

    @property
    def players_online_count(self) -> int:
        return self.get_live_snapshot().players_current

    @property
    def players_max_count(self) -> int:
        return self.get_live_snapshot().players_limit

    @property
    def players_online(self) -> list[MinecraftUser]:
        return self.get_live_snapshot(resolve_uuid=self._resolve_player_uuids).players

    def get_online_players(
        self,
        *,
        resolve_uuid: bool | None = None,
        use_cache: bool = True,
    ) -> list[MinecraftUser]:
        return self.get_live_snapshot(resolve_uuid=resolve_uuid, use_cache=use_cache).players

    def is_player_online(self, player: str | MinecraftUser, *, case_sensitive: bool = False) -> bool:
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
        return self.request_server_data("GET", "")

    @property
    def server_name(self) -> str | None:
        server_data = self.get_server_data().get("server")
        if not isinstance(server_data, dict):
            return None
        name = server_data.get("name")
        return name.strip() if isinstance(name, str) and name.strip() else None

    @property
    def dns(self) -> str | None:
        server_data = self.get_server_data().get("server")
        if not isinstance(server_data, dict):
            return None
        dns_value = server_data.get("dns")
        return dns_value.strip() if isinstance(dns_value, str) and dns_value.strip() else None

    @property
    def server_ip(self) -> str | None:
        server_data = self.get_server_data().get("server")
        if not isinstance(server_data, dict):
            return None
        ip_value = server_data.get("ip")
        return ip_value.strip() if isinstance(ip_value, str) and ip_value.strip() else None

    @property
    def server_port(self) -> int | None:
        server_data = self.get_server_data().get("server")
        if not isinstance(server_data, dict):
            return None
        port_raw = server_data.get("port")
        parsed = parse_int(port_raw, -1)
        return parsed if parsed >= 0 else None

    def get_server_websocket_credentials(self) -> MinestratorWebsocketCredentials:
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

    def get_sftp_credentials(self, *, required: bool = False) -> MinestratorSftpCredentials | None:
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
        normalized_path = normalize_remote_path(path)
        if not normalized_path:
            raise ValueError("path is required")

        data = self.request_server_data("GET", f"files/content/{normalized_path}")
        content = data.get("content")
        if not isinstance(content, str):
            raise MinestratorApiError(f"Missing file content for path: {path}")
        return content

    def get_file_json(self, path: str) -> Any:
        content = self.get_file_content(path)
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise MinestratorApiError(f"Invalid JSON in remote file: {path}") from exc

    def check_files_exist(self, file_paths: Sequence[str], *, prefer_post: bool = True) -> dict[str, bool]:
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
        return self.request_server_data("GET", "properties")

    def get_server_properties(self) -> dict[str, str]:
        properties_data = self.get_properties_data().get("properties")
        if not isinstance(properties_data, dict):
            return {}

        parsed: dict[str, str] = {}
        for key, value in properties_data.items():
            if isinstance(key, str):
                parsed[key] = str(value)
        return parsed

    def get_property(self, key: str, default: str | None = None) -> str | None:
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
        api_section = self.request_server_api("GET", "plugins", allow_api_error=True)
        return self._parse_addon_result(api_section, key="plugins")

    def get_mods(self) -> MinestratorAddonResult:
        api_section = self.request_server_api("GET", "mods", allow_api_error=True)
        return self._parse_addon_result(api_section, key="mods")

    def get_stats(self, start: str | datetime, end: str | datetime) -> list[MinestratorStatPoint]:
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

    def event(self, callback: Callable[..., None]) -> Callable[..., None]:
        """Register an event callback based on callback name."""
        event_name = callback.__name__.strip().lower()
        if event_name not in self._EVENT_NAMES:
            names = ", ".join(sorted(self._EVENT_NAMES))
            raise ValueError(f"Unknown event name '{callback.__name__}'. Expected one of: {names}")

        self._register_event(event_name, callback)

        if event_name in {"on_chat_message", "on_system_message"}:
            self.start_chat_listener()
        elif event_name in {"on_player_join", "on_player_leave", "on_status_update"}:
            self.start_presence_listener()

        return callback

    def on_chat_message(
        self,
        *,
        auto_start: bool = True,
        daemon: bool = False,
        reconnect: bool = True,
        reconnect_delay: float = 3.0,
        send_logs_on_auth: bool = False,
    ) -> Callable[[ChatCallback], ChatCallback]:
        def decorator(callback: ChatCallback) -> ChatCallback:
            self._register_event("on_chat_message", callback)
            if auto_start:
                self.start_chat_listener(
                    daemon=daemon,
                    reconnect=reconnect,
                    reconnect_delay=reconnect_delay,
                    send_logs_on_auth=send_logs_on_auth,
                )
            return callback

        return decorator

    def on_system_message(
        self,
        *,
        auto_start: bool = True,
        daemon: bool = False,
        reconnect: bool = True,
        reconnect_delay: float = 3.0,
        send_logs_on_auth: bool = False,
    ) -> Callable[[ChatCallback], ChatCallback]:
        def decorator(callback: ChatCallback) -> ChatCallback:
            self._register_event("on_system_message", callback)
            if auto_start:
                self.start_chat_listener(
                    daemon=daemon,
                    reconnect=reconnect,
                    reconnect_delay=reconnect_delay,
                    send_logs_on_auth=send_logs_on_auth,
                )
            return callback

        return decorator

    def on_player_join(
        self,
        *,
        auto_start: bool = True,
        daemon: bool = False,
        poll_interval: float | None = None,
        resolve_uuid: bool | None = None,
        use_cache: bool = True,
        emit_initial: bool = False,
    ) -> Callable[[UserCallback], UserCallback]:
        def decorator(callback: UserCallback) -> UserCallback:
            self._register_event("on_player_join", callback)
            if auto_start:
                self.start_presence_listener(
                    daemon=daemon,
                    poll_interval=poll_interval,
                    resolve_uuid=resolve_uuid,
                    use_cache=use_cache,
                    emit_initial=emit_initial,
                )
            return callback

        return decorator

    def on_player_leave(
        self,
        *,
        auto_start: bool = True,
        daemon: bool = False,
        poll_interval: float | None = None,
        resolve_uuid: bool | None = None,
        use_cache: bool = True,
        emit_initial: bool = False,
    ) -> Callable[[UserCallback], UserCallback]:
        def decorator(callback: UserCallback) -> UserCallback:
            self._register_event("on_player_leave", callback)
            if auto_start:
                self.start_presence_listener(
                    daemon=daemon,
                    poll_interval=poll_interval,
                    resolve_uuid=resolve_uuid,
                    use_cache=use_cache,
                    emit_initial=emit_initial,
                )
            return callback

        return decorator

    def on_status_update(
        self,
        *,
        auto_start: bool = True,
        daemon: bool = False,
        poll_interval: float | None = None,
        resolve_uuid: bool | None = None,
        use_cache: bool = True,
        emit_initial: bool = False,
    ) -> Callable[[StatusCallback], StatusCallback]:
        def decorator(callback: StatusCallback) -> StatusCallback:
            self._register_event("on_status_update", callback)
            if auto_start:
                self.start_presence_listener(
                    daemon=daemon,
                    poll_interval=poll_interval,
                    resolve_uuid=resolve_uuid,
                    use_cache=use_cache,
                    emit_initial=emit_initial,
                )
            return callback

        return decorator

    def on_listener_error(self) -> Callable[[ErrorCallback], ErrorCallback]:
        def decorator(callback: ErrorCallback) -> ErrorCallback:
            self._register_event("on_listener_error", callback)
            return callback

        return decorator

    def _register_event(self, event_name: str, callback: Callable[..., None]) -> None:
        if event_name not in self._EVENT_NAMES:
            raise ValueError(f"Unsupported event: {event_name}")

        handlers = self._event_handlers[event_name]
        if callback not in handlers:
            handlers.append(callback)

    def _dispatch(self, event_name: str, *args: Any) -> None:
        callbacks = list(self._event_handlers.get(event_name, []))
        for callback in callbacks:
            try:
                callback(*args)
            except Exception as exc:
                if event_name == "on_listener_error":
                    continue
                error_callbacks = list(self._event_handlers.get("on_listener_error", []))
                for error_callback in error_callbacks:
                    try:
                        error_callback(exc, f"callback:{event_name}")
                    except Exception:
                        continue

    def _handle_status_value(self, status: str | None) -> None:
        normalized_status = status.strip() if isinstance(status, str) and status.strip() else None
        previous_status = self._last_status
        if normalized_status == previous_status:
            return

        self._last_status = normalized_status
        self._dispatch("on_status_update", previous_status, normalized_status)

    def start_chat_listener(
        self,
        *,
        daemon: bool = False,
        reconnect: bool = True,
        reconnect_delay: float = 3.0,
        send_logs_on_auth: bool = False,
    ) -> None:
        if self._chat_listener is None:
            self._chat_listener = ChatListener(
                self,
                reconnect=reconnect,
                reconnect_delay=reconnect_delay,
                send_logs_on_auth=send_logs_on_auth,
            )

        if self._chat_listener.is_running:
            return

        self._chat_listener.start(daemon=daemon)

    def start_presence_listener(
        self,
        *,
        daemon: bool = False,
        poll_interval: float | None = None,
        resolve_uuid: bool | None = None,
        use_cache: bool = True,
        emit_initial: bool = False,
    ) -> None:
        effective_interval = self._presence_poll_interval if poll_interval is None else float(poll_interval)

        if self._presence_listener is None:
            self._presence_listener = PresenceListener(
                self,
                poll_interval=effective_interval,
                resolve_uuid=resolve_uuid,
                use_cache=use_cache,
                emit_initial=emit_initial,
            )
        else:
            self._presence_listener.update_settings(
                poll_interval=effective_interval,
                resolve_uuid=resolve_uuid,
                use_cache=use_cache,
                emit_initial=emit_initial,
            )

        if self._presence_listener.is_running:
            return

        self._presence_listener.start(daemon=daemon)

    def stop_chat_listener(self) -> None:
        if self._chat_listener is None:
            return
        if self._chat_listener.is_running:
            self._chat_listener.stop()
            self._chat_listener.join(timeout=5)

    def stop_presence_listener(self) -> None:
        if self._presence_listener is None:
            return
        if self._presence_listener.is_running:
            self._presence_listener.stop()
            self._presence_listener.join(timeout=5)

    def stop_listeners(self) -> None:
        self.stop_chat_listener()
        self.stop_presence_listener()

    def has_running_chat_listener(self) -> bool:
        return self._chat_listener is not None and self._chat_listener.is_running

    def has_running_presence_listener(self) -> bool:
        return self._presence_listener is not None and self._presence_listener.is_running

    def has_running_listeners(self) -> bool:
        return self.has_running_chat_listener() or self.has_running_presence_listener()
