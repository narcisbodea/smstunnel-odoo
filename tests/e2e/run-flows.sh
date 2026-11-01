#!/usr/bin/env bash
# Runs tests/e2e/flows.py (real Odoo flows) in `odoo shell` against the local SMSTunnel API, for one version.
# The database smst<version> gets the apps the flows use (installed apps are left as they are).
#
#   SMSTUNNEL_KEY_FILE=/path/to/local-test-key.json tests/e2e/run-flows.sh 17
set -euo pipefail
export MSYS_NO_PATHCONV=1
VERSION="${1:?Odoo version: 17, 18 or 19}"
HERE="$(cd "$(dirname "$0")" && (pwd -W 2>/dev/null || pwd))"   # pwd -W: a Windows path for Docker Desktop under Git Bash
COMPOSE=(docker compose -p smst-int-odoo -f "$HERE/docker-compose.yml")
DB="smst${VERSION}"
KEYFILE="${SMSTUNNEL_KEY_FILE:?SMSTUNNEL_KEY_FILE: JSON file with apiKey}"
KEY="$(node -e "process.stdout.write(require(process.argv[1]).apiKey)" "$KEYFILE")"
DEMO=(--without-demo=all)
[ "$VERSION" = "19" ] && DEMO=()   # Odoo 19 installs no demo data unless --with-demo

"${COMPOSE[@]}" run --rm -T "odoo$VERSION" odoo -d "$DB" "${DEMO[@]}" --stop-after-init --log-level=warn \
  -i sms_smstunnel,contacts,sale_management,sale_stock,stock_sms,base_automation,mass_mailing_sms

"${COMPOSE[@]}" run --rm -T \
  -e SMSTUNNEL_E2E_URL="${SMSTUNNEL_E2E_URL:-http://host.docker.internal:3101}" \
  -e SMSTUNNEL_E2E_KEY="$KEY" \
  -e SMSTUNNEL_E2E_NUMBER="${SMSTUNNEL_E2E_NUMBER:-+14155550123}" \
  -e SMSTUNNEL_E2E_OFFLINE_DEVICE="${SMSTUNNEL_E2E_OFFLINE_DEVICE:-}" \
  "odoo$VERSION" odoo shell -d "$DB" --no-http --log-level=warn < "$(dirname "$0")/flows.py"
