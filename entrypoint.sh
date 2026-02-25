#!/bin/sh
set -e

if [ -n "${DB_HOST:-}" ]; then
  echo "Waiting for database at ${DB_HOST}:${DB_PORT:-5432}..."
  python - <<'PY'
import os
import time

import psycopg

host = os.getenv("DB_HOST")
port = os.getenv("DB_PORT", "5432")
dbname = os.getenv("DB_NAME", "app")
user = os.getenv("DB_USER", "app")
password = os.getenv("DB_PASS", "app")

for attempt in range(1, 61):
    try:
        conn = psycopg.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=3,
        )
        conn.close()
        print("Database is ready.")
        break
    except Exception:
        if attempt == 60:
            raise
        print(f"Database not ready yet (attempt {attempt}/60). Retrying...")
        time.sleep(2)
PY
fi

python manage.py migrate --noinput

if [ "${RUN_COLLECTSTATIC:-0}" = "1" ]; then
  python manage.py collectstatic --noinput
fi

exec "$@"
