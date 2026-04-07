#!/usr/bin/env bash
# ─────────────────────────────────────────────
# ChainSight – MCP Server Launcher
# ─────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║    ChainSight MCP Server Launcher    ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Load .env if present
if [ -f "$ROOT_DIR/.env" ]; then
    echo "📦  Loading environment from .env…"
    export $(grep -v '^#' "$ROOT_DIR/.env" | xargs)
fi

MOCK_MODE=${CHAINSIGHT_MOCK_MODE:-true}
echo "🧪  Mock mode: $MOCK_MODE"

# Check Python
command -v python3 >/dev/null 2>&1 || { echo "❌  Python 3 required"; exit 1; }

# Check dependencies
echo "🔍  Checking dependencies…"
cd "$ROOT_DIR"
pip show mcp >/dev/null 2>&1 || { echo "📦  Installing dependencies…"; pip install -e ".[dev]" -q; }

echo ""
echo "🚀  Starting ChainSight MCP Server (stdio mode)…"
echo "    Tools exposed:"
echo "      - get_pool_health"
echo "      - analyze_swap_impact"
echo "      - get_beginner_recommendation"
echo ""
echo "    Connect with any MCP-compatible agent."
echo "    Press Ctrl+C to stop."
echo ""

PYTHONPATH="$ROOT_DIR/src:$PYTHONPATH" \
CHAINSIGHT_MOCK_MODE="$MOCK_MODE" \
python3 "$ROOT_DIR/src/mcp_server.py"