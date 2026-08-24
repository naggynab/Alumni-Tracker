# Alumni Tracker Deployment and Data Import Report

## 1. Project scope

This project was deployed from:

- GitHub repository: `https://github.com/naggynab/Alumni-Tracker.git`
- Live domain: `https://alumni-tracker.itprojects.pcampus.edu.np/`
- Hosting platform: Coolify
- Deployment team: Root Team
- Coolify project: `Alumni Tracker - New Deployment`
- Environment: `production`
- Application: `alumni-tracker`

The objective was to deploy the inherited Django project and privately import the real alumni data supplied locally, without committing the data to GitHub.

Secrets, passwords, import tokens, and personally identifiable information are intentionally not included in this report.

## 2. Repository inspection

The repository was cloned locally into:

`G:\downloads\Deploy this too\Alumni-Tracker`

The project was inspected to identify:

1. The Django entry point and settings.
2. Existing models and database migrations.
3. Existing import functionality.
4. Existing Docker or deployment configuration.
5. Existing fixtures and public/private data behavior.

The project already contained a Django management command at:

`directory/management/commands/import_alumni.py`

This command was used for the real import. The demo fixture was not used because the requirement was to use the real dataset.

## 3. Local data inspection

The supplied data was located under:

`G:\downloads\Deploy this too\data-20260824T181401Z-1-001\data`

The relevant files were:

- `data-sources/list for Alumni.csv`
- `data-sources/data.json`
- `data-sources/db-backup.dmp`
- `README.md`

There was also a duplicate CSV at the data root. The two CSV copies were checked and found to be identical.

The following non-sensitive validation checks were performed:

- CSV rows: 9,704.
- JSON objects: 12,470.
- JSON student records: 2,577.
- JSON address records: 1,654.
- JSON further-academic-status records: 287.
- The CSV key fields did not contain duplicate `(facultyName, classRollNo)` groups.
- The `.dmp` file was identified as a PostgreSQL custom-format dump.

The dump was not restored wholesale. The project’s purpose-built importer was used instead so that the data would match the application’s models and privacy rules.

## 4. Docker deployment configuration

The repository did not initially contain the required Docker deployment configuration, so a Dockerfile was added.

The Dockerfile performs the following operations:

1. Uses Python 3.12 Slim as the base image.
2. Installs the PostgreSQL client library required by the Django database driver.
3. Installs the packages from `requirements.txt`.
4. Copies the application into `/app`.
5. Collects Django static files.
6. Exposes port `8000`.
7. Runs migrations and starts Gunicorn.

The application is served with:

`gunicorn alumni_tracker.wsgi:application --bind 0.0.0.0:8000`

The Coolify application was configured with:

- Build pack: Dockerfile.
- Dockerfile location: `/Dockerfile`.
- Exposed application port: `8000`.
- Domain: `https://alumni-tracker.itprojects.pcampus.edu.np`.
- Production environment variables for allowed hosts, CSRF origins, Django secret configuration, security settings, and database connectivity.

## 5. Initial PostgreSQL setup

A PostgreSQL 17 database resource named `alumni-tracker-db` was initially created in Coolify.

Temporary public database access was enabled because direct external connectivity was requested for the import process. A connectivity test showed that the college VM/firewall did not allow direct external database access, so the import was performed through the application’s internal network instead.

During deployment testing, two issues were found with the initial database resource:

1. The database resource name did not resolve as an internal Docker hostname from the application container.
2. The password stored in the application configuration did not match the password already used by the existing PostgreSQL volume.

The existing database volume was left untouched. Because no real data had been imported into it, a new PostgreSQL 17 resource was created instead:

- Resource name: `alumni-tracker-db-real`
- Coolify resource id: `ykw04kgsssgw48g4cgc404w0`
- Database engine: PostgreSQL 17
- Persistent storage: enabled
- Public database access: disabled

A new strong password was generated and stored only in Coolify. The application’s production and preview `DATABASE_URL` values were then updated to use the new database resource’s internal hostname.

