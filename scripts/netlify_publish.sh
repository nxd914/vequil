#!/usr/bin/env bash
set -euo pipefail

if ! command -v netlify >/dev/null 2>&1; then
  echo "Netlify CLI not found. Install with: npm i -g netlify-cli"
  exit 1
fi

netlify deploy --prod --dir web/static

