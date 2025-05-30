#!/bin/bash
set -e

echo "Python environment information:"
python --version
pip list | grep alembic

echo "Running database migrations..."
if command -v alembic >/dev/null 2>&1; then
    alembic upgrade head
else
    echo "Alembic command not available, checking if it's installed as a package..."
    if pip list | grep -q alembic; then
        python -c "import alembic.config; alembic.config.main(argv=['upgrade', 'head'])" || \
        echo "Migration failed but continuing startup"
    else
        echo "Alembic package not found. Please add it to your requirements.txt"
        echo "Continuing without running migrations"
    fi
fi

echo "Starting the application..."
echo "Using port: ${PORT:-8000}"
uvicorn main:app --host 0.0.0.0 --port ${PORT:-5000}