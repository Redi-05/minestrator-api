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
        timeout: float = 10.0,
        session: requests.Session | None = None,
    ) -> None:
        """Create a client for the Minestrator API.

        Args:
            api_key (str): API token used for authentication.
            user_id (str | int | None): Optional user identifier for user endpoints.
            base_url (str): Base URL for the API.
            timeout (float): HTTP timeout in seconds.
            session (requests.Session | None): Optional requests session.

        Raises:
            ValueError: If api_key is empty.

        Returns:
            None
        """
        cleaned_key = api_key.strip()
        if not cleaned_key:
            raise ValueError("api_key is required")

        self._user_id = str(user_id).strip() if user_id is not None else None

        self._http = HttpClient(
            api_key=cleaned_key,
            base_url=base_url,
            timeout=timeout,
            session=session,
        )
        self._servers: dict[str, Server] = {}

    @property
    def user_id(self) -> str | None:
        """User identifier bound to this client."""
        return self._user_id

    @property
    def base_url(self) -> str:
        """Base URL used for API requests."""
        return self._http.base_url

    @property
    def timeout(self) -> float:
        """HTTP timeout in seconds."""
        return self._http.timeout

    def __enter__(self) -> Client:
        """Enter context manager and return self.

        Returns:
            Client: This client instance.
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
        """Close the client and all cached server objects.

        Returns:
            None
        """
        for server in list(self._servers.values()):
            server.close()
        self._http.close()

    def server(self, server_id: str | int) -> Server:
        """Get or create a Server object.

        Args:
            server_id (str | int): Server identifier.

        Returns:
            Server: Server object bound to the id.

        Raises:
            ValueError: If server_id is empty.
        """
        normalized_id = str(server_id).strip()
        if not normalized_id:
            raise ValueError("server_id is required")

        if normalized_id in self._servers:
            return self._servers[normalized_id]

        server = Server(
            self._http,
            normalized_id,
            user_id=self._user_id,
        )
        self._servers[normalized_id] = server
        return server

    def get_server(self, server_id: str | int) -> Server:
        """Alias for server().

        Args:
            server_id (str | int): Server identifier.

        Returns:
            Server: Server object bound to the id.
        """
        return self.server(server_id)

    def list_servers(self, user_id: str | int | None = None) -> list[MinestratorServerSummary]:
        """List servers accessible to a user.

        Args:
            user_id (str | int | None): User id to query.

        Returns:
            list[MinestratorServerSummary]: Server summaries.

        Raises:
            ValueError: If user_id is missing.
            MinestratorApiError: When the API returns an error payload.
        """
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
        """Send a raw request to any API route.

        Args:
            method (str): HTTP method.
            route (str): API route.
            params (dict[str, Any] | None): Query parameters.
            json_body (dict[str, Any] | None): JSON body.

        Returns:
            dict[str, Any]: Raw JSON payload.

        Raises:
            MinestratorApiError: When the API returns an error payload.
        """
        return self._http.request_raw(
            method,
            route,
            params=params,
            json_body=json_body,
        )
