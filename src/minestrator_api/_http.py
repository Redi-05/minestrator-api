from __future__ import annotations

from typing import Any, Mapping

import requests

from .errors import MinestratorApiError, MinestratorNetworkError, MinestratorProtocolError


class HttpClient:
    """Small HTTP wrapper for Minestrator API calls."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout: float,
        session: requests.Session | None = None,
    ) -> None:
        cleaned_key = api_key.strip()
        if not cleaned_key:
            raise ValueError("api_key is required")

        cleaned_base = base_url.strip().rstrip("/")
        if not cleaned_base:
            raise ValueError("base_url is required")

        self._api_key = cleaned_key
        self._base_url = cleaned_base
        self._timeout = float(timeout)
        self._session = session or requests.Session()

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def timeout(self) -> float:
        return self._timeout

    @property
    def default_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def extract_api_code(api_section: Mapping[str, Any]) -> int:
        """Extract api.code as integer, defaulting to 200 when missing."""
        code_value = api_section.get("code")
        if isinstance(code_value, int):
            return code_value
        if isinstance(code_value, str):
            try:
                return int(code_value.strip())
            except ValueError:
                return 200
        return 200

    def close(self) -> None:
        self._session.close()

    def request_raw(
        self,
        method: str,
        route: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_route = route if route.startswith("/") else f"/{route}"
        url = f"{self._base_url}{normalized_route}"

        try:
            response = self._session.request(
                method=method.upper(),
                url=url,
                headers=self.default_headers,
                params=dict(params) if params else None,
                json=dict(json_body) if json_body else None,
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise MinestratorNetworkError(
                f"Network error on {method.upper()} {url}: {exc}"
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise MinestratorProtocolError(
                f"Invalid JSON response ({response.status_code}) from {url}"
            ) from exc

        if response.status_code >= 400:
            raise MinestratorApiError(
                f"HTTP error {response.status_code} on {method.upper()} {url}: {payload}"
            )

        if not isinstance(payload, dict):
            raise MinestratorProtocolError(
                f"Unexpected payload type from {method.upper()} {url}: {type(payload).__name__}"
            )

        return payload

    def request_api(
        self,
        method: str,
        route: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        allow_api_error: bool = False,
    ) -> dict[str, Any]:
        payload = self.request_raw(method, route, params=params, json_body=json_body)
        api_section = payload.get("api")
        if not isinstance(api_section, dict):
            raise MinestratorProtocolError('Missing "api" object in response payload')

        api_code = self.extract_api_code(api_section)
        if not allow_api_error and api_code >= 400:
            error_message = api_section.get("error")
            raise MinestratorApiError(
                f"API code {api_code} on {method.upper()} {route}: {error_message or api_section}"
            )

        return api_section

    def request_data(
        self,
        method: str,
        route: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        allow_api_error: bool = False,
    ) -> dict[str, Any]:
        api_section = self.request_api(
            method,
            route,
            params=params,
            json_body=json_body,
            allow_api_error=allow_api_error,
        )

        data = api_section.get("data")
        if not isinstance(data, dict):
            raise MinestratorProtocolError('Missing "api.data" object in response payload')

        return data
