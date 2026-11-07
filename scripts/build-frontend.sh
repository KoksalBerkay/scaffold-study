#!/usr/bin/env bash
# Build the frontend into a temp folder and swap it in atomically, so a running app never sees a half-written build.
set -e
cd "$(dirname "$0")/../frontend"
rm -rf dist-next
npx vite build --outDir dist-next --emptyOutDir >/dev/null
# keep older hashed chunks so windows opened before this build can still lazy-load them
[ -d dist/assets ] && cp -n dist/assets/* dist-next/assets/ 2>/dev/null || true
rm -rf dist-old
[ -d dist ] && mv dist dist-old
mv dist-next dist
rm -rf dist-old
echo "frontend built"
