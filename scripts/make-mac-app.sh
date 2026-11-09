#!/usr/bin/env bash
# Creates Scaffold.app, a real macOS app (Spotlight, Launchpad, Dock) that launches the desktop app from this repo.
#   scripts/make-mac-app.sh                 → ~/Applications/Scaffold.app (Spotlight finds it)
#   scripts/make-mac-app.sh /Applications   → install somewhere else
#
# The app's executable is a tiny compiled, signed launcher (not a shell script): macOS ties privacy permissions
# such as Full Disk Access to a signed program, and everything the launcher starts inherits them.
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-$HOME/Applications}"
mkdir -p "$DEST"
APP="$DEST/Scaffold.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$REPO/assets/Scaffold.icns" "$APP/Contents/Resources/Scaffold.icns"

SRC="$(mktemp -d)/launcher.c"
cat > "$SRC" <<'C'
#include <fcntl.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>
extern char **environ;

int main(void) {
    const char *home = getenv("HOME");
    char path[4096], log[4096];
    snprintf(path, sizeof path, "/opt/homebrew/bin:/usr/local/bin:%s/.local/bin:%s/.cargo/bin:/usr/bin:/bin:/usr/sbin:/sbin", home, home);
    setenv("PATH", path, 1);
    snprintf(log, sizeof log, "%s/workspace/app.log", SCAFFOLD_REPO);
    int fd = open(log, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd >= 0) { dup2(fd, 1); dup2(fd, 2); close(fd); }
    if (chdir(SCAFFOLD_REPO) != 0) { perror("Scaffold: cannot open the repo folder"); return 1; }
    /* the shell loads nvm (for node) and starts the desktop app; it runs as our child, so it has our permissions */
    char *args[] = {"/bin/bash", "-c",
        "[ -s \"$HOME/.nvm/nvm.sh\" ] && . \"$HOME/.nvm/nvm.sh\"; exec /bin/bash ./run.sh --app --no-build", NULL};
    pid_t pid;
    if (posix_spawn(&pid, "/bin/bash", NULL, NULL, args, environ) != 0) { perror("Scaffold: cannot start"); return 1; }
    int status = 0;
    waitpid(pid, &status, 0);
    return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}
C
clang -O2 -DSCAFFOLD_REPO="\"$REPO\"" -o "$APP/Contents/MacOS/Scaffold" "$SRC"

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
  <key>CFBundleVersion</key><string>1.1</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSDocumentsFolderUsageDescription</key><string>Scaffold runs from its folder in Documents and reads your notes.</string>
  <key>NSDesktopFolderUsageDescription</key><string>Scaffold reads the course materials you keep on the Desktop.</string>
  <key>NSDownloadsFolderUsageDescription</key><string>Scaffold reads course materials you downloaded.</string>
</dict></plist>
PL
# the launcher stays in the background (LSUIElement); the Scaffold window shows its own Dock icon
codesign --force --deep --sign - --identifier local.scaffold.app "$APP" >/dev/null 2>&1
mkdir -p "$REPO/workspace"
touch "$APP"  # let Spotlight and Launchpad notice it
echo "Created $APP."
echo "Allow it once: System Settings → Privacy & Security → Full Disk Access → + → $APP"
echo "(If you rebuild the app later, remove the old entry there and add it again.)"
