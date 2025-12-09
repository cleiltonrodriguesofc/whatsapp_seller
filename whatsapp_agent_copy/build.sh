#!/bin/bash
set -e

echo "Installing Python dependencies..."
cd whatsapp_agent_project
pip install -r requirements.txt

echo "Installing additional dependencies..."
pip install gunicorn psycopg2-binary whitenoise

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Running migrations..."
python manage.py migrate

echo "Build completed successfully!"

