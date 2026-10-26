# Results Management System

A small Flask + MySQL web app for recording students, courses and exam results, with
automatic grading and a per-student transcript with GPA. It runs as two containers:
`web` (Flask served by gunicorn) and `db` (MySQL 8.0 with a persistent volume).

## Run it

```bash
cp .env.example .env        # then edit .env and change every password
docker compose up --build
```

Open <http://localhost> and sign in with `ADMIN_USER` / `ADMIN_PASSWORD` from `.env`.

If port 80 is already in use on your machine, change `"80:80"` in `docker-compose.yml`
to something like `"8080:80"` and open <http://localhost:8080>.

Useful commands:

```bash
docker compose logs -f web      # watch the app logs
docker compose down             # stop, keep the data
docker compose down -v          # stop AND delete the database volume
```

## What it does

- **Students**: add, list, delete; each has a transcript page.
- **Courses**: add, list, delete; each has a credit-unit value.
- **Results**: record coursework (max 40) and exam (max 60); the total, letter grade and
  grade point are computed automatically. Saving again for the same student and course
  replaces the earlier marks.
- **Transcript**: all of a student's results with credit-weighted GPA.

## Grading scale

Defined in `app/grading.py` (5.0 scale): A 80+, B+ 75, B 70, C+ 65, C 60, D+ 55, D 50,
E below 50. Check it against Kabale University's official regulations and edit `SCALE`,
`MAX_COURSEWORK` and `MAX_EXAM` if they differ.

## Layout

```
docker-compose.yml     db + web services, volume, healthcheck
.env.example           settings to copy into .env
app/
  app.py               routes, login, CSRF protection
  grading.py           mark validation, grade scale, GPA
  db.py                MySQL connection helper
  init_db.py           creates the tables on start-up
  schema.sql           table definitions
  templates/ static/   pages and styling
```

## Ideas for next steps

Semester / academic-year on each result, student and lecturer accounts instead of a single
admin login, CSV import of marks, PDF transcripts, pagination on the results list.
