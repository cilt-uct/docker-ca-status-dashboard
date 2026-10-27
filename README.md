# Capture Agent Status Dashboard

A Docker Compose application that displays the availability of lecture venues and their Opencast capture agents. A scheduled service polls Opencast and stores agent names and status in Redis; a FastAPI service serves the dashboard and a JSON API.

This is the codebase for https://recording.uct.ac.za/.

## Services

- `scheduled_service` loads capture-agent details on startup, refreshes details hourly, and refreshes agent state every five minutes.
- `ui_service` serves the dashboard at `/`, provides the agent API, and reports service metadata at `/status`.
- `redis` stores the agent index, agent data, refresh timestamp, and service start times.

The dashboard displays venue code, venue name, and status, with counts and filters for Online, Recording, and Offline agents. Opencast is required for the scheduler to populate the dashboard.

## Requirements

- Docker Engine and Docker Compose v2
- An Opencast server with credentials that can access its capture-agent endpoints

## Run with Docker Compose

1. Create the Compose environment file:

   ```sh
   cp .env.template .env
   ```

2. Create the secret files at the paths configured in `docker-compose.yml`:

   ```sh
   sudo mkdir -p /usr/local/serverconfig
   sudo cp secrets/recording.cfg.example /usr/local/serverconfig/recording.cfg
   sudo cp secrets/redis_password.example /usr/local/serverconfig/recording_redis_password
   ```

   Edit `recording.cfg` with the Opencast URL, username, and password. Replace the example Redis password with a private value. The Redis secret must contain only the password on one line. The Compose file mounts these host files as `/run/secrets/passwords` and `/run/secrets/redis_password` inside the services.

3. Review `.env` before starting. In particular, `REDIS_CLEAN_START=True` clears the Redis database whenever the scheduler starts. Set it to `False` to retain existing Redis data.

4. Build and start the services:

   ```sh
   docker compose up --build -d
   ```

5. Open <http://localhost:8000/>. Check service logs with:

   ```sh
   docker compose logs -f scheduled_service ui_service redis
   ```

## Configuration

The runtime settings are defined in `utils/settings.py`. Compose reads `.env` for general settings and mounts Opencast and Redis credentials as Docker secrets.

| Setting | Purpose | Default |
| --- | --- | --- |
| `ENV` | Environment label returned by `/status` | `dev` |
| `DEBUG` | Debug mode | `False` |
| `RUNNING_IN_DOCKER` | Docker runtime indicator | `False` |
| `ROOT_PATH` | ASGI root path | `/` |
| `REDIS_HOST` | Redis hostname | `localhost` |
| `REDIS_PORT` | Redis port | `6379` |
| `REDIS_CLEAN_START` | Clear the Redis database on scheduler startup | `False` |
| `OC_SERVER` | Opencast base URL | `http://localhost` |
| `OC_USER` | Opencast username | `opencast` |
| `OC_PASS` | Opencast password | `password` |
| `CONTACT_EMAIL` | Helpdesk contact setting | `helpdesk@example.com` |

In Compose, `REDIS_HOST` is set to `redis`. `OC_SERVER`, `OC_USER`, and `OC_PASS` are read from the `recording.cfg` secret file. Redis reads its password from the `redis_password` secret. Do not commit populated secret files or real credentials.

## How Data Is Refreshed

At startup, the scheduler fetches capture-agent names, capabilities, and current status from Opencast, then writes the configured agents to Redis. It refreshes agent details every hour and current state every five minutes. The UI reads the agent index and details from Redis; it does not call Opencast for each page request.

## HTTP Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | Dashboard HTML |
| `GET` | `/api/agents` | Capture-agent data, count, last refresh time, and version/ETag |
| `GET` | `/status` | Service version, environment, runtime flags, and service start times |
| `GET` | `/robots.txt` | Robots policy |
| `GET` | `/humans.txt` | Site and team information |

Example requests:

```sh
curl http://localhost:8000/status
curl -i http://localhost:8000/api/agents
```

The `/api/agents` response includes `status`, `agents`, `total`, `last_refresh`, and `version`. Each agent contains `name`, `display`, `state`, `time_since_last_update`, and `last_updated`. The endpoint returns an ETag and a `Cache-Control: no-cache, must-revalidate` header.

## Local Development

The root `requirements.txt` contains development tooling. Runtime dependencies are in `scheduled_service/requirements.txt` and `ui_service/requirements.txt`.

Run the scheduler from the repository root so the `opencast` and `utils` packages are importable. Run the UI from its service directory with the repository root on `PYTHONPATH`. Both processes need a reachable Redis instance and the same Opencast settings used by the Compose deployment.

```sh
python -m pip install -r scheduled_service/requirements.txt -r ui_service/requirements.txt

# Terminal 1, from the repository root
PYTHONPATH=. python scheduled_service/scheduler.py

# Terminal 2, from the repository root
cd ui_service
PYTHONPATH=.. python main.py
```

## Troubleshooting

- **Opencast requests fail:** Check `OC_SERVER`, `OC_USER`, and `OC_PASS` in `/usr/local/serverconfig/recording.cfg`, and verify that the server is reachable from the containers.
- **Redis authentication fails:** Check that the secret file contains the Redis password as a single line and that it matches the password used by Redis.
- **The dashboard has no agents:** Check scheduler logs and `/status`; confirm the Opencast endpoints are accessible and that the agents are included in Opencast's capture-agent name list.
- **Redis reports `exec /redis-entrypoint.sh: no such file or directory`:** Ensure `redis-entrypoint.sh` has Unix (LF) line endings. `.gitattributes` enforces LF for this script. Recreate Redis after correcting it:

  ```sh
  docker compose up -d --no-deps --force-recreate redis
  docker compose logs --tail=50 redis
  ```

## Project Structure

```text
.
├── scheduled_service/   # Opencast polling scheduler and Dockerfile
├── ui_service/          # FastAPI app, templates, assets, and Dockerfile
├── opencast/            # Opencast API client and capture-agent model
├── utils/               # Shared settings and REST client
├── secrets/             # Example secret files only
├── docker-compose.yml
├── redis-base.conf
└── redis-entrypoint.sh
```

## Development Checks

Install the repository tooling and run the configured pre-commit hooks:

```sh
python -m pip install -r requirements.txt
pre-commit install
pre-commit run --all-files
```

## License

This project is licensed under the Educational Community License, Version 2.0 (**ECL-2.0**). See [LICENSE](LICENSE) for details.
