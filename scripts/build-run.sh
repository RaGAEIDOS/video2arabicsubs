#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# build-run.sh — build dist/v2as-<version>-linux-x86_64.run
#
# A self-extracting, *portable* installer: no root needed. It unpacks the
# application under ~/.local/share/v2as, links `v2as` into ~/.local/bin and
# then starts it — the shared launcher performs the usual first-run venv setup.
#
#   ./scripts/build-run.sh                # → dist/v2as-0.4-linux-x86_64.run
#   V2AS_INSTALL_DIR=/opt/v2as sudo ...    # custom destination (as root)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="$(sed -n 's/^__version__ *= *"\([^"]*\)".*/\1/p' app/__init__.py)"
[ -n "$VERSION" ] || { echo "could not read __version__" >&2; exit 1; }
PKG="v2as"
STAGE="$ROOT/build/run"
PAYLOAD="$STAGE/$PKG-$VERSION"
OUT="$ROOT/dist"
ARCH="$(uname -m)"

echo "▸ Building $PKG $VERSION self-extracting installer ($ARCH)"

rm -rf "$STAGE"
mkdir -p "$PAYLOAD" "$OUT"

# ── payload ─────────────────────────────────────────────────────────────────
tar -C "$ROOT" \
    --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='venv' --exclude='.venv' \
    --exclude='dist' --exclude='build' --exclude='.git' \
    --exclude='web/data' --exclude='tests' --exclude='screenshots' \
    -cf - core app web main.py requirements.txt LICENSE img \
    | tar -C "$PAYLOAD" -xf -
install -m 0755 packaging/v2as.sh "$PAYLOAD/v2as"
cat > "$PAYLOAD/INSTALL.txt" <<EOF
Video2ArabicSubs $VERSION — portable install
=============================================
Start:            ./v2as
Web UI:           ./v2as --web
English UI:       ./v2as --lang en
Reinstall deps:   ./v2as --setup

First start installs the Python dependencies into ~/.cache/v2as/venv
(a few minutes, once). Application files live in this folder.
EOF

# ── self-extracting header ──────────────────────────────────────────────────
HEADER="$STAGE/header.sh"
cat > "$HEADER" <<EOF
#!/usr/bin/env bash
# Video2ArabicSubs $VERSION — self-extracting installer (no root required).
set -eu
PKG="$PKG"
VERSION="$VERSION"
TARGET="\${V2AS_INSTALL_DIR:-\${HOME:-/tmp}/.local/share/\$PKG-\$VERSION}"
SKIP="\$(awk '/^__ARCHIVE_BELOW__\$/ { print NR + 1; exit }' "\$0")"

echo "▸ Extracting \$PKG \$VERSION → \$TARGET"
mkdir -p "\$TARGET"
tail -n +"\$SKIP" "\$0" | tar -xzf - -C "\$TARGET"
APP="\$TARGET/\$PKG-\$VERSION"
chmod +x "\$APP/v2as" 2>/dev/null || true

BIN_DIR="\${HOME:-/tmp}/.local/bin"
if mkdir -p "\$BIN_DIR" 2>/dev/null; then
  ln -sf "\$APP/v2as" "\$BIN_DIR/\$PKG" 2>/dev/null && echo "▸ Launcher: \$BIN_DIR/\$PKG"
  case ":\$PATH:" in
    *":\$BIN_DIR:"*) ;;
    *) echo "ℹ To use the short command, add to PATH:  export PATH=\"\$BIN_DIR:\$PATH\"" ;;
  esac
fi

echo "▸ Done. Application files: \$APP"
echo "▸ The first start installs the Python dependencies (a few minutes)."
if [ "\${1:-}" = "--no-start" ]; then
  echo "▸ Start later with:  \$APP/v2as"
  exit 0
fi
echo "▸ Starting…"
exec "\$APP/v2as" "\$@"
exit 0
__ARCHIVE_BELOW__
EOF

# ── assemble (header + gzipped tarball) ─────────────────────────────────────
RUN="$OUT/$PKG-$VERSION-linux-$ARCH.run"
{
  cat "$HEADER"
  tar -C "$STAGE" -czf - "$PKG-$VERSION"
} > "$RUN"
chmod 0755 "$RUN"

echo "▸ Built: $RUN ($(du -h "$RUN" | awk '{print $1}'))"
