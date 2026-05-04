# minestrator-api

Object-oriented Python client for the Minestrator API.

This project is designed as a clean pip package with a readable multi-file architecture.

## Features

- Clean package layout ready for publishing on PyPI.
- Typed models for servers, players, files, addons, and stats.
- Automatic conversion to `MinecraftUser` objects in player-related APIs.
- Full access to SFTP credentials from API payloads without implementing SFTP transport.
- Simple websocket-based access to console chat.

## Installation

```bash
pip install minestrator-api
```

Chat access requires an optional dependency:

```bash
pip install minestrator-api[realtime]
```

## Quick Start

```python
from minestrator_api import Client

client = Client(api_key="YOUR_API_KEY", user_id=<USER_ID>)
server = client.server(<SERVER_ID>)

print(server.server_name)
print(server.status)
print(server.version)

for player in server.get_online_players():
	print(player.username, player.uuid)
```

## Chat Access

```python
from minestrator_api import Client

client = Client(api_key="YOUR_API_KEY", user_id=<USER_ID>)
server = client.server(<SERVER_ID>)

for line in server.iter_chat_messages(send_logs=True):
  print(f"<{line.author.username}> {line.content}")
```

## Main Endpoints Covered

- `GET /server/{id}`
- `GET /server/{id}/live`
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
```

AI were used in this project