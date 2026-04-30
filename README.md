# minestrator-api

Object-oriented Python client for the Minestrator API.

This project is designed as a clean pip package with a readable multi-file architecture.

## Features

- Clean package layout ready for publishing on PyPI.
- Typed models for servers, players, files, addons, stats, and chat messages.
- Decorator-based listeners for chat, join, leave, status updates, and listener errors.
- Automatic conversion to `MinecraftUser` objects in player-related APIs and events.
- Full access to SFTP credentials from API payloads without implementing SFTP transport.

## Installation

```bash
pip install minestrator-api
```

Realtime websocket listeners need an optional dependency:

```bash
pip install minestrator-api[realtime]
```

## Quick Start

```python
from minestrator_api import Client

client = Client(api_key="YOUR_API_KEY", user_id=229306)
server = client.server(353794)

print(server.server_name)
print(server.status)
print(server.version)

for player in server.get_online_players():
	print(player.username, player.uuid)
```

## Listener Style API

```python
from minestrator_api import Client

client = Client(api_key="YOUR_API_KEY", user_id=229306)
server = client.server(353794)


@server.on_chat_message()
def handle_chat(message):
	print(f"[CHAT] {message.author.username}: {message.content}")


@server.on_player_join(emit_initial=True)
def handle_join(user):
	print(f"[JOIN] {user.username}")


@server.on_player_leave()
def handle_leave(user):
	print(f"[LEAVE] {user.username}")


@server.on_status_update()
def handle_status(old_status, new_status):
	print(f"Status changed: {old_status} -> {new_status}")


@server.on_listener_error()
def handle_listener_error(exc, source):
	print(f"Listener error from {source}: {exc}")
```

Listeners start automatically when decorators are registered.
No explicit `wait_forever()` helper is required.

By default listeners run in non-daemon threads, so the process stays alive while listeners are active.

To stop listeners explicitly:

```python
server.stop_listeners()
client.close()
```

## Generic Event Decorator

You can also register events with one generic decorator. The callback name must match a supported event.

```python
@server.event
def on_chat_message(message):
	print(message.content)
```

Supported event names:

- `on_chat_message`
- `on_system_message`
- `on_player_join`
- `on_player_leave`
- `on_status_update`
- `on_listener_error`

## Main Endpoints Covered

- `GET /server/{id}`
- `GET /server/{id}/live/light`
- `GET /server/{id}/properties`
- `GET /server/{id}/files/list/{path}`
- `GET /server/{id}/files/content/{path}`
- `GET|POST /server/{id}/files/exists`
- `GET /server/{id}/plugins`
- `GET /server/{id}/mods`
- `GET /server/{id}/stats/{start}/{end}`
- `PUT /server/{id}/command`
- `GET /user/{id}/servers`
- `GET /user/{id}/servers/websocket`

## SFTP Credentials

The library intentionally does not implement SFTP transport.
It only exposes credentials so users can connect with their own SFTP tooling.

```python
creds = server.get_sftp_credentials()
if creds:
	print(creds.endpoint)
```

## Project Layout

```text
src/minestrator_api/
  __init__.py
  _http.py
  _utils.py
  client.py
  errors.py
  models.py
  server.py
  listeners/
	__init__.py
	chat.py
	presence.py
```

AI where used in this project