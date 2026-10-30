#!/usr/bin/env bash
# Each Vercel service builds in its own checkout. Generate from committed inputs,
# never from a developer's ignored runtime/public directories.
set -euo pipefail
service="${1:?Choose frontend or backend}"
case "$service" in frontend|backend) ;; *) exit 2 ;; esac
cd "$(dirname "$0")/../.."
npm ci --prefix scripts/migration --no-audit --no-fund
python3 -m pip install --disable-pip-version-check --target .migration-cache/python -r apps/backend/requirements.txt
export PYTHONPATH="$PWD/.migration-cache/python${PYTHONPATH:+:$PYTHONPATH}"
python3 scripts/migration/prepare_release.py
node scripts/migration/check_release.mjs "$service"
if [ "$service" = frontend ]; then
  npm run build --prefix apps/web
fi
