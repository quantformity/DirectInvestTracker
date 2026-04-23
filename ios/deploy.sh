#!/usr/bin/env bash
# deploy.sh — Build and install DirectInvestTracker on a connected iPhone
# Usage:
#   ./deploy.sh                        # auto-detect device + team
#   ./deploy.sh DEVICE_UDID TEAM_ID    # explicit device and team

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCHEME="DirectInvestTracker"
DEVICE_UDID="${1:-}"
TEAM_ID="${2:-}"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}▶ $*${NC}"; }
success() { echo -e "${GREEN}✔ $*${NC}"; }
warn()    { echo -e "${YELLOW}⚠ $*${NC}"; }
error()   { echo -e "${RED}✖ $*${NC}"; exit 1; }

# ── Check Xcode tools ─────────────────────────────────────────────────────────
command -v xcodebuild &>/dev/null || error "xcodebuild not found. Install Xcode."

# ── Detect connected device ───────────────────────────────────────────────────
if [ -z "$DEVICE_UDID" ]; then
    info "Looking for connected iPhone…"
    # Try xcrun devicectl (Xcode 15+)
    if xcrun devicectl list devices &>/dev/null 2>&1; then
        DEVICE_UDID=$(xcrun devicectl list devices 2>/dev/null \
            | grep -i "iphone\|ipad" \
            | grep -v "Simulator" \
            | grep -oE '[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}' \
            | head -1)
    fi
    # Fallback: instruments
    if [ -z "$DEVICE_UDID" ]; then
        DEVICE_UDID=$(instruments -s devices 2>/dev/null \
            | grep -i "iphone\|ipad" \
            | grep -v "Simulator" \
            | grep -o '[0-9a-f]\{40\}\|[0-9A-F-]\{36\}' \
            | head -1)
    fi
    [ -z "$DEVICE_UDID" ] && error "No iPhone found. Connect your iPhone via USB and trust this Mac."
    info "Found device: $DEVICE_UDID"
fi

# ── Detect signing team ───────────────────────────────────────────────────────
if [ -z "$TEAM_ID" ]; then
    # Try valid identities first, then fall back to all (handles untrusted root cert)
    TEAM_ID=$(security find-identity -v -p codesigning 2>/dev/null \
        | grep -o '([A-Z0-9]\{10\})' | head -1 | tr -d '()' || true)
    if [ -z "$TEAM_ID" ]; then
        TEAM_ID=$(security find-identity 2>/dev/null \
            | grep "Apple Development" \
            | grep -o '([A-Z0-9]\{10\})' | head -1 | tr -d '()' || true)
    fi
    [ -z "$TEAM_ID" ] && error "No signing identity found.\nOpen Xcode → Settings → Accounts and add your Apple ID first.\nOr run: ./deploy.sh DEVICE_UDID YOUR_TEAM_ID"
    info "Using team: $TEAM_ID"
fi

# ── Resolve app path (use Xcode's last build; skip CLI rebuild) ───────────────
APP_PATH=$(find ~/Library/Developer/Xcode/DerivedData -name "$SCHEME.app" \
    -path "*Debug-iphoneos*" 2>/dev/null \
    | xargs ls -dt 2>/dev/null | head -1)
if [ -z "$APP_PATH" ]; then
    warn "No Xcode device build found — attempting CLI build..."
    "$SCRIPT_DIR/build.sh" device "$TEAM_ID"
    APP_PATH=$(find ~/Library/Developer/Xcode/DerivedData -name "$SCHEME.app" \
        -path "*Debug-iphoneos*" 2>/dev/null \
        | xargs ls -dt 2>/dev/null | head -1)
fi
[ -z "$APP_PATH" ] && error "Could not find built .app. Open Xcode, select your iPhone, and press Cmd+B first."
info "App: $APP_PATH"

# ── Install ───────────────────────────────────────────────────────────────────
info "Installing on device ${DEVICE_UDID}..."
warn "If prompted on your iPhone, tap 'Trust'."

if xcrun devicectl device install app --device "$DEVICE_UDID" "$APP_PATH" 2>/dev/null; then
    success "App installed successfully!"
elif command -v ios-deploy &>/dev/null; then
    # Fallback to ios-deploy
    ios-deploy --bundle "$APP_PATH" --id "$DEVICE_UDID"
    success "App installed via ios-deploy."
else
    warn "xcrun devicectl failed. Trying alternative method…"
    xcodebuild \
        -project "$SCRIPT_DIR/DirectInvestTracker.xcodeproj" \
        -scheme  "$SCHEME" \
        -destination "platform=iOS,id=$DEVICE_UDID" \
        -allowProvisioningUpdates \
        CODE_SIGN_STYLE=Automatic \
        DEVELOPMENT_TEAM="$TEAM_ID" \
        install
    success "App installed via xcodebuild install."
fi

echo ""
success "Done! Open the app on your iPhone."
echo -e "${YELLOW}Note: With a free Apple ID, the certificate expires in 7 days.${NC}"
echo -e "${YELLOW}      Re-run ./deploy.sh to renew it.${NC}"
