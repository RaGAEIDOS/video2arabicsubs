#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# build-apt-repo.sh — assemble a Debian apt repository tree from the built
# .deb files, ready to be published as the ROOT of the gh-pages branch so it
# can be consumed with:
#
#   echo "deb [trusted=yes] https://RaGAEIDOS.github.io/video2arabicsubs stable main" \
#     | sudo tee /etc/apt/sources.list.d/v2as.list
#   sudo apt update
#   sudo apt install v2as
#
# Output (default): build/apt-repo/
#   pool/main/v/v2as/v2as_<ver>_amd64.deb
#   dists/stable/main/binary-amd64/Packages{,.gz}
#   dists/stable/Release[.gpg] + InRelease     (signed when APT_GPG_KEY is set)
#
#   ./scripts/build-apt-repo.sh                 # uses dist/*.deb
#   APT_GPG_KEY=<keyid> ./scripts/build-apt-repo.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REPO_DIR="${APT_REPO_DIR:-$ROOT/build/apt-repo}"
COMPONENT="main"
SUITE="stable"
ARCH="${DEB_ARCH:-amd64}"

shopt -s nullglob
DEBS=( "$@" "$ROOT"/dist/v2as_*_"$ARCH".deb )
if [ "${#DEBS[@]}" -eq 0 ]; then
  echo "No .deb found in dist/ — run scripts/build-deb.sh first." >&2
  exit 1
fi

echo "▸ Building apt repository → $REPO_DIR"
rm -rf "$REPO_DIR"
mkdir -p "$REPO_DIR/pool/main/v/v2as" "$REPO_DIR/dists/$SUITE/$COMPONENT/binary-$ARCH"

PACKAGES="$REPO_DIR/dists/$SUITE/$COMPONENT/binary-$ARCH/Packages"
: > "$PACKAGES"

hash_of() { # file alg → lowercase hex
  case "$2" in
    md5)    md5sum "$1" | awk '{print $1}' ;;
    sha1)   sha1sum "$1" | awk '{print $1}' ;;
    sha256) sha256sum "$1" | awk '{print $1}' ;;
  esac
}

for DEB in "${DEBS[@]}"; do
  NAME="$(basename "$DEB")"
  cp "$DEB" "$REPO_DIR/pool/main/v/v2as/$NAME"
  REL="pool/main/v/v2as/$NAME"
  DEST="$REPO_DIR/$REL"

  SIZE="$(stat -c %s "$DEST")"
  MD5="$(hash_of "$DEST" md5)"
  SHA1="$(hash_of "$DEST" sha1)"
  SHA256="$(hash_of "$DEST" sha256)"

  FIELD() { dpkg-deb -f "$DEB" "$1" 2>/dev/null || true; }

  {
    echo "Package: $(FIELD Package)"
    echo "Version: $(FIELD Version)"
    echo "Architecture: $(FIELD Architecture)"
    [ -n "$(FIELD Maintainer)" ] && echo "Maintainer: $(FIELD Maintainer)"
    [ -n "$(FIELD Installed-Size)" ] && echo "Installed-Size: $(FIELD Installed-Size)"
    [ -n "$(FIELD Depends)" ] && echo "Depends: $(FIELD Depends)"
    [ -n "$(FIELD Recommends)" ] && echo "Recommends: $(FIELD Recommends)"
    [ -n "$(FIELD Section)" ] && echo "Section: $(FIELD Section)"
    [ -n "$(FIELD Priority)" ] && echo "Priority: $(FIELD Priority)"
    [ -n "$(FIELD Homepage)" ] && echo "Homepage: $(FIELD Homepage)"
    echo "Filename: $REL"
    echo "Size: $SIZE"
    echo "MD5sum: $MD5"
    echo "SHA1: $SHA1"
    echo "SHA256: $SHA256"
    echo "Description: $(FIELD Description)"
    echo ""
  } >> "$PACKAGES"
done

gzip -9 -n -c "$PACKAGES" > "$PACKAGES.gz"

# ── Release (checksums for every file apt may fetch) ────────────────────────
RELEASE="$REPO_DIR/dists/$SUITE/Release"
DATE_RFC2822="$(date -Ru | sed 's/+0000/UTC/')"
rel_lines() { # file → " <hash> <size> <path>"
  # Paths inside Release are relative to the Release file's own directory
  # (dists/<suite>/) — this is what apt resolves the index files against.
  local f="$1" alg="$2" rel
  rel="${f#"$REPO_DIR/dists/$SUITE/"}"
  printf ' %s %s %s\n' "$(hash_of "$f" "$alg")" "$(stat -c %s "$f")" "$rel"
}

{
  echo "Origin: Video2ArabicSubs"
  echo "Label: Video2ArabicSubs"
  echo "Suite: $SUITE"
  echo "Codename: $SUITE"
  echo "Date: $DATE_RFC2822"
  echo "Architectures: $ARCH"
  echo "Components: $COMPONENT"
  echo "Description: Video2ArabicSubs official apt repository"
  echo "MD5Sum:"
  rel_lines "$PACKAGES" md5
  rel_lines "$PACKAGES.gz" md5
  echo "SHA1:"
  rel_lines "$PACKAGES" sha1
  rel_lines "$PACKAGES.gz" sha1
  echo "SHA256:"
  rel_lines "$PACKAGES" sha256
  rel_lines "$PACKAGES.gz" sha256
} > "$RELEASE"

# ── optional signing (when APT_GPG_KEY is provided) ─────────────────────────
if [ -n "${APT_GPG_KEY:-}" ] && command -v gpg >/dev/null 2>&1; then
  echo "▸ Signing Release with key $APT_GPG_KEY"
  gpg --batch --yes --local-user "$APT_GPG_KEY" \
      --digest-algo SHA256 --clearsign -o "$REPO_DIR/dists/$SUITE/InRelease" "$RELEASE"
  gpg --batch --yes --local-user "$APT_GPG_KEY" \
      --digest-algo SHA256 --armor --detach-sign -o "$RELEASE.gpg" "$RELEASE"
else
  echo "ℹ Unsigned repository — consumers need [trusted=yes] (see README)."
fi

echo "▸ Repository contents:"
( cd "$REPO_DIR" && find . -type f | sort | sed 's/^/    /' )
echo "▸ Done: $REPO_DIR"
