#!/usr/bin/env bash
# ─────────────────────────────────────────────
# ChainSight – Agentic Wallet Setup Helper
# Generates a fresh EOA, funds it from X Layer
# Testnet faucet, and writes .env
# ─────────────────────────────────────────────
set -e

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   ChainSight Agentic Wallet Setup    ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Check Python
command -v python3 >/dev/null 2>&1 || { echo "❌  Python 3 required"; exit 1; }

# Check / install eth_account
python3 -c "import eth_account" 2>/dev/null || pip install eth-account -q

echo "🔑  Generating new EOA on X Layer Testnet…"
python3 - <<'PYEOF'
import json, os
from eth_account import Account

Account.enable_unaudited_hdwallet_features()
acct = Account.create()
addr = acct.address
pk   = acct.key.hex()

print(f"\n✅  Address    : {addr}")
print(f"🔐  Private key: {pk}")
print(f"\n⚠️  KEEP YOUR PRIVATE KEY SAFE — DO NOT SHARE IT.\n")

# Write to .env if it exists, else .env.local
env_path = ".env" if os.path.exists(".env") else ".env.local"
lines = []
if os.path.exists(env_path):
    with open(env_path) as f:
        lines = f.readlines()

# Update or append the two keys
keys_to_set = {
    "CHAINSIGHT_WALLET_ADDRESS": addr,
    "CHAINSIGHT_PRIVATE_KEY":    pk,
}

existing_keys = {l.split("=")[0].strip() for l in lines if "=" in l}
new_lines = []
for line in lines:
    k = line.split("=")[0].strip()
    if k in keys_to_set:
        new_lines.append(f"{k}={keys_to_set.pop(k)}\n")
    else:
        new_lines.append(line)
for k, v in keys_to_set.items():
    new_lines.append(f"{k}={v}\n")

with open(env_path, "w") as f:
    f.writelines(new_lines)

print(f"💾  Written to {env_path}")
PYEOF

echo ""
echo "💧  Fund your wallet with test OKB:"
echo "    👉  https://www.okx.com/xlayer/faucet"
echo ""
echo "    Copy your address from above and paste it on the faucet page."
echo ""
echo "🔗  View your wallet:"
echo "    👉  https://www.okx.com/explorer/xlayer-test"
echo ""
echo "✅  Done! Run the MCP server next:"
echo "    bash scripts/run_mcp_server.sh"
echo ""