#!/usr/bin/env bash
# Runs the module's Odoo tests for one version (17, 18 or 19) in the local Docker stack.
# The end-to-end tests run against the local SMSTunnel API when SMSTUNNEL_KEY_FILE points to a JSON file
# with "apiKey" (the key is read here and passed as an environment variable; it is never printed).
#
#   tests/e2e/run-tests.sh 17 [extra odoo options]
set -euo pipefail
export MSYS_NO_PATHCONV=1
VERSION="${1:?Odoo version: 17, 18 or 19}"; shift || true
HERE="$(cd "$(dirname "$0")" && (pwd -W 2>/dev/null || pwd))"   # pwd -W: a Windows path for Docker Desktop under Git Bash
DB="smst${VERSION}t"
E2E_URL="${SMSTUNNEL_E2E_URL:-http://host.docker.internal:3101}"
KEY=""
if [ -n "${SMSTUNNEL_KEY_FILE:-}" ]; then
  KEY="$(node -e "process.stdout.write(require(process.argv[1]).apiKey)" "$SMSTUNNEL_KEY_FILE")"
fi
DEMO=(--without-demo=all)
[ "$VERSION" = "19" ] && DEMO=()   # Odoo 19 installs no demo data unless --with-demo
EXISTS="$(docker compose -p smst-int-odoo -f "$HERE/docker-compose.yml" exec -T db psql -U odoo -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DB'" || true)"
if [ "$EXISTS" = "1" ]; then MODE=(-u sms_smstunnel); else MODE=(-i sms_smstunnel,mass_mailing_sms "${DEMO[@]}"); fi
docker compose -p smst-int-odoo -f "$HERE/docker-compose.yml" run --rm -T \
  -e SMSTUNNEL_E2E_URL="$E2E_URL" -e SMSTUNNEL_E2E_KEY="$KEY" \
  "odoo$VERSION" odoo -d "$DB" "${MODE[@]}" --test-tags /sms_smstunnel --stop-after-init --log-level=test "$@"
