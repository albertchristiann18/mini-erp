#!/usr/bin/env bash
set -euo pipefail

echo "Applying migrations..."
uv run python manage.py migrate --noinput

# Optional: collectstatic if you want (safe for dev)
# echo "Collecting static files..."
# python manage.py collectstatic --noinput --clear

echo "Creating superuser if missing..."
uv run python manage.py shell -c "
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
