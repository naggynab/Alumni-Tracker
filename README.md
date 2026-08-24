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
- College roll number (for example `080BCT047` or `076BCE086`) + password
- Passwords require at least 8 characters, including lowercase, uppercase,
  number, and special-character requirements
- A recovery email is saved during registration and supports password reset
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
location, further-study and contact details. The supplied alumni dataset is
approved for publication and appears in the public yearbook; contact details
remain handled through the application's private contact workflows.

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

For a full project handoff covering deployment, private production data, environment
variables, authentication, migration safety, and continuation guidance, read
[`PROJECT_HANDOFF.md`](PROJECT_HANDOFF.md).

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

For Windows, `start.bat` applies pending migrations, starts the development
server in the background, and opens http://127.0.0.1:8000/. Run `stop.bat` when
you are finished. The PowerShell versions (`start.ps1` and `stop.ps1`) do the
same work from a terminal. Server output is saved under `logs/`.

### Department officer report

The Department Report is staff-only. It includes unclaimed and private records
for internal planning and never exposes email addresses or phone numbers. The
report covers headline totals, Nepal/abroad location, countries, cities,
districts, batch trends, program splits, careers, higher studies, tracker
adoption, and missing-data coverage. Department officers can download aggregate
CSV breakdowns or the full report; every report view and export is recorded in
`logs/department_audit.log`.

Access is granted explicitly by adding a user to the `Department Staff` group,
adding an exact address to `DEPARTMENT_EMAILS`, or (only when deliberately
configured) trusting every user under a domain in `DEPARTMENT_EMAIL_DOMAINS`.
The domain setting defaults to empty because enabling it grants access to every
authenticated account under each listed domain. Administrators can manage
named group access without the admin site:

```bash
.venv/Scripts/python.exe manage.py grant_department_access officer@example.com
.venv/Scripts/python.exe manage.py grant_department_access officer@example.com --revoke
.venv/Scripts/python.exe manage.py grant_department_access --list
```

The staff-only operational pages are available at `/reports/department/` and
the following additive routes: `/reports/department/data-quality/`,
`/reports/department/compare/`, `/reports/department/follow-ups/`,
`/reports/department/verification/`, and `/reports/department/roles/`.
The signed-in profile checklist is at `/me/completeness/`. These pages reuse
the app shell and do not modify the existing home page or public UI.

Student Services is available at `/student/`. It includes correction requests,
mentorship, moderated jobs and internships, event registration/submissions,
and private contact requests. Students only see published community content;
corrections, jobs, and events require staff review before publication or data
changes.

The Student Services area also includes notifications, saved directory searches,
private favorites, batch/community groups, moderated alumni stories, skills and
endorsements, surveys, a moderated resource library, profile-based alumni
recommendations, a downloadable profile PDF, account activity history, API token
management, email two-step login verification, and English/Nepali language
selection. The public home page remains unchanged.

The read-only API uses a personal bearer token created at `/student/api-tokens/`:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://127.0.0.1:8000/api/v1/me/
curl -H "Authorization: Bearer YOUR_TOKEN" "http://127.0.0.1:8000/api/v1/alumni/?batch=080"
```

Department data editors can review community stories/resources at
`/reports/department/content-moderation/` and resolve identity conflicts at
`/reports/department/conflicts/`. Preview a CSV without writing anything with
`python manage.py preview_alumni_import --csv path/to/file.csv`; scan scoped
batch/program/roll identities with `python manage.py scan_data_conflicts --dry-run`
before creating review records.

Roles can be managed from the department admin page or with:

```bash
python manage.py department_role_access officer@example.com --role report
python manage.py department_role_access officer@example.com --role editor
python manage.py department_role_access --list
```

Before a bulk import, run `python manage.py validate_alumni_import --csv
path/to/file.csv --fail-on-issues`. Scheduled-safe aggregate exports use
`python manage.py export_department_report --output exports/report.csv`, and
the included `export_department_report.ps1` can be registered with Windows
Task Scheduler for a daily or monthly run. Local SQLite backups use
`python manage.py backup_database`. To send reminders
to claimed alumni with incomplete profiles, configure email delivery and run
`python manage.py notify_incomplete_profiles --dry-run` first.

The importer and `directory.choices` keep raw employer, city, and university
text while storing indexed canonical columns for reliable filtering and
reporting. Existing databases are backfilled by migrations; rerunning
`python manage.py migrate` is sufficient after deployment.

### Password-reset email delivery

To send reset links to real inboxes, configure SMTP in the local `.env` file.

#### Resend API (recommended for Render)

Create a Resend API key and verify your sending domain, then set these Render
environment variables. When `RESEND_API_KEY` is set, the application uses the
Resend API automatically.

```env
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_your_api_key
DEFAULT_FROM_EMAIL=Alumni Tracker <noreply@your-verified-domain.example>
```

#### Gmail or Google Workspace SMTP

For a Gmail or Google Workspace sender, create a Google **App Password** (do
not use the normal account password), then set:

```env
EMAIL_PROVIDER=smtp
EMAIL_ENABLED=True
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_TIMEOUT=10
EMAIL_HOST_USER=your-sender@example.com
EMAIL_HOST_PASSWORD=your-16-character-google-app-password  # spaces are OK
DEFAULT_FROM_EMAIL=your-sender@example.com
```

Restart the server after saving the file. If the campus Google Workspace admin
does not permit App Passwords, request the campus SMTP relay details instead.

### Google sign-in

Create OAuth credentials in the Google Cloud Console and set `GOOGLE_CLIENT_ID`
and `GOOGLE_CLIENT_SECRET` in `.env`. The provider is configured from settings —
no database `SocialApp` row is required. Add these authorized redirect URIs to
the Google OAuth client:

- Local: `http://127.0.0.1:8000/accounts/google/login/callback/`
- Production: `https://alumni-tracker.itprojects.pcampus.edu.np/accounts/google/login/callback/`

If the credentials are absent, the Google button stays hidden and direct visits
to the Google login URL return a clear setup message instead of a server error.

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

### Secure Render data loading

The full source files contain personal student data and are intentionally not
part of the application repository. The Render build only runs migrations; it
never imports data from the code checkout. After the web service and Postgres
database are created, load the files once from a trusted machine using the
database's private connection method or a temporary, restricted external
connection:

```powershell
$env:DATABASE_URL = "<temporary Render database connection string>"
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py import_alumni `
  --csv "data\data-sources\list for Alumni.csv" `
  --json "data\data-sources\data.json"
Remove-Item Env:DATABASE_URL
```

Do not put the connection string, source files, exports, or database backups in
Git, tickets, screenshots, or chat. The supplied dataset is approved for
publication; review any future dataset's approval status before importing it.

## Tests

```bash
python manage.py test
```

Covers the source-data normalisers, all six search filters, record visibility,
and the account claim flow (success, wrong details, and missing identity proof).