After redeployment, the application successfully connected to PostgreSQL and ran its migrations.

## 6. Temporary private import mechanism

The existing importer is a Django management command that runs inside the application container. Because the local data files were not available inside the deployed container, a temporary protected upload mechanism was added for the import only.

The temporary mechanism provided:

- A protected upload endpoint for the CSV and JSON files.
- A readiness endpoint used to confirm that the deployed code was active.
- A protected status endpoint used to monitor the background import.
- Token authentication through a temporary Coolify environment variable.
- Multipart upload support for the two source files.
- Background execution of the existing `import_alumni` management command.

The import was run without the destructive `--flush` option. This avoided deleting any existing records.

At import time, the importer applied the project’s then-configured privacy
behavior:

- Detailed JSON records were imported.
- Roster CSV records were imported.
- Duplicate records already represented by the JSON data were skipped where appropriate.
- Imported alumni records were initially marked `is_public=False`.

## 7. Real data import

The real CSV and JSON files were uploaded directly from the local data folder to the protected endpoint over HTTPS.

The upload was accepted with HTTP status `202`, meaning the background import was started successfully.

The completed importer reported:

- Detailed DOECE records imported: 2,577.
- Roster records imported: 9,120.
- Total alumni records in the directory: 11,697.
- Import exit code: `0`.

The source files were not copied into the repository, uploaded to GitHub, or added to any public storage location.

## 8. Cleanup after import

After the import completed, all temporary import functionality was removed from the codebase.

Removed items:

- Temporary import view module: `directory/import_views.py`.
- Temporary upload route.
- Temporary readiness route.
- Temporary import status route.
- Temporary import form route.

The cleanup was committed and pushed to GitHub as:

- Commit: `5e318b9`
- Message: `Remove temporary private import endpoint`

The application was redeployed from that cleanup commit.

The temporary `ALUMNI_IMPORT_TOKEN` environment variable was deleted from both:

- Production environment variables.
- Preview deployment environment variables.

The application was redeployed again so the old container could not retain the temporary token.

The old unused database resource was also made private and stopped. It was not deleted because deletion is irreversible and was unnecessary for completing the deployment.

## 9. Verification performed

The following checks were completed after cleanup:

1. The live website returned HTTP `200`.
2. The temporary import endpoint returned HTTP `404`, confirming that it was no longer deployed.
3. The new PostgreSQL database resource was running.
4. The application was connected to the new PostgreSQL resource.
5. The import status reported exit code `0`.
6. No real CSV, JSON, or PostgreSQL dump files were tracked by Git.
7. The local Git working tree was clean after the cleanup commit.

The authenticated alumni API was not used as a public data check because it requires a valid bearer token. This is expected application behavior.

## 10. Publication approval

The dataset owner later approved all imported records for publication. A
follow-up application migration changed every existing alumni record to
`is_public=True`, and the importer was updated to mark future imports public by
default.

The public directory therefore uses the complete approved dataset. Contact
details are still handled through the application's private contact workflows.

The raw CSV and JSON source files remain outside GitHub and public file storage.

## 11. Current deployment state

The project is currently deployed as follows:

- Website: `https://alumni-tracker.itprojects.pcampus.edu.np/`
- Application source: GitHub `main` branch.
- Latest publication commit: recorded in Git after deployment.
- Application container: running through Coolify.
- Production database: `alumni-tracker-db-real`.
- Database access: internal/private only.
- Real alumni records: imported and approved for publication.
- Temporary import endpoint: removed.
- Temporary import credentials: removed.
- Raw data files in GitHub: none.

## 12. Recommended next steps

Before the demonstration:

1. Test the login and administrator workflow.
2. Confirm that the public directory does not expose private contact or address fields.
3. Create a PostgreSQL backup before making further data changes.

After the demonstration:

1. Review whether the old unused database resource should be deleted.
2. Rotate any deployment credentials that were shared during setup.
3. Keep the real dataset out of public repositories and public file storage.
4. Set up scheduled database backups if the project will remain online.
