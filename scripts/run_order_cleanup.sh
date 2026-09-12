#!/bin/sh
set -eu
while true; do
  python manage.py cleanup_pending_orders || true
  sleep 60
done
