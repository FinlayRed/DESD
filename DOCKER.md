# Docker Guide

This document explains Docker basics and how Docker is set up in this Django project.

## What Docker is

Docker lets you run software in isolated environments called **containers**.

- **Image**: A read-only blueprint (like a template) for a container.
- **Container**: A running instance of an image.
- **Volume**: Persistent storage managed by Docker.
- **Network**: Private communication between containers.

Why use Docker:

- Same runtime on every machine.
- Easy onboarding for new developers.
- Keeps local host dependencies minimal.

## What a Dockerfile is

A `Dockerfile` is a step-by-step recipe for building an image.

In this project (`Dockerfile`):

1. Starts from `python:3.12-slim`.
2. Sets Python runtime env vars.
3. Sets working directory to `/app`.
4. Copies `requirements.txt` and installs dependencies.
5. Copies project source code.
6. Defines default command to run Django.

The output of building this file is the image used by the `web` service.

## What Docker Compose is

`docker-compose.yml` defines and runs multiple services together.

In this project it runs:

- `web`: Django app container.
- `db`: PostgreSQL container.

Compose also handles:

- Service networking (so Django can reach Postgres at host `db`).
- Startup ordering (`web` waits for healthy `db`).
- Port mapping (`8000` on your machine to `8000` in container).
- Persistent database storage via `postgres_data` volume.

## How Docker works in this project

### Services

- **web**
  - Built from `Dockerfile`.
  - Uses `entrypoint.sh` for boot automation.
  - Entrypoint waits for DB, runs migrations, optionally runs `collectstatic`, then starts the configured command.
  - Mounts the project folder into `/app` for live code edits.
  - Uses environment variables for Django settings.

- **db**
  - Uses `postgres:16-alpine` image.
  - Initializes DB/user/password from env vars.
  - Stores data in `postgres_data` so data survives container restarts.

### Environment variables

The app reads config from env vars in `config/settings.py`:

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASS`
- `RUN_COLLECTSTATIC` (set `1` to run collectstatic during boot)

Use `.env.example` as a template:

```bash
cp .env.example .env
```

Compose uses `.env` values automatically for substitutions.

## Common commands

Start everything:

```bash
docker compose up --build
```

Run in background:

```bash
docker compose up --build -d
```

Stop services:

```bash
docker compose down
```

Stop and remove DB data volume too:

```bash
docker compose down -v
```

View logs:

```bash
docker compose logs -f
```

Run Django management commands:

```bash
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py shell
```

## Files related to Docker in this repo

- `Dockerfile`: builds Django app image.
- `docker-compose.yml`: defines `web` + `db` services.
- `.dockerignore`: excludes unnecessary files from image build context.
- `.env.example`: sample environment variables.

## Typical development flow

1. `cp .env.example .env`
2. `docker compose up --build`
3. Open `http://127.0.0.1:8000/`
4. Edit code locally; changes are reflected through bind mount.
5. Stop with `docker compose down`.

## Production-oriented compose variant

This repo also includes `docker-compose.prod.yml` for a more production-like runtime:

- Uses `gunicorn` instead of Django dev server.
- Runs `migrate` and `collectstatic` before starting app server.
- Keeps Postgres on a named volume.
- Uses `DEBUG=0` by default.

Start it:

```bash
cp .env.example .env
docker compose -f docker-compose.prod.yml up --build -d
```

Stop it:

```bash
docker compose -f docker-compose.prod.yml down
```

Tune Gunicorn with:

- `GUNICORN_WORKERS` (default `3`)
- `GUNICORN_TIMEOUT` (default `120`)

## Troubleshooting

- Port 8000 already in use:
  - Stop conflicting process or change published port in `docker-compose.yml`.
- Database connection errors:
  - Check `db` container health and env variable values.
- Dependency changes not picked up:
  - Rebuild image: `docker compose up --build`.
