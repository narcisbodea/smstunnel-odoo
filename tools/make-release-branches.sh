#!/usr/bin/env bash
# Creates (or moves) the local branches 17.0, 18.0 and 19.0 from the folders of the same name on the current
# branch, with their history (git subtree split). Each branch then has sms_smstunnel/ at its root, as the
# Odoo Apps store and Odoo.sh submodules expect. Nothing is pushed.
#
#   tools/make-release-branches.sh            # then: git push origin main 17.0 18.0 19.0
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -n "$(git status --porcelain)" ]; then
  echo "Commit or stash your changes first." >&2
  exit 1
fi
for v in 17.0 18.0 19.0; do
  commit="$(git subtree split --prefix="$v")"
  git branch -f "$v" "$commit"
  echo "$v -> $(git log -1 --format='%h %s' "refs/heads/$v" --)"
done
