# IOE Pulchowk Alumni Tracking System

A campus-wide alumni tracking web application for the Department of Electronics &
Computer Engineering (DOECE), IOE Pulchowk Campus. Alumni sign in securely and
anyone can search the alumni directory across six filters.

Built with **Django 4.2** and inspired by the existing
[`naggynab/almuni-tracker`](https://github.com/naggynab/almuni-tracker) project
and the accompanying Alumni Tracker case study, rewritten cleanly with a stronger
authentication story and campus-wide (multi-faculty) search.

## Features

**Secure alumni sign-in** (via [django-allauth](https://docs.allauth.org/))
- Email + password with **mandatory email verification** and password reset
- **Google** sign-in (OAuth)
- Brute-force throttling (5 failed logins / 5 min)
- Alumni **claim** their pre-loaded record by confirming batch + field + last
  name + (roll number *or* date of birth) — stricter than the reference app,
  which authenticated on date of birth alone.

**Six-filter alumni search** (`/alumni/`)
| Filter | Field |
| --- | --- |
| Name | first / middle / last (each term matched across all name parts) |
| Batch | enrollment batch/year (e.g. `078`) |
| Field of study | Computer, Electronics, Electrical, Civil, Mechanical, Architecture, Aerospace, Chemical, Science |
| Current city | city the alumnus currently lives in |
| Works at | employer / organization |
| Country | country the alumnus is currently in |

Filters combine, paginate, and preserve state across pages.

**Self-service profiles** — once linked, alumni edit their own employment,
location, further-study and contact details, and can make their record private.

## Project layout

```
alumni_tracker/     Django project settings, root URLs
directory/          Alumnus model, search filters, directory views
  ├─ choices.py     canonical fields of study + normalisers for messy source data
  ├─ filters.py     the six-filter FilterSet
  └─ management/commands/import_alumni.py
accounts/           account claim + profile-edit flow (auth via allauth)
templates/          base layout, directory pages, and custom auth pages
data/               seed data sources (CSV roster + DOECE JSON dump)
```

## Getting started

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then edit SECRET_KEY etc.

python manage.py migrate
python manage.py loaddata demo   # ~25 demo alumni so every filter returns hits
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/. In development, verification/reset emails print to
the console, and the database defaults to a local SQLite file (set `DATABASE_URL`
for Postgres).

### Google sign-in

Create OAuth credentials in the Google Cloud Console and set `GOOGLE_CLIENT_ID`
and `GOOGLE_CLIENT_SECRET` in `.env`. The provider is configured from settings —
no database `SocialApp` row is required.

## Data

The repo ships a small demo fixture (`directory/fixtures/demo.json`, ~25 alumni)
so every filter returns hits out of the box — load it with `loaddata demo`.

For the full directory (~10,300 alumni), the `import_alumni` command builds it
from two provided sources (which are large and **not committed** — see
`data/README.md`):

- `data/doece_dump.json` — the reference DOECE database dump. Rich records for
  Computer & Electronics alumni (employer, current city/country, further study).
- `data/list_for_alumni.csv` — the campus-wide roster, used for every other
  faculty (Civil, Electrical, Mechanical, Architecture, ...). DOECE rows are
  skipped here to avoid duplicating the richer JSON records.

Faculty names in the roster were recorded in 64 inconsistent variants; they are
normalised into canonical fields of study (see `directory/choices.py`).

```bash
python manage.py import_alumni            # import from data/
python manage.py import_alumni --flush    # wipe unclaimed records first
```

## Tests

```bash
python manage.py test
```

Covers the source-data normalisers, all six search filters, record visibility,
and the account claim flow (success, wrong details, and missing identity proof).
