#!/usr/bin/env bash
set -euo pipefail

DB_NAME="trading_platform_dev"
DB_USER="${PGUSER:-postgres}"
DB_HOST="${PGHOST:-localhost}"
DB_PORT="${PGPORT:-5432}"

echo "Checking for PostgreSQL..."

# Check if PostgreSQL is accessible
if pg_isready -h "$DB_HOST" -p "$DB_PORT" > /dev/null 2>&1; then
    echo "PostgreSQL is running at $DB_HOST:$DB_PORT"
else
    echo "PostgreSQL is not running. Attempting to start via Docker Compose..."
    docker compose up -d postgres
    echo "Waiting for PostgreSQL to be ready..."
    for i in $(seq 1 30); do
        if pg_isready -h "$DB_HOST" -p "$DB_PORT" > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" > /dev/null 2>&1; then
        echo "ERROR: PostgreSQL failed to start within 30 seconds."
        exit 1
    fi
    echo "PostgreSQL is ready."
fi

# Create database if it doesn't exist
if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    echo "Database '$DB_NAME' already exists."
else
    echo "Creating database '$DB_NAME'..."
    createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"
    echo "Database '$DB_NAME' created."
fi

CONNECTION_STRING="postgresql://$DB_USER@$DB_HOST:$DB_PORT/$DB_NAME"
echo ""
echo "Connection string: $CONNECTION_STRING"
echo "Set it in your .env: DATABASE_URL=$CONNECTION_STRING"
