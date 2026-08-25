# Alumni Tracker — Project Handoff

This document is the operational handoff for future developers and AI assistants.
It explains the project, the data model, what has already been done, how to run it,
how production is deployed, and which decisions must not be changed casually.

## 1. Project identity

- Repository: <https://github.com/naggynab/Alumni-Tracker>
- Main branch: `main`
- Live website: <https://alumni-tracker.itprojects.pcampus.edu.np/>
- Deployment platform: Coolify on the college VM
- Current production database resource: `alumni-tracker-db-real`
- Current deployment commit at the time of this handoff: `3687960`
- Main Django model for alumni records: `directory.models.Alumnus`
- Default database table: `directory_alumnus`

The Coolify project is named **Alumni Tracker - New Deployment**, the environment
is **production**, and the application is named **alumni-tracker**. The Coolify
dashboard and application identifiers are deployment metadata, not application
secrets. Access credentials are intentionally not written in this repository.

## 2. What the application does

The application is a Django 4.2 alumni directory for IOE Pulchowk. It provides:

- Public alumni search at `/alumni/`.
- Search by name, batch, field of study, current city, employer, and country.
- Alumni registration using a pre-loaded identity record when one exists.
- College roll-number/password login.
- Department-only staff email/password login at `/accounts/department/login/`.
- Recovery email and password-reset flow.
- Optional Google sign-in.
- Alumni profile editing and public-profile visibility.
- Student Services at `/student/`.
- Staff-only department reports and data-quality workflows.
- Department data-editor replies for department-owned Student Services requests.
- A read-only authenticated API under `/api/v1/`.

Important source locations:

| Area | Location |
|---|---|
| Django settings | `alumni_tracker/settings.py` |
| Root URLs | `alumni_tracker/urls.py` |
| Alumni model | `directory/models.py` |
| Public directory views | `directory/views.py` |
| Directory filters | `directory/filters.py` |
| Import command | `directory/management/commands/import_alumni.py` |
| Account forms | `accounts/forms.py` |
| Account views | `accounts/views.py` |
| Templates | `templates/` |
| Demo fixture | `directory/fixtures/demo.json` |
| Deployment report | `DEPLOYMENT_AND_DATA_IMPORT.md` |

## 3. Data origins and storage

There are two broad origins of records:

1. The repository contains a small demo fixture of approximately 25 synthetic/demo
   alumni records in `directory/fixtures/demo.json`. This fixture was not loaded
   into production.
2. The production database contains the real imported dataset. The source files
   were supplied privately and were never committed to GitHub.

The real import used two source files:

- Detailed JSON records: 2,577 records.
- Campus-wide CSV roster: 9,120 records after duplicate handling.
- Total imported alumni records: 11,697.

The real source files were located locally at:

```text
G:\downloads\Deploy this too\data-20260824T181401Z-1-001\data\data-sources\
```

The live records are stored in the private PostgreSQL database attached to Coolify,
not in GitHub, the Docker image, or the public website files. The application reads
them through the `DATABASE_URL` environment variable.

The `Alumnus` model currently does not have a `source` column. After importing,
JSON and CSV records are normal alumni records in the same table and cannot be
separated with a source filter. Do not infer data origin from `date_added`; it is
not a reliable source marker.

The real dataset was approved for publication. Public directory visibility is
controlled by `Alumnus.is_public`; the publication migration set existing approved
records to public, and the importer/registration flow now marks approved records
public by default. Contact details remain handled through private workflows.

## 4. Production deployment

The production application is deployed from the GitHub `main` branch through
Coolify using the repository's `Dockerfile`.

The Docker image:

1. Uses Python 3.12.
2. Installs `requirements.txt`.
3. Copies the application code.
4. Runs `collectstatic`.
5. Exposes port `8000`.
6. Runs migrations and Gunicorn at container startup.

The deployment command is defined in `Dockerfile`:

```text
python manage.py migrate && gunicorn alumni_tracker.wsgi:application --bind 0.0.0.0:8000
```

`build.sh` also runs migrations for platforms that use it. The build deliberately
does not import the private alumni source files. Data imports must be performed
explicitly from a trusted environment.

### Redeploy procedure

1. Make and test changes locally.
2. Review `git diff` and `git status`.
3. Commit to `main`.
4. Push to GitHub.
5. Open the Coolify application.
6. Confirm the branch is `main` and click **Redeploy**.
7. Wait for the Docker build, rolling update, and health check to finish.
8. Confirm the deployment log shows the new commit SHA.
9. Check the live website and the affected workflow.

Do not change another team's Coolify project. Do not delete the production
database or persistent volume during routine redeployments.

## 5. Environment variables

