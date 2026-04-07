"""
ChainSight – Agentic Wallet
On-chain identity for ChainSight on X Layer Testnet.

Role       : Receive micro-tips for premium insights; sign data payloads.
Network    : X Layer Testnet (Chain ID 195)
Key mgmt   : Private key loaded from ENV — never hardcoded.
Log file   : wallet_activity.log (for judge verification)
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("chainsight.wallet")

# ─────────────────────────────────────────────
# X Layer Testnet Config
# ─────────────────────────────────────────────
XLAYER_TESTNET_RPC   = os.getenv("XLAYER_RPC_URL", "https://testrpc.xlayer.tech")
XLAYER_TESTNET_ID    = 195
WALLET_LOG_PATH      = Path(os.getenv("WALLET_LOG_PATH", "wallet_activity.log"))

# Known deployed address (replace after real deployment)
DEPLOYED_ADDRESS     = os.getenv(
    "CHAINSIGHT_WALLET_ADDRESS",
    "0x0000000000000000000000000000000000000000"   # placeholder
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─────────────────────────────────────────────
# Wallet Manager
# ─────────────────────────────────────────────
class AgenticWallet:
    """
    ChainSight's on-chain identity on X Layer Testnet.

    Permissions:
      - RECEIVE tips / payments
      - SIGN data payloads (EIP-191 personal_sign)
      - READ balance
      ✗ Does NOT auto-spend funds without explicit user approval.
    """

    def __init__(self):
        self.address        = DEPLOYED_ADDRESS
        self._private_key   = os.getenv("CHAINSIGHT_PRIVATE_KEY")  # never log this
        self._web3_client   = None
        self._mock_balance  = 0.05   # testnet OKB
        self._tip_log: list[dict] = []
        self._log_file = WALLET_LOG_PATH
        self._init_log()

    # ── Setup ───────────────────────────────

    def _init_log(self) -> None:
        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        if not self._log_file.exists():
            self._log_file.write_text(
                json.dumps({
                    "chainsight_wallet": self.address,
                    "network":           "X Layer Testnet",
                    "chain_id":          XLAYER_TESTNET_ID,
                    "role":              "Agentic data-insight service wallet",
                    "permissions":       ["receive_tips", "sign_data", "read_balance"],
                    "created":           _now_iso(),
                    "activity":          [],
                }, indent=2)
            )

    def _log_activity(self, event: dict) -> None:
        try:
            state = json.loads(self._log_file.read_text())
            state.setdefault("activity", []).append({**event, "timestamp": _now_iso()})
            self._log_file.write_text(json.dumps(state, indent=2))
        except Exception as exc:
            logger.warning("Failed to write wallet log: %s", exc)

    def _try_load_web3(self) -> bool:
        """Lazy-load web3.py if available."""
        if self._web3_client is not None:
            return True
        try:
            from web3 import Web3
            self._web3_client = Web3(Web3.HTTPProvider(XLAYER_TESTNET_RPC))
            return self._web3_client.is_connected()
        except ImportError:
            logger.info("web3.py not installed — using mock wallet mode")
            return False
        except Exception as exc:
            logger.warning("Web3 connection failed: %s", exc)
            return False

    # ── Public API ──────────────────────────

    def get_info(self) -> dict:
        """Return public wallet metadata (safe to display)."""
        return {
            "address":    self.address,
            "network":    "X Layer Testnet",
            "chain_id":   XLAYER_TESTNET_ID,
            "rpc":        XLAYER_TESTNET_RPC,
            "role":       "ChainSight Agentic Wallet — receives tips, signs insights",
            "explorer":   f"https://www.okx.com/explorer/xlayer-test/address/{self.address}",
        }

    async def get_balance(self) -> dict:
        """Fetch OKB balance on X Layer Testnet."""
        if self._try_load_web3():
            try:
                from web3 import Web3
                w3 = self._web3_client
                bal_wei = w3.eth.get_balance(
                    Web3.to_checksum_address(self.address)
                )
                bal_eth = w3.from_wei(bal_wei, "ether")
                result = {
                    "address":  self.address,
                    "balance":  float(bal_eth),
                    "currency": "OKB",
                    "network":  "X Layer Testnet",
                    "source":   "live",
                }
                self._log_activity({"type": "balance_check", "balance": float(bal_eth)})
                return result
            except Exception as exc:
                logger.warning("Live balance fetch failed: %s", exc)

        # Mock fallback
        result = {
            "address":  self.address,
            "balance":  self._mock_balance,
            "currency": "OKB",
            "network":  "X Layer Testnet (mock)",
            "source":   "mock",
        }
        self._log_activity({"type": "balance_check_mock", "balance": self._mock_balance})
        return result

    async def receive_tip(self, amount: float, currency: str = "OKB") -> dict:
        """
        Record an incoming tip/payment for a premium insight.
        In real deployment: listens for Transfer events on X Layer.
        """
        if amount <= 0:
            return {"status": "error", "message": "Tip amount must be positive"}

        self._mock_balance += amount
        record = {
            "type":     "tip_received",
            "amount":   amount,
            "currency": currency,
            "from":     "external",
            "status":   "confirmed_mock",
        }
        self._tip_log.append(record)
        self._log_activity(record)

        logger.info("Tip received: %s %s", amount, currency)
        return {
            "status":  "received",
            "amount":  amount,
            "currency": currency,
            "new_balance": self._mock_balance,
            "tx_hash": f"0x{'0' * 62}mock",   # placeholder
        }

    def sign_data_payload(self, payload: dict) -> dict:
        """
        Sign an insight payload with EIP-191 personal_sign.
        Provides tamper-proof attestation that the data came from ChainSight.
        """
        if not payload:
            return {"status": "error", "message": "Empty payload"}

        payload_str = json.dumps(payload, sort_keys=True)

        if self._try_load_web3() and self._private_key:
            try:
                from eth_account import Account
                from eth_account.messages import encode_defunct
                message   = encode_defunct(text=payload_str)
                signed    = Account.sign_message(message, private_key=self._private_key)
                signature = signed.signature.hex()
                logger.info("Payload signed: %s...", signature[:20])
                self._log_activity({"type": "sign_payload", "signature_prefix": signature[:20]})
                return {
                    "status":    "signed",
                    "signature": signature,
                    "signer":    self.address,
                    "method":    "EIP-191",
                }
            except Exception as exc:
                logger.warning("Live signing failed: %s", exc)

        # Mock deterministic signature (hash-based, NOT cryptographically valid)
        fake_sig = "0x" + hashlib.sha256(payload_str.encode()).hexdigest() * 2
        self._log_activity({"type": "sign_payload_mock"})
        return {
            "status":    "signed_mock",
            "signature": fake_sig[:132],
            "signer":    self.address,
            "method":    "EIP-191 (mock mode)",
            "note":      "Mock signature for demo — not cryptographically valid",
        }

    def get_tip_history(self) -> list[dict]:
        """Return all recorded tips this session."""
        return list(self._tip_log)

    async def fund_from_faucet(self) -> dict:
        """Helper: return faucet URL for X Layer Testnet funding."""
        faucet_url = "https://www.okx.com/xlayer/faucet"
        self._log_activity({"type": "faucet_requested"})
        return {
            "status":       "info",
            "faucet_url":   faucet_url,
            "address":      self.address,
            "instructions": (
                f"Visit {faucet_url}, paste your address "
                f"({self.address}), and request test OKB."
            ),
        }