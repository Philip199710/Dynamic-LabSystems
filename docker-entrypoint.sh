#!/bin/sh
set -e

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

if [ "$SEED_DEMO_DATA" = "1" ]; then
  echo "Seeding demo data..."
  python manage.py seed_demo
fi

exec "$@"