The repository contains `.env.example` with safe placeholders. Copy it to `.env`
for local development. Never commit `.env`.

### Required or strongly recommended in production

```env
SECRET_KEY=<long random Django secret; store only in Coolify secrets>
DEBUG=False
ALLOWED_HOSTS=alumni-tracker.itprojects.pcampus.edu.np
CSRF_TRUSTED_ORIGINS=https://alumni-tracker.itprojects.pcampus.edu.np
DATABASE_URL=<private PostgreSQL connection string; store only in Coolify secrets>
```

Generate a new Django key locally with:

```powershell
.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Do not copy the generated key into this document or GitHub. The live value is
managed in Coolify. Rotating `SECRET_KEY` invalidates existing Django sessions.

### Email delivery

Local development can use console email output. Production password resets require
one of these configurations:

```env
# Resend
EMAIL_PROVIDER=resend
RESEND_API_KEY=<secret>
DEFAULT_FROM_EMAIL=Alumni Tracker <noreply@verified-domain.example>
```

or:

```env
# SMTP / Google Workspace
EMAIL_PROVIDER=smtp
EMAIL_ENABLED=True
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_TIMEOUT=10
EMAIL_HOST_USER=<sender address>
EMAIL_HOST_PASSWORD=<Google App Password, not the normal account password>
DEFAULT_FROM_EMAIL=<sender address>
```

### Google sign-in

Google sign-in is optional. The button stays hidden and the login route fails
gracefully when these values are absent:

```env
GOOGLE_CLIENT_ID=<OAuth client ID>
GOOGLE_CLIENT_SECRET=<OAuth client secret>
```

The production OAuth callback must be exactly:

```text
https://alumni-tracker.itprojects.pcampus.edu.np/accounts/google/login/callback/
```

For local development, also authorize:

```text
http://127.0.0.1:8000/accounts/google/login/callback/
```

Do not put Google secrets in GitHub. Configure them in Coolify and Google Cloud
Console only.

### Department access

These values are optional and grant access to staff-only reports or workflows:

```env
DEPARTMENT_EMAILS=staff1@example.com,staff2@example.com
DEPARTMENT_EMAIL_DOMAINS=
DEPARTMENT_GROUP_NAME=Department Staff
DEPARTMENT_DATA_EDITOR_GROUP=Alumni Data Editors
DEPARTMENT_ADMIN_GROUP=Alumni Administrators
```

An email domain grants access to every matching authenticated account, so leave
`DEPARTMENT_EMAIL_DOMAINS` empty unless this is deliberately approved.

Department-only accounts should be created with
`manage.py create_department_staff staff@example.com`; assign `Alumni Data Editors` only to
staff who should review and reply to Student Services submissions. Alumni who
also work for the department should keep their linked alumni record and use
roll-number login so both Student Services and the Department Report remain
available. The department request queue is intentionally limited to corrections,
jobs, events, stories, and resources; private peer-to-peer mentorship and
contact requests are not exposed to department staff.

## 6. Local development on Windows

From the repository directory:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` for local use. A local SQLite database is used when `DATABASE_URL` is
unset. Then run:

```powershell
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py runserver
```

Open <http://127.0.0.1:8000/>.

For a clean demo environment, load the fixture into a fresh local database:

```powershell
.venv\Scripts\python.exe manage.py loaddata demo
```

Do not use the demo fixture command against a local database that contains records
you want to preserve without first making a backup.

Convenience scripts are available as `start.bat`, `start.ps1`, `stop.bat`, and
`stop.ps1`. Local logs are written under `logs/`.

## 7. Tests and verification

Run these before pushing changes:

```powershell
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py test
git diff --check
```

The latest completed local suite ran 71 tests successfully.

Important workflows already covered by tests include:

- Roll-number login and wrong-password rejection.
- Registration password policy.
- Recovery email and password reset.
- Pre-loaded identity matching.
- Public visibility after registration and claiming.
- Google configuration fallback behavior.
- Directory filters and public/private visibility.
- Date-of-birth matching in registration and claim flows.

## 8. Important behavior and recent fixes

### Public directory

The public directory uses `Alumnus.objects.filter(is_public=True)`. Staff reports
can access broader internal data, so staff routes must not be made public casually.

### Registration identity matching

Registration matches a pre-loaded record using roll number, last name, batch,
program/field, and date of birth. It does not trust a roll number alone.

The date field is B.S. The matching logic normalizes equivalent spellings such as:

```text
12/01/2061
12/1/2061
2061/12/01
```

The current approved record for `080BCT011` stores the equivalent B.S. date
`12/1/2061`. An A.D. date such as `03/14/2004` will not match that B.S. record.

