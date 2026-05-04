# Minstrator api unofficial doc
This api is not complete and may be subject to future changes.
Feel free to contact me on discord (redi_05 - 695285554161385553) if you found any issue or if you want to contribute.

## Header
Each request should have this header :
```json
"Authorization": "Bearer <api_key>",
"Content-Type": "application/json"
```

## Endpoints
Most HTTP responses follow this structure:

```json
{
  "api": {
    "description": "Human-readable endpoint description",
    "endpoint": "/path/of/the/request",
    "data": {...}, // The actual response data, structure varies by endpoint
    "code": 200
  }
}
```

Here are some examples of responses from various endpoints:

`https://mine.sttr.io//server/<server_id>/files/exists?files=path/to/file1.txt,path/to/file2.txt`
```json
{
    "api": {
        "description": "Server - Files - Check if files exist",
        "endpoint": "\/server\/<server_id>\/files\/exists",
        "data": {
            "exists": {
                "file1.txt": true,
                "file2.txt": false,
            }
        },
        "code": 200
    }
}
```

`https://mine.sttr.io//server/<server_id>/files/content/path/to/file.json`
```json
{
    "api": {
        "description": "Server - Files - Get file content",
        "endpoint": "\/server\/<server_id>\/files\/content\/path\/to\/file.json",
        "data": {
            "content": "[\n  {\n    \"example\": \"hey !\",\n    \"text\": \"this is the content of the file !\",\n  },\n  {\n    \"second_line\": \"some text\",\n  }\n]"
        },
        "code": 200
    }
}
```

`https://mine.sttr.io//user/<user_id>/servers`
```json
{
    "api": {
        "description": "User - Servers - Get user servers",
        "endpoint": "\/user\/<user_id>\/servers",
        "data": {
            "servers_groups": {
                "<box_id>": {
                    "id": 12345,
                    "owner": 0,
                    "owner_name": "name", // this field is only present if the user is not the owner of the box
                    "name": "Ma MyBox",
                    "hashsupport": "ABCDE",
                    "order": 0,
                    "mybox": 1,
                    "tend": "2026-05-20 14:22:00",
                    "offer": "MyBoxPart 64",
                    "note": "",
                    "is_free": 0,
                    "is_pro": 0,
                    "is_expired": 0,
                    "is_suspended": 0,
                    "promo_recurrent": null,
                    "promo_reduction": null,
                    "resources": {
                        "cpu": 16,
                        "ram": 64,
                        "disk": 500
                    },
                    "permissions": [
                        "view"
                    ],
                    "servers": [
                        {
                            "id_server": <server_id>,
                            "permissions": [
                                "view",
                                "server_name",
                                "settings_view",
                                "settings_edit",
                                "sftp",
                                "command",
                                "poweraction_start",
                                "poweraction_restart",
                                "poweraction_stop",
                                "poweraction_kill",
                                "players",
                                "players_kick",
                                "players_ban",
                                "players_whitelist",
                                "players_operator",
                                "version",
                                "ports_view",
                                "ports_edit",
                                "dns",
                                "livemap",
                                "saves_view",
                                "saves_restore",
                                "saves_download",
                                "plugins",
                                "schedules_view",
                                "schedules_edit"
                            ]
                        }
                    ]
                }
            },
            "servers": [
                {
                    "id": <server_id>,
                    "hashsupport": "ABCDE",
                    "id_mybox": 12345,
                    "id_daemon": 1234,
                    "tstart": "2025-08-21 14:22:00",
                    "tend": "2026-05-20 14:22:00",
                    "ip": "xxx.xxx.xxx.xxx",
                    "port": 12345,
                    "dns": "something.mine.fun",
                    "is_free": 0,
                    "hibernation": 0,
                    "id_groupe": 0,
                    "note": "",
                    "id_egg": 1,
                    "is_disabled": 0,
                    "name": "name",
                    "owner": 0,
                    "is_bedrock": 0,
                    "egg_uuid": "<uuid>",
                    "egg_name": "Minecraft",
                    "egg_icon": "minecraft.webp",
                    "is_expired": 0,
                    "is_suspended": 0,
                    "reduction": 0,
                    "poweraction_message_restart": "",
                    "poweraction_message_stop": ""
                }
            ]
        },
        "code": 200
    }
}
```

`https://mine.sttr.io//user/<user_id>/servers/websocket`
```json
{
    "api": {
        "description": "User - Get all websocket credentials",
        "endpoint": "\/user\/<user_id>\/servers\/websocket",
        "data": {
            "servers": [
                {
                    "id": 123456,
                    "uuid": "8b3b705c",
                    "name": "name",
                    "mybox_id": 12345,
                    "socket": "wss:\/\/xx.mystrator.com:xx\/api\/servers\/xxxx\/ws",
                    "token": "token"
                }
            ],
            "count": 1
        },
        "code": 200
    }
}
```

