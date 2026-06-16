#!/bin/sh
set -eu

echo "[entrypoint] Starting FreightDash boot sequence"
echo "[entrypoint] Python: $(python --version 2>&1)"
echo "[entrypoint] PORT=${PORT:-8000}"

echo "[entrypoint] Waiting for database connection"
for i in 1 2 3 4 5 6 7 8 9 10; do
    if python manage.py showmigrations --plan > /tmp/showmig.out 2>&1; then
        echo "[entrypoint] Database is reachable"
        break
    fi
    echo "[entrypoint] DB not ready (attempt $i/10) — $(head -1 /tmp/showmig.out)"
    if [ "$i" -eq 10 ]; then
        echo "[entrypoint] Database is not reachable after retries"
        cat /tmp/showmig.out
        exit 1
    fi
    sleep 3
done

echo "[entrypoint] Running migrations"
python manage.py migrate --noinput

echo "[entrypoint] Seeding Pacific port geofences"
python manage.py seed_pacific_ports || true

if [ "${RUN_SAMPLE_SEED:-false}" = "true" ]; then
    echo "[entrypoint] Seeding sample routes"
    python manage.py create_sample_routes || true
else
    echo "[entrypoint] Skipping sample route seeding (RUN_SAMPLE_SEED is not true)"
fi

echo "[entrypoint] Creating default admin user"
python manage.py create_admin || true

echo "[entrypoint] Collecting static files"
python manage.py collectstatic --noinput || true

echo "[entrypoint] Pre-flight import check"
python -c "from config.wsgi import application; print('[entrypoint] WSGI import OK')"

echo "[entrypoint] Launching Gunicorn on 0.0.0.0:${PORT:-8000}"
exec gunicorn \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 2 \
    --worker-class sync \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    config.wsgi:application
