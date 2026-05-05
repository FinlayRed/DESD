#  Django project!

The repo for our DESD project.

# Whats been done

- [x] Django project + Posgres setup
- [x] Containerize using a docker file
- [x] Create a docker-compose.yml with separated Nginx, Django, and PostgreSQL containers
- [x] One command start
- [x] Basic UI skeleton for demo
- [x] env setup
- [x] Documentation
- [x] Yas' Models
- [x] Get demo ready


# How to use

You will need docker installed. https://www.docker.com/products/docker-desktop/ is going to be the easiest.

# Quickstart
Make sure you're running this in the directory.

```bash
cp .env.example .env 
docker compose up --build
```

Defaults to port 8000 so http://127.0.0.1:8000/ to access the website.

Docker starts three services:

- `nginx`: public web server and reverse proxy
- `web`: Django application served with Gunicorn
- `db`: PostgreSQL database
