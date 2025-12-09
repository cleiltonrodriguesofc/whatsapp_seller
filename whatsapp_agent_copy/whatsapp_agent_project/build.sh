#!/bin/bash
set -e

echo "Starting build process..."

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Install system dependencies for TextBlob
echo "Installing TextBlob corpora..."
python -c "import nltk; nltk.download('punkt')" || true
python -c "import nltk; nltk.download('brown')" || true

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Run migrations
echo "Running database migrations..."
python manage.py migrate

echo "Build completed successfully!"

