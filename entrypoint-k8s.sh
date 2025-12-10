#!/usr/bin/env bash
set -euo pipefail

# --- K8s Readiness Check (Essential for Minikube) ---
# Call the script to wait for the database service to be ready.
# We use 'python' because it's available via the VENV path in the container.
echo "Running database readiness check..."
python /app/wait_for_db.py || { echo "DB check failed."; exit 1; }

# --- Django Setup (REPLACED 'uv run' with 'python' or 'gunicorn') ---

echo "Applying migrations..."
# Original: uv run python manage.py migrate --noinput
python manage.py migrate --noinput

echo "Collecting static files..."
# Original: uv run python manage.py collectstatic --noinput
python manage.py collectstatic --noinput

echo "Creating superuser if missing..."
# Original: uv run python manage.py shell -c "..."
python manage.py shell -c "
import os
from django.contrib.auth import get_user_model

u = os.getenv('DJANGO_SUPERUSER_USERNAME')
e = os.getenv('DJANGO_SUPERUSER_EMAIL')
p = os.getenv('DJANGO_SUPERUSER_PASSWORD')

if u and e and p:
    User = get_user_model()
    if not User.objects.filter(username=u).exists():
        User.objects.create_superuser(username=u, email=e, password=p)
        print(f'Superuser {u!r} created.')
    else:
        print(f'Superuser {u!r} already exists.')
else:
    print('DJANGO_SUPERUSER_* not fully set; skipping superuser creation.')
"

# --- K8s / Production Server Start (Gunicorn) ---
echo "Starting Gunicorn server..."
exec gunicorn core.wsgi:application --bind 0.0.0.0:8000