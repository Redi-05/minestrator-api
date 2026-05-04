from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import requests


@dataclass(slots=True, frozen=True)
class MinecraftUser:
    """Minecraft player identity used across the library."""
    username: str
    uuid: str

    def __post_init__(self) -> None:
        # Juste de la validation basique, pas d'appels réseau ici !
        object.__setattr__(self, "username", self.username.strip())
        object.__setattr__(self, "uuid", self.uuid.strip())

    @classmethod
    def create_from_username(cls, username: str) -> "MinecraftUser":
        """Create a MinecraftUser from a username using the Mojang API."""
        username = username.strip()
        resp = requests.get(f"https://api.mojang.com/users/profiles/minecraft/{username}")
        if resp.status_code == 200:
            return cls(username=username, uuid=resp.json()["id"])
        raise ValueError(f"Pseudo introuvable : {username}")

    @classmethod
    def create_from_uuid(cls, uuid: str) -> "MinecraftUser":
        """Create a MinecraftUser from a UUID using the Mojang API."""
        uuid = uuid.strip()
        resp = requests.get(f"https://sessionserver.mojang.com/session/minecraft/profile/{uuid}")
        if resp.status_code == 200:
            return cls(username=resp.json()["name"], uuid=uuid)
        raise ValueError(f"UUID introuvable : {uuid}")

    @property
    def avatar_url(self) -> str:
        return f"https://mc-heads.net/avatar/{self.uuid}"

    @property
    def skin_url(self) -> str:
        return f"https://mc-heads.net/body/{self.username}"
    
    def __str__(self) -> str:
        return self.username or self.uuid or "UnknownPlayer"


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
        """True when the endpoint is available."""
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
    """Typed snapshot from /server/<id>/live endpoint."""

    status: str | None
    state: str | None
    version: str | None
    hostname: str | None
    cpu_current: int
    cpu_dedicated: int
    cpu_flexcore: int
    cpu_limit: int
    cpu_percent: float
    cpu_is_bursting: bool
    memory_current_mb: int
    memory_limit_mb: int
    memory_percent: float
    disk_current_mb: int
    disk_limit_mb: int
    disk_percent: float
    network_received_bytes: int
    network_transmitted_bytes: int
    uptime_seconds: int
    players_current: int
    players_limit: int
    players: list[MinecraftUser]


@dataclass(slots=True, frozen=True)
class MinestratorConsoleLine:
    """Console or chat line parsed from the websocket stream."""

    content: str
    raw_line: str
    received_at: datetime
    author: MinecraftUser | None = None
    is_chat: bool = False



