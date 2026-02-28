#!/bin/bash
# Dev-mode deploy: regenerate manifests and hot-deploy to LO cache.
#
# Requires a prior normal install (install-plugin.sh --force) so the cache
# directory exists. After that, use this script for fast iteration.
#
# Usage:
#   ./scripts/dev-deploy.sh              # Regenerate + deploy to cache
#   ./scripts/dev-deploy.sh --no-gen     # Deploy only (skip generate_manifest)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

NO_GEN=false
if [ "${1:-}" = "--no-gen" ]; then
    NO_GEN=true
fi

echo ""
echo "=== Dev Deploy ==="
echo ""

# ── Regenerate manifests ────────────────────────────────────────────────────

if ! $NO_GEN; then
    echo "[*] Regenerating manifests..."
    python3 "$SCRIPT_DIR/generate_manifest.py"
    echo ""
fi

# ── Deploy to cache ─────────────────────────────────────────────────────────

exec bash "$SCRIPT_DIR/install-plugin.sh" --cache
