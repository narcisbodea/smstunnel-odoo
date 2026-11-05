#!/usr/bin/env bash
# Fills <version>/sms_smstunnel/static/description for the Odoo Apps page: index.html from
# tools/description-template.html and the LICENSE; with a folder, also the icon, the cover and that version's
# screenshots.
#   tools/build-descriptions.sh                         # index.html and LICENSE only
#   tools/build-descriptions.sh /path/to/screenshots    # files: icon.png, banner.png, odoo<NN>-<name>.png
set -euo pipefail
SHOTS="${1:-}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
for v in 17 18 19; do
  dst="$ROOT/$v.0/sms_smstunnel/static/description"
  mkdir -p "$dst"
  if [ -n "$SHOTS" ]; then
    cp "$SHOTS/icon.png" "$SHOTS/banner.png" "$dst/"
    cp "$SHOTS/odoo$v-configure.png" "$dst/configure_screenshot.png"
    cp "$SHOTS/odoo$v-settings.png" "$dst/settings.png"
    cp "$SHOTS/odoo$v-test-text.png" "$dst/test_text.png"
    cp "$SHOTS/odoo$v-contact.png" "$dst/contact.png"
    cp "$SHOTS/odoo$v-failure.png" "$dst/failure.png"
  fi
  # Odoo's label for the trigger that runs at every save: "On save" in 17.0 and 18.0, "On create and edit" in 19.0.
  if [ "$v" = 19 ]; then save="On create and edit"; else save="On save"; fi
  sed -e "s/{{VERSION}}/$v.0/g" -e "s/{{SAVE_TRIGGER}}/$save/g" "$ROOT/tools/description-template.html" > "$dst/index.html"
  cp "$ROOT/LICENSE" "$ROOT/$v.0/sms_smstunnel/LICENSE"
done
