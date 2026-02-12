import os
import socket
import sys
import time

# Read environment variables set in k8s/django-app.yaml
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = int(os.environ.get("DB_PORT", 5432))

max_retries = 20
retry_delay = 3

print(f"Checking database readiness at {DB_HOST}:{DB_PORT}...")

for attempt in range(max_retries):
    try:
        # Attempt to create a socket connection
        s = socket.create_connection((DB_HOST, DB_PORT), timeout=5)
        s.close()
        print("Database connection successful!")
        sys.exit(0)  # Success
    except socket.error:
        if attempt < max_retries - 1:
            print(
                f"Waiting for DB (Attempt {attempt + 1}/{max_retries}). Retrying in {retry_delay} seconds..."
            )
            time.sleep(retry_delay)
        else:
            print(f"Failed to connect to database after {max_retries} attempts.")
            sys.exit(1)  # Failure
