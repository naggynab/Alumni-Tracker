#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# One-time data import: only runs if the database is empty.
python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alumni_tracker.settings')
django.setup()
from directory.models import Alumnus
if Alumnus.objects.count() == 0:
    print('DATABASE EMPTY — running import_alumni...')
    import subprocess
    subprocess.run(['python', 'manage.py', 'import_alumni'], check=True)
else:
    print(f'Database already has {Alumnus.objects.count()} alumni — skipping import.')
"
