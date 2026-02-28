#!/usr/bin/env bash
# enable-menu-icons.sh — Enable "Icons in Menus" in LibreOffice on Linux/GTK3.
#
# On Linux with GTK3, LibreOffice hides menu icons by default.
# This script safely enables them by patching registrymodifications.xcu.
#
# Usage:
#   bash scripts/enable-menu-icons.sh          # patch default profile
#   bash scripts/enable-menu-icons.sh --check  # check current state
#   bash scripts/enable-menu-icons.sh --revert # revert to system default
#
# Requirements:
#   - LibreOffice must NOT be running (it overwrites the file on exit)
#   - Creates a backup before any modification
#
# What it does:
#   Sets Office.Common.View.Menu.ShowIconsInMenues = true
#   Sets Office.Common.View.Menu.IsSystemIconsInMenus = false
#
# This is equivalent to: Tools > Options > LibreOffice > View > Icon in Menus
#
set -euo pipefail

REGISTRY="${HOME}/.config/libreoffice/4/user/registrymodifications.xcu"
SHOW_ITEM='<item oor:path="/org.openoffice.Office.Common/View/Menu"><prop oor:name="ShowIconsInMenues" oor:op="fuse"><value>true</value></prop></item>'
SYSTEM_ITEM='<item oor:path="/org.openoffice.Office.Common/View/Menu"><prop oor:name="IsSystemIconsInMenus" oor:op="fuse"><value>false</value></prop></item>'

die() { echo "ERROR: $*" >&2; exit 1; }
info() { echo ":: $*"; }

# ── Check LibreOffice is not running ──────────────────────────────────
check_lo_not_running() {
    if pgrep -x soffice.bin >/dev/null 2>&1; then
        die "LibreOffice is running. Close it first, then re-run this script."
    fi
}

# ── Check registry file exists ────────────────────────────────────────
check_registry() {
    if [ ! -f "$REGISTRY" ]; then
        die "Registry file not found: $REGISTRY
Start LibreOffice at least once to create the user profile."
    fi
}

# ── Check current state ──────────────────────────────────────────────
check_state() {
    check_registry
    local has_show=false
    local has_system=false
    if grep -q 'ShowIconsInMenues.*true' "$REGISTRY" 2>/dev/null; then
        has_show=true
    fi
    if grep -q 'IsSystemIconsInMenus.*false' "$REGISTRY" 2>/dev/null; then
        has_system=true
    fi
    if $has_show && $has_system; then
        info "Menu icons are ENABLED (ShowIconsInMenues=true, IsSystemIconsInMenus=false)"
        return 0
    elif ! $has_show && ! $has_system; then
        info "Menu icons use SYSTEM DEFAULT (icons hidden on GTK3/Linux)"
        return 1
    else
        info "Menu icons in PARTIAL state (ShowIconsInMenues=$has_show, IsSystemIconsInMenus=!$has_system)"
        return 1
    fi
}

# ── Backup ────────────────────────────────────────────────────────────
backup_registry() {
    local backup="${REGISTRY}.bak.$(date +%Y%m%d%H%M%S)"
    cp "$REGISTRY" "$backup"
    info "Backup created: $backup"
}

# ── Remove our settings (idempotent) ─────────────────────────────────
remove_settings() {
    # Remove any existing ShowIconsInMenues and IsSystemIconsInMenus items
    sed -i '/<item oor:path="\/org.openoffice.Office.Common\/View\/Menu"><prop oor:name="ShowIconsInMenues"/d' "$REGISTRY"
    sed -i '/<item oor:path="\/org.openoffice.Office.Common\/View\/Menu"><prop oor:name="IsSystemIconsInMenus"/d' "$REGISTRY"
}

# ── Apply settings ───────────────────────────────────────────────────
apply_settings() {
    check_lo_not_running
    check_registry
    backup_registry

    # Remove any existing entries first (idempotent)
    remove_settings

    # Insert before closing </oor:items> tag
    sed -i "s|</oor:items>|${SHOW_ITEM}\n${SYSTEM_ITEM}\n</oor:items>|" "$REGISTRY"

    # Verify
    if grep -q 'ShowIconsInMenues.*true' "$REGISTRY" && \
       grep -q 'IsSystemIconsInMenus.*false' "$REGISTRY"; then
        info "Menu icons ENABLED successfully."
        info "Restart LibreOffice to see the change."
    else
        die "Patch failed — please check $REGISTRY manually."
    fi
}

# ── Revert to system default ─────────────────────────────────────────
revert_settings() {
    check_lo_not_running
    check_registry
    backup_registry
    remove_settings
    info "Reverted to system default (menu icons controlled by desktop theme)."
    info "Restart LibreOffice to see the change."
}

# ── Main ─────────────────────────────────────────────────────────────
case "${1:-}" in
    --check)
        check_state
        ;;
    --revert)
        revert_settings
        ;;
    --help|-h)
        sed -n '2,/^$/s/^# //p' "$0"
        ;;
    "")
        apply_settings
        ;;
    *)
        die "Unknown option: $1 (use --check, --revert, or no argument)"
        ;;
esac