`https://mine.sttr.io//server/<server_id>`
```json
{
    "api": {
        "description": "Server - Actions - Get datas",
        "endpoint": "\/server\/<server_id>",
        "data": {
            "websocket": {
                "url": "wss:\/\/xx.mystrator.com:xx\/api\/servers\/xxxx\/ws",
                "token": "token"
            },
            "options": [],
            "mybox": {
                "name": "name",
                "hashsupport": "ABCDE",
                "resources": {
                    "cpu": 2,
                    "ram": 10,
                    "disk": 50
                },
                "to_review": 0
            },
            "offer": {
                "name": "MyBox 10",
                "is_pro": 0,
                "is_trial": 0,
                "is_free": 0,
                "cpu": 2,
                "ram": 10,
                "disk": 50
            },
            "egg": {
                "id": 1,
                "type": 1,
                "name": "Minecraft",
                "icon": "minecraft.webp",
                "uuid": "uuid"
            },
            "settings": {
                "poweraction_message": {
                    "restart": "",
                    "stop": ""
                },
                "is_bedrock": 0,
                "is_bungeecord": 0,
                "java_memory": 30,
                "image": "reg.sttr.io\/java\/21_perf:latest",
                "id_java_version": 57,
                "startup": "java -Xms128M -Xmx7877M -Dterminal.jline=false -Dterminal.ansi=true -Djline.terminal=jline.UnsupportedTerminal -jar {{SERVER_JARFILE}}",
                "startup_file": "server.jar"
            },
            "history": [
                {
                    "date": "2026-03-22 10:39:37.107",
                    "ip": "xxx.xxx.xxx.xxx",
                    "action": "power.start"
                },
                {
                    "date": "2026-03-22 10:39:22.864",
                    "ip": "xxx.xxx.xxx.xxx",
                    "action": "power.stop"
                },
            ],
            "ports": [
                {
                    "port": 30338,
                    "ip": "xxx.xxx.xxx.xxx",
                    "description": "rcon"
                }
            ],
            "sftp": {
                "protocol": "sftp",
                "host": "5037.mystrator.com",
                "port": 2022,
                "user": "username",
                "password": "password"
            },
            "livemap": {
                "option": 0,
                "enabled": 0,
                "is_free": 0
            },
            "server": {
                "id": 123456,
                "hashsupport": "ABCDE",
                "id_mybox": 12345,
                "id_daemon": 5037,
                "tstart": "2025-07-23 18:35:47",
                "tend": "2027-07-23 18:32:20",
                "ip": "xxx.xxx.xxx.xxx",
                "port": 25652,
                "dns": "something.mine.fun",
                "is_free": 0,
                "hibernation": 0,
                "id_groupe": 0,
                "ordre": 0,
                "name": "name",
                "uuid": "uuid",
                "dedicated_ip": 0,
                "owner": 1,
                "permissions": []
            }
        },
        "code": 200
    }
}
```

`https://mine.sttr.io//server/<server_id>/live`
```json
{
    "api": {
        "description": "Server - Actions - Get live datas",
        "endpoint": "/server/<server_id>/live",
        "data": {
            "state": "online", // "online" | "offline" (maybe other)
            "status": null, // null : serveur operationel, "installing" : serveur en cours d'installation, "install_failed" : échec de l'installation, "suspended" : serveur suspendu
            "stats": {
                "state": "online",
                "cpu": {
                    "current": 0.162,
                    "dedicated": 200,
                    "flexcore": 100,
                    "limit": 300,
                    "percent": 0,
                    "is_bursting": false
                },
                "memory": {
                    "current": 4851,
                    "limit": 10000,
                    "percent": 47
                },
                "disk": {
                    "current": 25891,
                    "limit": 50500,
                    "percent": 51
                },
                "network": {
                    "rx_bytes": 720869732,
                    "tx_bytes": 9713601070
                },
                "uptime": {
                    "days": 2,
                    "hours": 7,
                    "minutes": 6,
                    "total_seconds": 198361
                },
                "players": {
                    "current": 0,
                    "limit": 42,
                    "list": []
                },
                "version": "1.21.11",
                "hostname": "motd"
            }
        },
        "code": 200
    }
}
```

`https://mine.sttr.io//server/<server_id>/live/light`
```json
{
    "api": {
        "description": "Server - Actions - Get live datas (light)",
        "endpoint": "\/server\/<server_id>\/live\/light",
        "data": {
            "status": null, // null : serveur operationel, "installing" : serveur en cours d'installation, "install_failed" : échec de l'installation, "suspended" : serveur suspendu
            "cpu": {
                "dedicated": 200,
                "flexcore": 100,
                "limit": 300
            },
            "disk": {
                "limit": 50500
            },
            "memory": {
                "limit": 10000
            },
            "players": {
                "current": 1,
                "limit": 42,
                "list": [
                    "Redi_05"
                ]
            },
            "version": "1.21.11",
            "hostname": "motd"
        },
        "code": 200
    }
}
```

