#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# v2as — Video2ArabicSubs launcher (shared by the .deb package and the
# portable .run installer).
#
#   • Resolves the app directory from its own location, so the same script
#     works for /opt/v2as (deb) and for a portable extract (~/.local/share).
#   • FIRST RUN: creates a per-user virtual environment in ~/.cache/v2as/venv
#     and installs requirements.txt into it automatically — the reason the
#     .deb itself stays tiny (~10 MB) while still being self-sufficient.
#   • Re-runs the install automatically whenever requirements.txt changes,
#     and on demand with:  v2as --setup
#   • Forwards every argument to the app:  v2as --web | --lang en | --version
#
# Exit codes: 0 ok · 1 environment/dependency problem.
# ─────────────────────────────────────────────────────────────────────────────
set -u

VERSION="0.4"

SELF="$(readlink -f "${BASH_SOURCE[0]:-$0}" 2>/dev/null || echo "$0")"
APP_DIR="$(cd "$(dirname "$SELF")" && pwd)"
CACHE_DIR="${XDG_CACHE_HOME:-${HOME:-/tmp}/.cache}/v2as"
VENV_DIR="$CACHE_DIR/venv"
REQ="$APP_DIR/requirements.txt"
STAMP="$CACHE_DIR/requirements.stamp"
VENV_LOG="$CACHE_DIR/venv.log"

say() { printf '%s\n' "$*"; }
err() { printf '%s\n' "$*" >&2; }

die() {
  err ""
  err "❌ $*"
  err ""
  exit 1
}

find_python() {
  for candidate in python3 python; do
    command -v "$candidate" >/dev/null 2>&1 && { printf '%s' "$candidate"; return 0; }
  done
  return 1
}

requirements_hash() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$REQ" | awk '{print $1}'
  else
    cksum "$REQ" | awk '{print $1"-"$2}'
  fi
}

# ── args ────────────────────────────────────────────────────────────────────
FORCE_SETUP=0
case "${1:-}" in
  --setup) FORCE_SETUP=1; shift ;;
esac

if [ ! -f "$REQ" ]; then
  die "application files not found in: $APP_DIR
       (re-install the package, or re-run the .run installer)"
fi

PY="$(find_python)" || die "Python 3 was not found.
       Debian/Ubuntu:  sudo apt install python3 python3-venv python3-tk
       Fedora:         sudo dnf install python3 python3-tkinter"

mkdir -p "$CACHE_DIR" || die "cannot write to $CACHE_DIR"

# ── 1) virtual environment ──────────────────────────────────────────────────
if [ ! -x "$VENV_DIR/bin/python" ]; then
  say "⏳ Video2ArabicSubs $VERSION — first run: creating a virtual environment…"
  if ! "$PY" -m venv "$VENV_DIR" 2>"$VENV_LOG"; then
    err "   python3 -m venv failed — the python3-venv package is required."
    err "   Debian/Ubuntu:  sudo apt install python3-venv python3-pip"
    [ -s "$VENV_LOG" ] && err "   log: $VENV_LOG"
    die "could not create the virtual environment"
  fi
fi

# ── 2) dependencies (installed only when missing/changed) ───────────────────
CURRENT_SUM="$(requirements_hash)"
STORED_SUM="none"
[ -f "$STAMP" ] && STORED_SUM="$(cat "$STAMP" 2>/dev/null || echo none)"

if [ "$FORCE_SETUP" = 1 ] || [ "$CURRENT_SUM" != "$STORED_SUM" ]; then
  say "⏳ Installing Python dependencies (this can take a few minutes)…"
  say "   venv: $VENV_DIR"
  "$VENV_DIR/bin/python" -m pip install --upgrade pip --disable-pip-version-check -q \
    || say "   (pip self-upgrade skipped)"
  if ! "$VENV_DIR/bin/python" -m pip install -r "$REQ" \
        --disable-pip-version-check; then
    die "dependency installation failed.
       Check your internet connection, then re-run:  v2as --setup
       (manual equivalent:  $VENV_DIR/bin/python -m pip install -r $REQ)"
  fi
  printf '%s' "$CURRENT_SUM" > "$STAMP" || true
fi

# ── 3) start the app ────────────────────────────────────────────────────────
exec "$VENV_DIR/bin/python" "$APP_DIR/main.py" "$@"
