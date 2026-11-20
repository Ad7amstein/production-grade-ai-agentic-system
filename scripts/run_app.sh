#!/usr/bin/env bash
# Install deps and start the app, dev or prod. Usage: ./scripts/run_app.sh --mode <dev|prod>
set -euo pipefail

# --- fixed prod certificate paths ---
SSL_CERT_FILE="/etc/ssl/certs/app.crt"
SSL_KEY_FILE="/etc/ssl/private/app.key"

usage() {
    echo "Usage: $0 --mode <dev|prod>" >&2
    exit 1
}

MODE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)
            MODE="${2:-}"
            shift 2
            ;;
        *)
            usage
            ;;
    esac
done

case "$MODE" in
    dev)
        echo "Installing dev dependencies..."
        pip install --upgrade pip
        uv pip install -e .[dev]

        echo "Starting server in development mode..."
        APP_ENV=development uv run uvicorn main:app --reload --port 8000 --loop uvloop --timeout-graceful-shutdown 30
        ;;
    prod)
        echo "Installing prod dependencies..."
        pip install --no-deps --no-build-isolation --no-cache-dir --upgrade --force-reinstall .

        echo "Starting server in production mode..."
        APP_ENV=production uvicorn main:app --host 0.0.0.0 --port 8000 --loop uvloop --timeout-graceful-shutdown 30 \
            --ssl-certfile "$SSL_CERT_FILE" --ssl-keyfile "$SSL_KEY_FILE"
        ;;
    *)
        usage
        ;;
esac
