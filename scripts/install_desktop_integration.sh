#!/usr/bin/env bash
set +e +u +o pipefail

APP_ID="beast-mode-mastering"
APP_NAME="Beast Mode Mastering"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ICON_SRC="$REPO_DIR/assets/icons/${APP_ID}.svg"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor"

mkdir -p "$BIN_DIR" "$APP_DIR" "$ICON_DIR/scalable/apps"

for SZ in 16 24 32 48 64 128 256 512; do
  mkdir -p "$ICON_DIR/${SZ}x${SZ}/apps"
done

cp -f "$ICON_SRC" "$ICON_DIR/scalable/apps/${APP_ID}.svg"

for SZ in 16 24 32 48 64 128 256 512; do
  if command -v rsvg-convert >/dev/null 2>&1; then
    rsvg-convert -w "$SZ" -h "$SZ" "$ICON_SRC" > "$ICON_DIR/${SZ}x${SZ}/apps/${APP_ID}.png"
  fi
done

DESKTOP_ICON="$ICON_DIR/256x256/apps/${APP_ID}.png"
if [ ! -f "$DESKTOP_ICON" ]; then
  DESKTOP_ICON="$ICON_DIR/scalable/apps/${APP_ID}.svg"
fi

cat > "$BIN_DIR/${APP_ID}" <<LAUNCH
#!/usr/bin/env bash
set +e +u +o pipefail
REPO_DIR="$REPO_DIR"
cd "\$REPO_DIR" || exit 0

if [ -x "\$REPO_DIR/.venv/bin/python" ]; then
  exec "\$REPO_DIR/.venv/bin/python" -m beast_mode_mastering.app "\$@"
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 -m beast_mode_mastering.app "\$@"
fi

echo "Python 3 not found."
LAUNCH

chmod +x "$BIN_DIR/${APP_ID}"

cat > "$APP_DIR/${APP_ID}.desktop" <<DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=$APP_NAME
Comment=AI-powered Linux mastering assistant
Exec=$BIN_DIR/${APP_ID}
Path=$REPO_DIR
Icon=$DESKTOP_ICON
Terminal=false
Categories=AudioVideo;Audio;Music;
Keywords=audio;music;mastering;mix;wav;ai;
StartupNotify=true
DESKTOP

chmod 644 "$APP_DIR/${APP_ID}.desktop"

update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
gtk-update-icon-cache "$ICON_DIR" >/dev/null 2>&1 || true
xdg-desktop-menu forceupdate >/dev/null 2>&1 || true

echo "Installed desktop launcher:"
printf '  %s\n' "$APP_DIR/${APP_ID}.desktop"
echo "Installed launcher command:"
printf '  %s\n' "$BIN_DIR/${APP_ID}"
echo "Installed icon base:"
printf '  %s\n' "$ICON_DIR"
