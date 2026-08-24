#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# Never import personal student data from the application repository during a
# build. Load the private source files once, from a trusted machine, using the
# procedure documented in README.md.
