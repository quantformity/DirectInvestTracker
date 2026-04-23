#!/usr/bin/env bash
# build.sh — Build DirectInvestTracker for simulator or device
# Usage:
#   ./build.sh                  # build for simulator (default)
#   ./build.sh simulator        # build for simulator
#   ./build.sh device           # build for device (requires TEAM_ID)
#   ./build.sh device TEAM_ID   # build for device with explicit team

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$SCRIPT_DIR/DirectInvestTracker.xcodeproj"
SCHEME="DirectInvestTracker"
TARGET="${1:-simulator}"
TEAM_ID="${2:-}"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}▶ $*${NC}"; }
success() { echo -e "${GREEN}✔ $*${NC}"; }
warn()    { echo -e "${YELLOW}⚠ $*${NC}"; }
error()   { echo -e "${RED}✖ $*${NC}"; exit 1; }

# ── Regenerate project ────────────────────────────────────────────────────────
if command -v xcodegen &>/dev/null; then
    info "Regenerating Xcode project with xcodegen…"
    xcodegen generate --spec "$SCRIPT_DIR/project.yml" --quiet
elif [ -f /tmp/xcodegen/bin/xcodegen ]; then
    info "Regenerating Xcode project with xcodegen…"
    /tmp/xcodegen/bin/xcodegen generate --spec "$SCRIPT_DIR/project.yml" --quiet
else
    warn "xcodegen not found — skipping project regeneration"
fi

# ── Build ─────────────────────────────────────────────────────────────────────
if [ "$TARGET" = "device" ]; then
    # Resolve team ID
    if [ -z "$TEAM_ID" ]; then
        TEAM_ID=$(xcrun security find-identity -v -p codesigning 2>/dev/null \
            | grep -o '\[[A-Z0-9]\{10\}\]' | head -1 | tr -d '[]')
    fi
    [ -z "$TEAM_ID" ] && error "No signing identity found. Run: ./build.sh device YOUR_TEAM_ID\nFind your Team ID at: https://developer.apple.com/account"

    info "Building for device (team: $TEAM_ID)..."
    if command -v xcpretty &>/dev/null; then
        xcodebuild \
            -project "$PROJECT" \
            -scheme  "$SCHEME" \
            -configuration Debug \
            -destination 'generic/platform=iOS' \
            -allowProvisioningUpdates \
            CODE_SIGN_STYLE=Automatic \
            DEVELOPMENT_TEAM="$TEAM_ID" \
            build | xcpretty || error "Device build failed."
    else
        xcodebuild \
            -project "$PROJECT" \
            -scheme  "$SCHEME" \
            -configuration Debug \
            -destination 'generic/platform=iOS' \
            -allowProvisioningUpdates \
            CODE_SIGN_STYLE=Automatic \
            DEVELOPMENT_TEAM="$TEAM_ID" \
            build || error "Device build failed."
    fi

    APP_PATH=$(find ~/Library/Developer/Xcode/DerivedData -name "$SCHEME.app" \
        -path "*Debug-iphoneos*" 2>/dev/null | sort -t/ -k1,1 | tail -1)
    success "Device build: $APP_PATH"
    echo "$APP_PATH" > /tmp/dit_device_app_path.txt

else
    # Default simulator ID
    SIM_ID="22DABA2C-EC2C-4D47-B0D7-0B35F1FF7F65"

    info "Building for simulator..."
    if command -v xcpretty &>/dev/null; then
        xcodebuild \
            -project "$PROJECT" \
            -scheme  "$SCHEME" \
            -configuration Debug \
            -destination "platform=iOS Simulator,id=$SIM_ID" \
            build | xcpretty || error "Simulator build failed."
    else
        xcodebuild \
            -project "$PROJECT" \
            -scheme  "$SCHEME" \
            -configuration Debug \
            -destination "platform=iOS Simulator,id=$SIM_ID" \
            build || error "Simulator build failed."
    fi

    APP_PATH=$(find ~/Library/Developer/Xcode/DerivedData -name "$SCHEME.app" \
        -path "*Debug-iphonesimulator*" 2>/dev/null | sort -t/ -k1,1 | tail -1)
    success "Simulator build: $APP_PATH"
    echo "$APP_PATH" > /tmp/dit_simulator_app_path.txt
fi

success "Build complete."
