#!/usr/bin/env bash
set +e +u +o pipefail

APP_ID="beast-mode-mastering"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor"

rm -f "$BIN_DIR/${APP_ID}"
rm -f "$APP_DIR/${APP_ID}.desktop"
rm -f "$ICON_DIR/scalable/apps/${APP_ID}.svg"

for SZ in 16 24 32 48 64 128 256 512; do
  rm -f "$ICON_DIR/${SZ}x${SZ}/apps/${APP_ID}.png"
done

update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
gtk-update-icon-cache "$ICON_DIR" >/dev/null 2>&1 || true
xdg-desktop-menu forceupdate >/dev/null 2>&1 || true

echo "Desktop integration removed for ${APP_ID}"
