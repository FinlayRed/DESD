# DESD Django Project

This is the DESD project repository. It is a Django app that can run with Docker Compose

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

Docker is the recommended way to run the project because it starts Django, PostgreSQL, and Nginx together.

```bash
docker compose up --build
```

Open the site at:

```text
http://127.0.0.1:8000/
```

Docker starts these services:

- `nginx`: public web server and reverse proxy
- `web`: Django application served with Gunicorn
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
