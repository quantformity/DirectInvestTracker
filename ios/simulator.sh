#!/usr/bin/env bash
# simulator.sh — Build and launch DirectInvestTracker in the iOS Simulator
# Usage:
#   ./simulator.sh               # use default simulator (iPhone 16 Plus)
#   ./simulator.sh "iPhone 17"   # use a specific simulator by name

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCHEME="DirectInvestTracker"
BUNDLE_ID="com.quantformity.directinvest"
REQUESTED_SIM="${1:-}"

# Default simulator UDID (iPhone 16 Plus)
DEFAULT_SIM_ID="22DABA2C-EC2C-4D47-B0D7-0B35F1FF7F65"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}▶ $*${NC}"; }
success() { echo -e "${GREEN}✔ $*${NC}"; }
warn()    { echo -e "${YELLOW}⚠ $*${NC}"; }
error()   { echo -e "${RED}✖ $*${NC}"; exit 1; }

# ── Resolve simulator ─────────────────────────────────────────────────────────
if [ -n "$REQUESTED_SIM" ]; then
    SIM_ID=$(xcrun simctl list devices available 2>/dev/null \
        | grep "$REQUESTED_SIM" \
        | grep -o '[A-F0-9-]\{36\}' \
        | head -1)
    [ -z "$SIM_ID" ] && error "Simulator '$REQUESTED_SIM' not found.\nAvailable:\n$(xcrun simctl list devices available | grep -E 'iPhone|iPad')"
    info "Using simulator: $REQUESTED_SIM ($SIM_ID)"
else
    SIM_ID="$DEFAULT_SIM_ID"
    SIM_NAME=$(xcrun simctl list devices available 2>/dev/null \
        | grep "$SIM_ID" | sed 's/ *(.*//' | xargs)
    info "Using simulator: ${SIM_NAME:-iPhone 16 Plus} ($SIM_ID)"
fi

# ── Boot simulator ────────────────────────────────────────────────────────────
SIM_STATE=$(xcrun simctl list devices 2>/dev/null | grep "$SIM_ID" | grep -o 'Booted\|Shutdown' | head -1)
if [ "$SIM_STATE" != "Booted" ]; then
    info "Booting simulator…"
    xcrun simctl boot "$SIM_ID"
fi
open -a Simulator

# ── Build ─────────────────────────────────────────────────────────────────────
"$SCRIPT_DIR/build.sh" simulator

# ── Resolve app path ──────────────────────────────────────────────────────────
if [ -f /tmp/dit_simulator_app_path.txt ]; then
    APP_PATH=$(cat /tmp/dit_simulator_app_path.txt)
else
    APP_PATH=$(find ~/Library/Developer/Xcode/DerivedData -name "$SCHEME.app" \
        -path "*Debug-iphonesimulator*" 2>/dev/null | sort -t/ -k1,1 | tail -1)
fi
[ -z "$APP_PATH" ] && error "Could not find built .app — did the build succeed?"
info "App: $APP_PATH"

# ── Install and launch ────────────────────────────────────────────────────────
info "Installing…"
xcrun simctl terminate "$SIM_ID" "$BUNDLE_ID" 2>/dev/null || true
xcrun simctl install "$SIM_ID" "$APP_PATH"

info "Launching…"
xcrun simctl launch "$SIM_ID" "$BUNDLE_ID"

success "App launched in simulator."
