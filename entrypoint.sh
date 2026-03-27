#!/bin/sh
set -eu

echo "[entrypoint] Starting FreightDash boot sequence"

echo "[entrypoint] Waiting for database connection"
for i in 1 2 3 4 5 6 7 8 9 10; do
    if python manage.py showmigrations --plan >/dev/null 2>&1; then
        echo "[entrypoint] Database is reachable"
        break
    fi
    if [ "$i" -eq 10 ]; then
        echo "[entrypoint] Database is not reachable after retries"
        exit 1
    fi
    sleep 3
done

echo "[entrypoint] Running migrations"
python manage.py migrate --noinput

echo "[entrypoint] Seeding sample routes"
python manage.py create_sample_routes || true

echo "[entrypoint] Collecting static files"
python manage.py collectstatic --noinput --clear

echo "[entrypoint] Launching Gunicorn"
exec gunicorn \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 2 \
    --worker-class sync \
    --worker-tmp-dir /dev/shm \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    config.wsgi:application
