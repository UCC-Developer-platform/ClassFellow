#!/bin/sh
set -e

# =============================================================================
# ClassFellow Web - Production Container Entrypoint Script (Category 17)
# =============================================================================

echo "[Entrypoint] Starting ClassFellow container initialization..."

# Wait for PostgreSQL if configured
if [ "$DJANGO_DB_ENGINE" != "sqlite" ] && [ -n "$POSTGRES_HOST" ]; then
  echo "[Entrypoint] Waiting for PostgreSQL database at $POSTGRES_HOST:${POSTGRES_PORT:-5432}..."
  while ! nc -z "$POSTGRES_HOST" "${POSTGRES_PORT:-5432}" 2>/dev/null; do
    sleep 0.5
  done
  echo "[Entrypoint] PostgreSQL database is reachable and accepting connections."
fi

# Run database schema migrations
echo "[Entrypoint] Applying database schema migrations..."
python classfellow_web/manage.py migrate --noinput

# Collect static assets for WhiteNoise / Nginx
echo "[Entrypoint] Collecting static assets..."
python classfellow_web/manage.py collectstatic --noinput --clear || true

echo "[Entrypoint] Initialization complete. Executing command: $@"
exec "$@"
