#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# build-deb.sh — build dist/v2as_<version>_amd64.deb
#
# The package is intentionally *lightweight* (source-only payload, well under
# 10 MB): on first run `v2as` installs the Python dependencies into the
# per-user venv (~/.cache/v2as/venv) automatically.
#
#   ./scripts/build-deb.sh            # → dist/v2as_0.4_amd64.deb
#   ./scripts/build-deb.sh --install  # build + sudo dpkg -i (local test)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="$(sed -n 's/^__version__ *= *"\([^"]*\)".*/\1/p' app/__init__.py)"
[ -n "$VERSION" ] || { echo "could not read __version__" >&2; exit 1; }
ARCH="${DEB_ARCH:-amd64}"
PKG="v2as"
STAGE="$ROOT/build/debian"
OUT="$ROOT/dist"

echo "▸ Building $PKG $VERSION ($ARCH)"

rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" "$STAGE/opt/$PKG" "$STAGE/usr/bin" \
         "$STAGE/usr/share/applications" "$STAGE/usr/share/pixmaps" \
         "$STAGE/usr/share/icons/hicolor/256x256/apps" "$OUT"

# ── payload: /opt/v2as (runtime sources only) ───────────────────────────────
tar -C "$ROOT" \
    --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='venv' --exclude='.venv' \
    --exclude='dist' --exclude='build' --exclude='.git' \
    --exclude='web/data' --exclude='tests' --exclude='screenshots' \
    -cf - core app web main.py requirements.txt LICENSE img \
    | tar -C "$STAGE/opt/$PKG" -xf -

install -m 0755 packaging/v2as.sh "$STAGE/opt/$PKG/v2as"
install -m 0755 packaging/debian/usr/bin/v2as "$STAGE/usr/bin/v2as"
install -m 0644 packaging/debian/usr/share/applications/v2as.desktop \
                 "$STAGE/usr/share/applications/v2as.desktop"

# ── icons (hicolor 256×256 + classic pixmaps fallback) ─────────────────────
ICON_SRC="$ROOT/img/first-logo-design.png"
ICON256="$STAGE/usr/share/icons/hicolor/256x256/apps/v2as.png"
if command -v convert >/dev/null 2>&1; then
  convert "$ICON_SRC" -resize 256x256 "$ICON256"
  install -m 0644 "$ICON256" "$STAGE/usr/share/pixmaps/v2as.png"
elif command -v magick >/dev/null 2>&1; then
  magick "$ICON_SRC" -resize 256x256 "$ICON256"
  install -m 0644 "$ICON256" "$STAGE/usr/share/pixmaps/v2as.png"
else
  # no ImageMagick → ship the original in pixmaps, drop the size-tagged dir
  rm -rf "$STAGE/usr/share/icons"
  install -m 0644 "$ICON_SRC" "$STAGE/usr/share/pixmaps/v2as.png"
fi

# ── control fields ──────────────────────────────────────────────────────────
SIZE_KB="$(du -sk "$STAGE/opt" | awk '{print $1}')"
sed -e "s/@VERSION@/$VERSION/g" -e "s/@SIZE_KB@/$SIZE_KB/g" \
    packaging/debian/DEBIAN/control > "$STAGE/DEBIAN/control"

# lintian-friendly permissions (DEBIAN scripts must be 0755, files 0644)
find "$STAGE" -type d -exec chmod 755 {} +
find "$STAGE" -type f ! -path '*/DEBIAN/*' -exec chmod 644 {} +
find "$STAGE" -type f -path '*/usr/bin/*' -exec chmod 755 {} +
chmod 755 "$STAGE/opt/$PKG/v2as"

DEB="$OUT/${PKG}_${VERSION}_${ARCH}.deb"
if command -v dpkg-deb >/dev/null 2>&1; then
  dpkg-deb --build --root-owner-group "$STAGE" "$DEB"
else
  echo "dpkg-deb not found — cannot produce the .deb here" >&2
  exit 1
fi

echo "▸ Built: $DEB ($(du -h "$DEB" | awk '{print $1}'))"
dpkg-deb --info "$DEB" | sed -n '1,12p'

if [ "${1:-}" = "--install" ]; then
  echo "▸ Installing…"
  sudo dpkg -i "$DEB" || sudo apt-get install -f -y
  echo "▸ Done — run:  v2as"
fi