### Authentication

- Login uses the college roll number plus password.
- Recovery email is stored on the account and supports reset links.
- Google authentication is optional and requires OAuth environment variables.
- The Google login route is explicitly configured so missing OAuth credentials do
  not produce a server error.

### Data import safety

`directory/management/commands/import_alumni.py` is the supported importer. It
accepts the delivered nested source names as well as documented `data/` paths.

Preview/validation commands:

```powershell
.venv\Scripts\python.exe manage.py preview_alumni_import --csv path\to\file.csv
.venv\Scripts\python.exe manage.py validate_alumni_import --csv path\to\file.csv --fail-on-issues
.venv\Scripts\python.exe manage.py scan_data_conflicts --dry-run
```

Import only after validation and backup:

```powershell
.venv\Scripts\python.exe manage.py import_alumni `
  --csv "path\to\list for Alumni.csv" `
  --json "path\to\data.json"
```

`--flush` deletes existing unclaimed alumni records before importing. Never use it
on production without a verified database backup and explicit approval.

The temporary private upload/import endpoint used for the original migration was
removed after the import. Do not recreate an upload endpoint without a new security
review.

## 9. Backups and data migration

The production database is separate from the application code and should survive
normal code redeployments. A database backup is still required before migrations,
bulk imports, or a hosting move.

Recommended migration sequence:

1. Create a PostgreSQL backup from the current Coolify database.
2. Store an encrypted copy in approved private cloud storage and keep a second
   encrypted copy offline.
3. Create the target PostgreSQL database.
4. Restore the backup into the target database.
5. Configure the target application's `DATABASE_URL` as a server-side secret.
6. Run `python manage.py migrate`.
7. Test login, directory search, registration, reports, and data counts.
8. Keep the old database until the new deployment is verified.

Never store the raw CSV, JSON, SQL dump, PostgreSQL URL, or user passwords in a
public repository. A sanitized demo fixture is the correct dataset for junior
developers.

## 10. Vercel migration warning

This project is currently built and deployed as a Docker/Gunicorn Django service
on Coolify. Moving only the code to Vercel does not move the database.

If Vercel is considered later:

- Use a managed PostgreSQL database reachable by the Vercel runtime.
- Do not expose the current private college database casually to the public
  internet.
- Set `DATABASE_URL`, `SECRET_KEY`, `DEBUG=False`, host, CSRF, email, and optional
  Google variables in the Vercel Production environment.
- Restore a backup into the target database before switching the domain.
- Confirm connection pooling and migration behavior in a preview environment.

Keeping the application and database on Coolify is currently the lowest-risk option.

## 11. What has already been completed

- Inherited repository cloned and made deployable with Docker.
- Real alumni data imported privately into the production PostgreSQL database.
- 11,697 imported records approved for public directory publication.
- Temporary import mechanism removed after completion.
- Filter placeholder issue fixed.
- Login, registration, recovery email, and Google fallback flows fixed.
- Favicon and public-directory usability improvements added.
- B.S. date matching fixed for leading zeros and year-first equivalents.
- Local tests and live smoke checks completed.
- Current latest date-fix commit: `3687960 Fix B.S. date matching`.

Useful earlier commits:

```text
e1733ec Publish approved alumni dataset
5e318b9 Remove temporary private import endpoint
da1706f Fix authentication flows
e560f0b Fix public directory filter placeholders
```

## 12. Rules for future developers and AI assistants

Before changing anything:

1. Read this file, `README.md`, and `DEPLOYMENT_AND_DATA_IMPORT.md`.
2. Check `git status` and preserve unrelated work.
3. Inspect the relevant model, view, form, template, and tests.
4. Reproduce the issue locally before changing production.

While working:

- Never print or commit secrets.
- Never commit raw alumni source data or database backups.
- Never use `--flush` in production without approval and a backup.
- Preserve the public/private access rules.
- Do not make staff reports or contact workflows public.
- Add or update tests for behavior changes.
- Run `manage.py check` and the full test suite before pushing.

After changing code:

1. Commit with a descriptive message.
2. Push to `main`.
3. Redeploy through the existing Coolify application.
4. Verify the deployed commit and live behavior.
5. Report exactly what changed, what was tested, and any remaining limitation.

## 13. Secrets inventory — names only

The following values may exist in the production environment but are intentionally
not included here:

```text
SECRET_KEY
DATABASE_URL
RESEND_API_KEY
EMAIL_HOST_PASSWORD
GOOGLE_CLIENT_SECRET
Any Coolify, GitHub, database, or OAuth credentials
```

Obtain these through the authorized project owner or Coolify team access. If a
secret is exposed, rotate it immediately and update the deployment environment.
