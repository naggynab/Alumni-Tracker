# Data sources

The full alumni data sources are large and are **not committed** to the repo.
To load the complete directory (~10,300 alumni), place these files here and run
the import command:

| File | What it is |
| --- | --- |
| `list_for_alumni.csv` | Campus-wide student roster (all faculties). |
| `doece_dump.json` | Django dump from the reference DOECE app (rich Computer/Electronics records with employer, current location and further study). |

```bash
python manage.py import_alumni          # reads the two files above
python manage.py import_alumni --flush  # replace existing unclaimed records
```

## Just want to try it out?

A small demo dataset ships with the repo — no downloads needed:

```bash
python manage.py loaddata demo
```

This loads ~25 alumni spanning every field of study, several cities, countries
and employers, so all six search filters return results immediately.
