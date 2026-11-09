#!/bin/bash
# Launch the original Harbor Master (v2.1) in the patched touchHLE built by
# ./setup.sh. Controls: mouse = finger. Saves live in touchHLE/touchHLE_sandbox.
#
# Default: 2x resolution (960x640 window). Extra args go to touchHLE, e.g.
#   ./play.sh --fullscreen        fill the screen
#   ./play.sh --scale-hack=3      even sharper/bigger window
here="$(cd "$(dirname "$0")" && pwd)"
TOUCHHLE_DIR="${TOUCHHLE_DIR:-$here/touchHLE}"
IPA="$here/HarborMaster Decrypted.ipa"

[ -x "$TOUCHHLE_DIR/target/release/touchHLE" ] || { echo "touchHLE not built; run ./setup.sh first" >&2; exit 1; }
[ -f "$IPA" ] || { echo "missing \"$IPA\"; download it from https://archive.org/download/harbor-master-ios" >&2; exit 1; }

cd "$TOUCHHLE_DIR" || exit 1
# No sound backend is built in; OpenAL's silent "null" driver keeps the game's
# music/sound calls from failing (starting a match crashes without it).
export ALSOFT_DRIVERS=null
exec target/release/touchHLE "$IPA" --scale-hack=2 "$@"
