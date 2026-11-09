#!/usr/bin/env bash
# Creates Scaffold.app, a real macOS app (Spotlight, Launchpad, Dock) that launches the desktop app from this repo.
#   scripts/make-mac-app.sh                 → ~/Applications/Scaffold.app (Spotlight finds it)
#   scripts/make-mac-app.sh /Applications   → install somewhere else
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-$HOME/Applications}"
mkdir -p "$DEST"
APP="$DEST/Scaffold.app"
rm -rf "$APP"
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
  <key>NSDocumentsFolderUsageDescription</key><string>Scaffold runs from its folder in Documents and reads your notes.</string>
  <key>NSDesktopFolderUsageDescription</key><string>Scaffold reads the course materials you keep on the Desktop.</string>
  <key>NSDownloadsFolderUsageDescription</key><string>Scaffold reads course materials you downloaded.</string>
</dict></plist>
PL
mkdir -p "$REPO/workspace"
touch "$APP"  # let Spotlight and Launchpad notice it
echo "Created $APP. Open it from Spotlight (⌘Space, type Scaffold). The first launch builds nothing: run ./run.sh once first if you never did."
