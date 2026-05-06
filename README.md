# DESD Django Project

This is the DESD project repository. It is a Django app that runs with Docker Compose behind an Nginx reverse proxy.

## Requirements

- Docker Desktop, recommended for the easiest setup: <https://www.docker.com/products/docker-desktop/>
- Git

## Workspace Setup

Clone the repository, then open the project folder in your editor or terminal.

```bash
git clone <repository-url>
cd DESD
```

Create your environment file from the example:

```bash
cp .env.example .env
```

The default `.env.example` values are suitable for local Docker development.

## Start With Docker

Docker is the recommended way to run the project because it starts Django, PostgreSQL, and Nginx together. Nginx is the public entry point on port `8000` and proxies requests to the internal Django/Gunicorn service.

```bash
docker compose up --build
```

Open the site at:

```text
http://127.0.0.1:8000/
```

Docker starts these services:

- `nginx`: public web server and reverse proxy, exposed at `http://127.0.0.1:8000/`
- `web`: internal Django application served with Gunicorn on port `8000`
- `db`: PostgreSQL database

Stop the project with:

```bash
docker compose down
```

## Useful Docker Commands

Run database migrations:

```bash
docker compose exec web python manage.py migrate
```

Create an admin user:

```bash
docker compose exec web python manage.py createsuperuser
```

Seed demo data:

```bash
docker compose exec web python manage.py seed_demo_data
```

Manual testing flow for the seeded data:

```text
docs/manual-testing-flow.md
```

Run tests:

```bash
docker compose exec web python manage.py test
```

View logs:

```bash
docker compose logs -f
```


## Environment Variables

The project reads environment variables from `.env` when using Docker Compose.

- `SECRET_KEY`: Django secret key
- `DEBUG`: set to `1` for local debug mode or `0` for production-like mode
- `ALLOWED_HOSTS`: comma-separated hosts, for example `127.0.0.1,localhost`
- `DB_NAME`: PostgreSQL database name
- `DB_USER`: PostgreSQL username
- `DB_PASS`: PostgreSQL password

## Nginx Configuration

The Nginx configuration lives in `nginx/default.conf`. Docker Compose mounts it into the `nginx` container and forwards all requests to the `web` service.
