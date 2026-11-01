#!/usr/bin/env bash
# Fills <version>/sms_smstunnel/static/description for the Odoo Apps page: icon, cover, that version's
# screenshots and index.html (from tools/description-template.html).
#   tools/build-descriptions.sh /path/to/screenshots   (files: icon.png, banner.png, odoo<NN>-<name>.png)
set -euo pipefail
SHOTS="${1:?folder with the screenshots}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
for v in 17 18 19; do
  dst="$ROOT/$v.0/sms_smstunnel/static/description"
  mkdir -p "$dst"
  cp "$SHOTS/icon.png" "$SHOTS/banner.png" "$dst/"
  cp "$SHOTS/odoo$v-configure.png" "$dst/configure_screenshot.png"   # "_screenshot": the big image on the page
  cp "$SHOTS/odoo$v-settings.png" "$dst/settings.png"
  cp "$SHOTS/odoo$v-test-text.png" "$dst/test_text.png"
  cp "$SHOTS/odoo$v-contact.png" "$dst/contact.png"
  cp "$SHOTS/odoo$v-failure.png" "$dst/failure.png"
  sed "s/{{VERSION}}/$v.0/g" "$ROOT/tools/description-template.html" > "$dst/index.html"
  cp "$ROOT/LICENSE" "$ROOT/$v.0/sms_smstunnel/LICENSE"
done
