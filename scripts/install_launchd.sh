#!/bin/bash
# Install the weekday 09:00 job for this repo. Re-running replaces the existing job.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$HOME/Library/LaunchAgents/com.hanip.daily.plist"
mkdir -p "$REPO/logs" "$HOME/Library/LaunchAgents"
sed -e "s|__REPO__|$REPO|g" -e "s|__HOME__|$HOME|g" "$REPO/scripts/com.hanip.daily.plist" > "$DEST"
plutil -lint "$DEST"
launchctl bootout "gui/$(id -u)/com.hanip.daily" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DEST"
echo "installed: $DEST"