`https://mine.sttr.io//server/<server_id>/properties`
```json
{
    "api": {
        "description": "Server - Settings - Get server settings (server.properties)",
        "endpoint": "\/server\/<server_id>\/properties",
        "data": {
            "is_official": 1,
            "properties": {
                "accepts-transfers": "false",
                "allow-flight": "false",
                "allow-nether": "true",
                "broadcast-console-to-ops": "true",
                "broadcast-rcon-to-ops": "true",
                "bug-report-link": "",
                "debug": "false",
                "difficulty": "normal",
                "enable-code-of-conduct": "false",
                "enable-command-block": "false",
                "enable-jmx-monitoring": "false",
                "enable-query": "true",
                "enable-rcon": "true",
                "enable-status": "true",
                "enforce-secure-profile": "true",
                "enforce-whitelist": "true",
                "entity-broadcast-range-percentage": "100",
                "force-gamemode": "false",
                "function-permission-level": "2",
                "gamemode": "survival",
                "generate-structures": "true",
                "generator-settings": "{}",
                "hardcore": "false",
                "hide-online-players": "false",
                "initial-disabled-packs": "",
                "initial-enabled-packs": "vanilla",
                "level-name": "world",
                "level-seed": "1234567890",
                "level-type": "minecraft\\:normal",
                "log-ips": "true",
                "management-server-allowed-origins": "",
                "management-server-enabled": "false",
                "management-server-host": "localhost",
                "management-server-port": "0",
                "management-server-secret": "xxxxxxxxxxxx",
                "management-server-tls-enabled": "true",
                "management-server-tls-keystore": "",
                "management-server-tls-keystore-password": "",
                "max-chained-neighbor-updates": "1000000",
                "max-players": "42",
                "max-tick-time": "60000",
                "max-world-size": "29999984",
                "motd": "motd",
                "network-compression-threshold": "256",
                "online-mode": "true",
                "op-permission-level": "4",
                "pause-when-empty-seconds": "60",
                "player-idle-timeout": "5",
                "prevent-proxy-connections": "false",
                "pvp": "true",
                "query.port": "25652",
                "rate-limit": "0",
                "rcon.password": "password",
                "rcon.port": "30338",
                "region-file-compression": "deflate",
                "require-resource-pack": "false",
                "resource-pack": "",
                "resource-pack-id": "",
                "resource-pack-prompt": "",
                "resource-pack-sha1": "",
                "server-ip": "0.0.0.0",
                "server-port": "25652",
                "simulation-distance": "5",
                "spawn-animals": "true",
                "spawn-monsters": "true",
                "spawn-npcs": "true",
                "spawn-protection": "2",
                "status-heartbeat-interval": "0",
                "sync-chunk-writes": "true",
                "text-filtering-config": "",
                "text-filtering-version": "0",
                "use-native-transport": "true",
                "view-distance": "25",
                "white-list": "true"
            },
            "properties_type": "server_properties"
        },
        "code": 200
    }
}
```

`https://mine.sttr.io//server/<server_id>/files/list/path/to/folder`
```json
{
    "api": {
        "description": "Server - Files - Get files list from specific folder",
        "endpoint": "\/server\/<server_id>\/files\/list\/path\/to\/folder",
        "data": {
            "files": [
                {
                    "folder": 1,
                    "size": "",
                    "size_bytes": 4096,
                    "name": "Im_a_folder",
                    "created": "2026-03-22T10:39:37+01:00",
                    "modified": "2025-07-23T19:47:42+02:00"
                },
                {
                    "folder": 0,
                    "size": "2.65 Ko",
                    "size_bytes": 2712,
                    "name": "file.txt",
                    "created": "2026-03-22T10:39:47+01:00",
                    "modified": "2026-03-22T10:39:47+01:00"
                },
                // and so on... (list all files and folders in the directory)
            ]
        },
        "code": 200
    }
}
```

`\/server\/<server_id>\/stats\/2026-04-24T19:30:01\/2026-04-25T19:30:01`
```json
{
    "api": {
        "description": "Server - Actions - Get server stats",
        "endpoint": "\/server\/<server_id>\/stats\/2026-04-24T19:30:01\/2026-04-25T19:30:01",
        "data": {
            "stats": [
                {
                    "cpu": 0,
                    "ram": 0,
                    "disk": 0,
                    "players": 0,
                    "date": "2026-04-24 19:30:00"
                },
                {
                    "cpu": 0,
                    "ram": 0,
                    "disk": 0,
                    "players": 0,
                    "date": "2026-04-24 19:31:00"
                },
                // ...
                {
                    "cpu": 29, // percent of cpu usage
                    "ram": 3992, // Mb
                    "disk": 25466, // Mb
                    "players": 1,
                    "date": "2026-04-25 19:29:00"
                },
                {
                    "cpu": 0,
                    "ram": 0,
                    "disk": 0,
                    "players": 0,
                    "date": "2026-04-25 19:30:00"
                }
            ]
        },
        "code": 200,
        "cache": "MISS"
    }
}
```

