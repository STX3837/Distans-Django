#!/bin/sh
set -eu

INTERVAL_SECONDS="${CART_CLEANUP_INTERVAL_SECONDS:-86400}"

if [ "${INTERVAL_SECONDS}" -le 0 ] 2>/dev/null; then
  echo "[cart_cleanup] Invalid CART_CLEANUP_INTERVAL_SECONDS='${INTERVAL_SECONDS}'. Falling back to 86400."
  INTERVAL_SECONDS=86400
fi

echo "[cart_cleanup] Starting periodic guest cart cleanup every ${INTERVAL_SECONDS}s"

while true; do
  echo "[cart_cleanup] Running cleanup_guest_carts at $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  python manage.py cleanup_guest_carts || true
  sleep "${INTERVAL_SECONDS}"
done
