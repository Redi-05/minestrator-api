from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(slots=True, frozen=True)
class MinecraftUser:
    """Minecraft player identity used across the library."""

    username: str
    uuid: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.username, str) or not self.username.strip():
            
            raise ValueError("username is required")
        object.__setattr__(self, "username", self.username.strip())
        if isinstance(self.uuid, str):
            cleaned_uuid = self.uuid.strip()
            object.__setattr__(self, "uuid", cleaned_uuid or None)

    @property
    def avatar_url(self) -> str | None:
        """Avatar URL from mc-heads when uuid is available."""
        if not self.uuid:
            return None
        return f"https://mc-heads.net/avatar/{self.uuid}"

    @property
    def skin_url(self) -> str:
        """Body render URL from mc-heads."""
        return f"https://mc-heads.net/body/{self.username}"

    def __str__(self) -> str:
        return self.username


@dataclass(slots=True, frozen=True)
class MinestratorWebsocketCredentials:
    """Credentials required to connect to server websocket."""

    url: str
    token: str


@dataclass(slots=True, frozen=True)
class MinestratorSftpCredentials:
    """SFTP credentials."""

    protocol: str
    host: str
    port: int
    username: str
    password: str

    @property
    def endpoint(self) -> str:
        """Human readable endpoint like sftp://user@host:port."""
        return f"{self.protocol}://{self.username}@{self.host}:{self.port}"


@dataclass(slots=True, frozen=True)
class MinestratorFileEntry:
    """Single file or folder entry."""

    name: str
    is_folder: bool
    size_text: str | None
    size_bytes: int
    created_at: str | None
    modified_at: str | None


@dataclass(slots=True, frozen=True)
class MinestratorAddon:
    """Plugin or mod entry returned by addon endpoints."""

    name: str
    filename: str | None
    version: str | None
    enabled: bool | None


@dataclass(slots=True, frozen=True)
class MinestratorAddonResult:
    """Addon query result with API metadata."""

    items: list[MinestratorAddon]
    api_code: int
    error: str | None = None

    @property
    def available(self) -> bool:
        return self.api_code < 400


@dataclass(slots=True, frozen=True)
class MinestratorStatPoint:
    """Single point in server stats timeline."""

    date: str
    cpu: int
    ram: int
    disk: int
    players: int


@dataclass(slots=True, frozen=True)
class MinestratorServerSummary:
    """Compact server entry from user servers endpoint."""

    id: int
    name: str
    dns: str | None
    ip: str | None
    port: int | None
    is_disabled: bool
    is_suspended: bool
    is_expired: bool
    owner: bool | None


@dataclass(slots=True, frozen=True)
class MinestratorLiveSnapshot:
    """Typed snapshot from /server/<id>/live/light endpoint."""

    status: str | None
    version: str | None
    hostname: str | None
    cpu_dedicated: int
    cpu_flexcore: int
    cpu_limit: int
    memory_limit_mb: int
    disk_limit_mb: int
    players_current: int
    players_limit: int
    players: list[MinecraftUser]


@dataclass(slots=True, frozen=True)
class MinestratorChatMessage:
    """Chat or system line normalized from websocket console output."""

    author: MinecraftUser
    content: str
    raw_line: str
    received_at: datetime
    payload: Mapping[str, Any]
    is_system: bool = False
