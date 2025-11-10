#!/bin/bash
set -euo pipefail
set -x

# ===== logging: mirror to file + stdout from the start =====
LOG_FILE="${ENTRYPOINT_LOG:-/app/entrypoint.log}"
mkdir -p "$(dirname "$LOG_FILE")"
# write to both the file and container stdout
exec > >(tee -a "$LOG_FILE") 2>&1

echo "Waiting for postgres..."

python << 'PY'
import os, time, sys
import psycopg

host = os.getenv('DB_HOST', 'db')
port = int(os.getenv('DB_PORT', '5432'))
user = os.getenv('DB_USER', 'postgres')
password = os.getenv('DB_PASSWORD', 'postgres')
dbname = os.getenv('DB_NAME', 'postgres')

for i in range(30):
    try:
        with psycopg.connect(host=host, port=port, user=user, password=password, dbname=dbname):
            print("PostgreSQL is ready!")
            sys.exit(0)
    except Exception as e:
        print(f"Postgres is unavailable (attempt {i+1}/30) - sleeping")
        time.sleep(1)

print("Could not connect to PostgreSQL after 30 attempts")
sys.exit(1)
PY

echo "Running migrations..."
python manage.py migrate --noinput

echo "Ensuring superuser exists..."
python << 'PY'
import os
from django.contrib.auth import get_user_model

User = get_user_model()
u = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
e = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
p = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin')

if u and not User.objects.filter(username=u).exists():
    User.objects.create_superuser(username=u, email=e, password=p)
    print(f'Superuser "{u}" created.')
else:
    print(f'Superuser "{u}" already exists or username not set.')
PY

echo "Starting server..."
exec "$@"
