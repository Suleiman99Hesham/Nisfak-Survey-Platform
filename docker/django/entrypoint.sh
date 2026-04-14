#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
while ! python -c "import socket; s = socket.create_connection(('db', 5432), timeout=1); s.close()" 2>/dev/null; do
    sleep 1
done
echo "PostgreSQL is ready."

# Only the web container runs migrations and collectstatic
if [ "$1" = "python" ] && [ "$2" = "manage.py" ] && [ "$3" = "runserver" ]; then
    echo "Applying migrations..."
    python manage.py migrate --noinput

    echo "Collecting static files..."
    python manage.py collectstatic --noinput 2>/dev/null || true
fi

exec "$@"
