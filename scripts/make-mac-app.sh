#!/usr/bin/env bash
# Creates Scaffold.app (double-click / Dock) that launches the desktop app from this repo.
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
APP="$REPO/Scaffold.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$REPO/assets/Scaffold.icns" "$APP/Contents/Resources/Scaffold.icns"
cat > "$APP/Contents/MacOS/Scaffold" <<SH
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:\$HOME/.local/bin:\$HOME/.cargo/bin:\$PATH"
[ -s "\$HOME/.nvm/nvm.sh" ] && . "\$HOME/.nvm/nvm.sh"
cd "$REPO" && exec /bin/bash "$REPO/run.sh" --app --no-build >> "$REPO/workspace/app.log" 2>&1
SH
chmod +x "$APP/Contents/MacOS/Scaffold"
cat > "$APP/Contents/Info.plist" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Scaffold</string>
  <key>CFBundleDisplayName</key><string>Scaffold</string>
  <key>CFBundleIdentifier</key><string>local.scaffold.app</string>
  <key>CFBundleExecutable</key><string>Scaffold</string>
  <key>CFBundleIconFile</key><string>Scaffold</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
PL
mkdir -p "$REPO/workspace"
echo "Created $APP. Build the frontend once with ./run.sh, then double-click Scaffold.app."
