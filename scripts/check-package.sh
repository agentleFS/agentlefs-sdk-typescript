#!/usr/bin/env bash
# One packaging gate for regeneration and publication. Nothing here publishes.
set -euo pipefail
cd sdks/typescript
npm install --no-package-lock --no-audit --no-fund
npm run build
test -f dist/esm/index.js
test -f dist/cjs/index.js
test -f dist/esm/index.d.ts
tarball="$(npm pack --silent)"
tarball_path="$PWD/$tarball"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cd "$work"
npm init -y >/dev/null
npm install "$tarball_path" --no-audit --no-fund >/dev/null
node -e "const m = require('@agentlefs/sdk'); if (typeof m.AgentlefsApiClient !== 'function') throw new Error('CJS: client export missing'); console.log('CJS require() ok');"
node --input-type=module -e "import { AgentlefsApiClient } from '@agentlefs/sdk'; if (typeof AgentlefsApiClient !== 'function') throw new Error('ESM: client export missing'); console.log('ESM import ok');"
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "tarball=$tarball_path" >> "$GITHUB_OUTPUT"
fi
