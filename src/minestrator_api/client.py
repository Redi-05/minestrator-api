from __future__ import annotations

from typing import Any

import requests

from ._http import HttpClient
from ._utils import parse_int
from .models import MinestratorServerSummary
from .server import Server


class Client:
    """Top-level API client used to create Server objects."""

    def __init__(
        self,
        *,
        api_key: str,
        user_id: str | int | None = None,
        base_url: str = "https://mine.sttr.io",
        websocket_origin: str | None = "https://pteroapi.minestrator.com",
        timeout: float = 10.0,
        session: requests.Session | None = None,
        resolve_player_uuids: bool = True,
        presence_poll_interval: float = 2.0,
    ) -> None:
        cleaned_key = api_key.strip()
        if not cleaned_key:
            raise ValueError("api_key is required")

        self._user_id = str(user_id).strip() if user_id is not None else None
        self._websocket_origin = websocket_origin
        self._resolve_player_uuids = bool(resolve_player_uuids)
        self._presence_poll_interval = max(1.0, float(presence_poll_interval))

        self._http = HttpClient(
            api_key=cleaned_key,
            base_url=base_url,
            timeout=timeout,
            session=session,
        )
        self._servers: dict[str, Server] = {}

    @property
    def user_id(self) -> str | None:
        return self._user_id

    @property
    def base_url(self) -> str:
        return self._http.base_url

    @property
    def timeout(self) -> float:
        return self._http.timeout

    def __enter__(self) -> Client:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def close(self) -> None:
        for server in list(self._servers.values()):
            server.close()
        self._http.close()

    def server(self, server_id: str | int) -> Server:
        normalized_id = str(server_id).strip()
        if not normalized_id:
            raise ValueError("server_id is required")

        if normalized_id in self._servers:
            return self._servers[normalized_id]

        server = Server(
            self._http,
            normalized_id,
            user_id=self._user_id,
            websocket_origin=self._websocket_origin,
            resolve_player_uuids=self._resolve_player_uuids,
            presence_poll_interval=self._presence_poll_interval,
        )
        self._servers[normalized_id] = server
        return server

    def get_server(self, server_id: str | int) -> Server:
        return self.server(server_id)

    def list_servers(self, user_id: str | int | None = None) -> list[MinestratorServerSummary]:
        resolved_user_id = str(user_id).strip() if user_id is not None else self._user_id
        if not resolved_user_id:
            raise ValueError("user_id is required for /user/{id}/servers")

        data = self._http.request_data("GET", f"/user/{resolved_user_id}/servers")
        raw_servers = data.get("servers")
        if not isinstance(raw_servers, list):
            return []

        result: list[MinestratorServerSummary] = []
        for item in raw_servers:
            if not isinstance(item, dict):
                continue

            server_id_value = parse_int(item.get("id"), -1)
            name = item.get("name")
            if server_id_value < 0 or not isinstance(name, str) or not name.strip():
                continue

            dns_raw = item.get("dns")
            ip_raw = item.get("ip")
            port_raw = item.get("port")

            dns = dns_raw.strip() if isinstance(dns_raw, str) and dns_raw.strip() else None
            ip = ip_raw.strip() if isinstance(ip_raw, str) and ip_raw.strip() else None
            parsed_port = parse_int(port_raw, -1)
            port = parsed_port if parsed_port >= 0 else None

            owner_value: bool | None
            if "owner" in item:
                owner_value = bool(parse_int(item.get("owner"), 0))
            else:
                owner_value = None

            result.append(
                MinestratorServerSummary(
                    id=server_id_value,
                    name=name.strip(),
                    dns=dns,
                    ip=ip,
                    port=port,
                    is_disabled=bool(parse_int(item.get("is_disabled"), 0)),
                    is_suspended=bool(parse_int(item.get("is_suspended"), 0)),
                    is_expired=bool(parse_int(item.get("is_expired"), 0)),
                    owner=owner_value,
                )
            )

        return result

    def request_raw(
        self,
        method: str,
        route: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._http.request_raw(
            method,
            route,
            params=params,
            json_body=json_body,
        )
