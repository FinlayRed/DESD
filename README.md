#  Django project!!!1

The repo for our DESD project.

# Whats been done

- [x] Django project + Posgres setup
- [x] Containerize using a docker file
- [x] Create a docker-compose.yml with containers for db and django
- [x] One command start
- [x] Basic UI skeleton for demo
- [x] env setup
- [ ] Documentation
- [ ] Get demo ready


# How to use

You will need docker installed. https://www.docker.com/products/docker-desktop/ is going to be the easiest.

# Quickstart
Make sure you're running this in the directory!

```bash
cp .env.example .env 
docker compose up --build
```

Defaults to port 8000 so http://127.0.0.1:8000/ to access the website. 

# Yas' additions

Okay so once youve got an idea of the database design / schema you have to implement it in `models.py` as a python class. The way django works is the database is handled in the code as python classes / objects rather then using SQL (THANK GOD). These classes are then translated by django automatically into sql and is synced to the postgres db (this is all done for us so we should hopefully never have to use SQL directly unless we're debugging). LLM's will help you translate a schema to the `models.py` django format if you get stuck but it doesnt look too scary so you should be fine.

For the login auth, ive created a placeholder UI templates for the login and regiser pages in `/templates/core/producer_login.html` and `/templates/core/producer_register.html`. You'll need to create classs in `forms.py` that handles recives the data input in the html forms from the templates. After that im not too sure how you validate but thats your problem(SORRY). I think there's some built in `UserCreationForm` and `AuthenticateForm` things in django for this but I could be lying. If you need me to change any of my stuff or need a hand with anything lemme know!