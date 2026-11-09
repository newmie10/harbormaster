#!/bin/bash
# Build a patched touchHLE that can run Harbor Master (iOS, v2.1).
# Safe to re-run: each step is skipped if already done.
#
# Needs: git, curl, tar, cmake, a C/C++ compiler, and Rust (https://rustup.rs).
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
TOUCHHLE_DIR="${TOUCHHLE_DIR:-$here/touchHLE}"
TOUCHHLE_REPO="https://github.com/touchHLE/touchHLE.git"
TOUCHHLE_COMMIT="ca1de89c578e79746f33c1332e28efd106c334ba" # patch is made against this
BOOST_URL="https://archives.boost.io/release/1.81.0/source/boost_1_81_0.tar.gz"
PATCH="$here/patches/touchhle-harbormaster.patch"
IPA="$here/HarborMaster Decrypted.ipa"

for tool in git curl tar cmake cc c++ cargo; do
  command -v "$tool" >/dev/null || { echo "missing required tool: $tool" >&2; exit 1; }
done

if [ ! -d "$TOUCHHLE_DIR/.git" ]; then
  echo "==> Fetching touchHLE $TOUCHHLE_COMMIT"
  git init -q "$TOUCHHLE_DIR"
  git -C "$TOUCHHLE_DIR" remote add origin "$TOUCHHLE_REPO"
  git -C "$TOUCHHLE_DIR" fetch -q --depth 1 origin "$TOUCHHLE_COMMIT"
  git -C "$TOUCHHLE_DIR" checkout -q FETCH_HEAD
  echo "==> Fetching submodules (SDL, OpenAL, dynarmic, ...)"
  git -C "$TOUCHHLE_DIR" submodule update -q --init --recursive --depth 1
fi

# dynarmic needs Boost headers. touchHLE's build uses vendor/boost if present,
# which avoids needing a system boost-devel package (and sudo).
if [ ! -d "$TOUCHHLE_DIR/vendor/boost/boost" ]; then
  echo "==> Downloading Boost 1.81 headers"
  curl -fsSL "$BOOST_URL" | tar -xz -C "$TOUCHHLE_DIR/vendor" boost_1_81_0/boost
  mv "$TOUCHHLE_DIR/vendor/boost_1_81_0" "$TOUCHHLE_DIR/vendor/boost"
fi

if git -C "$TOUCHHLE_DIR" apply --reverse --check "$PATCH" 2>/dev/null; then
  echo "==> Harbor Master patch already applied"
else
  echo "==> Applying Harbor Master patch"
  git -C "$TOUCHHLE_DIR" apply "$PATCH"
fi

echo "==> Building touchHLE (release; first build takes several minutes)"
# GCC 15 defaults to C23 (breaks bundled SDL2) and is stricter about
# <cstdint> includes (breaks bundled OpenAL Soft); these flags restore the
# older behaviour. Harmless on older compilers.
(cd "$TOUCHHLE_DIR" && CFLAGS="-std=gnu17" CXXFLAGS="-include cstdint" cargo build --release)

echo
echo "touchHLE built: $TOUCHHLE_DIR/target/release/touchHLE"
if [ -f "$IPA" ]; then
  echo "Run ./play.sh to start the game."
else
  echo "Now download the game into this folder as \"HarborMaster Decrypted.ipa\":"
  echo "  https://archive.org/download/harbor-master-ios"
  echo "then run ./play.sh"
fi