`\/server\/<server_id>\/plugins`
```json
{
    "api": {
        "description": "Server - Plugins - Get plugins list installed on the server",
        "endpoint": "\/server\/<server_id>\/plugins",
        "data": {
            "plugins": [
                {
                    "name": "DiscordSRV",
                    "filename": "DiscordSRV-Build-1.28.0.jar_off",
                    "version": "1.28.0",
                    "enabled": false
                }
            ]
        },
        "code": 200
    }
}
```

`\/server\/<server_id>\/mods`
```json
{
    "api": {
        "description": "Server - Mods - Get mods list installed on the server",
        "endpoint": "\/server\/<server_id>\/mods",
        "code": 500,
        "error": "API_MODS_SCRIPT_ERROR: Directory not found"
    }
}
```



## Websocket console
Made by legeek01 - 563726267246182400
### Console d'un serveur
#### 1. Connexion
1. Récupérer le token du WebSocket
GET `https://mine.sttr.io/user/<id utilisateur>/servers/websocket`
Réponse :
```json
{
  "api": {
    "data": {
      "servers": [ // Liste des serveurs
        {
          "id": 000000, // ID du serveur
          "uuid": "xxxxxxxx", // UUID du serveur (pas utile dans notre cas)
          "name": "Mon serveur Minecraft", // Nom du serveur
          "mybox_id": 00000, // ID de la MyBox dans laquelle le serveur se trouve
          "socket":"wss://xxxx.mystrator.com:xxxxx/api/servers/xxxx/ws", // Lien de connexion du WebSocket
          "token":"gg" // Token de connexion au WebSocket
        }
      ],
      "count": 1 // Nombre de serveurs
      },
    "code":200 // OK
  }
}
```

2. Connexion au WebSocket
Établir une connexion WebSocket à l'adresse donnée dans la réponse API (pas besoin de headers), puis lors-ce que la connexion est faite (statut READY) envoyer le message suivant :
```json
{
  "event": "auth", // Nom de l'action (authentification)
  "args": [ "token" ] // Arguments (token)
}
```
Si l'auth est OK, le serveur va répondre :
```json
{ "event": "auth success" }
```
On peut désormais interagir avec la console.
Le serveur va envoyer ensuite deux autres messages :
```json
{ "event": "status", "args": [ "offline" ] } // Statut du serveur (Hors-ligne ici, car "offline")
```
Ce message sera envoyé chaque fois que le serveur change de statut.
```json
{ 
  "event":  "stats",
  "args": ["stats"] 
}
```
ATTENTION dans ce message les stats sont dans le texte "stats", qui ressemble au texte suivant :
```json
{
  "memory_bytes": 0, // Utilisation RAM en Bytes
  "memory_limit_bytes": 0, // Limitation RAM en Bytes
  "cpu_absolute": 0, // Utilisation CPU en pourcent d'utilisation
  "network": {
    "rx_bytes": 0, // Nombre de bytes envoyés
    "tx_bytes": 0 // Nombre de bytes reçus
  },
  "uptime": 0, // Durée d'allumage en secondes
  "state": "offline", // Statut
  "disk_bytes": 0 // Utilisation disque du serveur en bytes
}
```
Si le serveur est en marche, ce message sera envoyé toutes les secondes.

3. Ré-authentification
Au bout de 10 minutes, l'authentification va expirer et le serveur va envoyer le message suivant :
```json
{ "event": "token expiring" }
```
Il faut alors répéter les étapes de connexion avec l'acquisition d'un nouveau token. Nul besoin de répéter la connexion au WebSocket, on peut se ré-authentifier dans la même connexion.

#### 2. Réception des messages de la console
1. Réception des messages
À chaque nouvelle ligne dans la console, le serveur va envoyer le message suivant :
```json
{ "event": "console output", "args": [ "[12:25:55 INFO]: Preparing level \"world\"" ] }
```
2. Recevoir les anciens logs
Envoyer le message suivant :
```json
{ "event": "send logs" , "args": [] }
```
Le serveur va ensuite transmettre les anciens logs par les messages "console output".

#### 3. Envoyer des messages
PUT `https://mine.sttr.io/server/<id serveur>/command`
Avec comme body :
```json
{ "command": "list" } // On envoie la commande "list" par exemple
```
Si OK, l'API va répondre :
```json
{
  "api": {
    "code": 200
  }
}
```
La commande sera répétée dans la console par le serveur via le WebSocket.

