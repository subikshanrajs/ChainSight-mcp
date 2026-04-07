"""
ChainSight – On-Chain Data Layer
Fetches X Layer + Uniswap V3 pool metrics.

Onchain OS Integration: Uses OS-standard data indexing & caching pattern.
Uniswap Integration:   Mirrors Uniswap pool-analytics skill architecture.

Two modes:
  mock_mode=True  → static test data (safe for demos, no API key needed)
  mock_mode=False → live GraphQL queries to The Graph / X Layer RPC
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

logger = logging.getLogger("chainsight.onchain")

# ─────────────────────────────────────────────
# X Layer Chain Config
# ─────────────────────────────────────────────
XLAYER_CHAIN_ID    = 196          # X Layer Mainnet
XLAYER_TESTNET_ID  = 195          # X Layer Testnet
XLAYER_RPC_MAIN    = "https://rpc.xlayer.tech"
XLAYER_RPC_TEST    = "https://testrpc.xlayer.tech"

# Uniswap V3 Subgraph – The Graph (replace with X Layer-specific endpoint when live)
UNISWAP_SUBGRAPH = (
    "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"
)

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─────────────────────────────────────────────
# Mock Pool Data  (3-4 representative X Layer pools)
# ─────────────────────────────────────────────
MOCK_POOLS: dict[str, dict] = {
    "USDC/ETH": {
        "pool_address":  "0xAbC1230000000000000000000000000000000001",
        "token0":        "USDC",
        "token1":        "ETH",
        "fee_tier":      "0.05%",
        "apy":           7.2,
        "tvl_usd":       4_800_000,
        "volume_24h":    320_000,
        "price_token1":  3_210.50,   # ETH/USD
        "liquidity":     9_500_000,
        "tick_spacing":  10,
        "whale_alert":   False,
        "recent_large_tx": None,
        "hourly_vol_change": 0.03,
        "subgraph_url":  f"{UNISWAP_SUBGRAPH}",
        "last_updated":  _now(),
    },
    "USDT/OKB": {
        "pool_address":  "0xAbC1230000000000000000000000000000000002",
        "token0":        "USDT",
        "token1":        "OKB",
        "fee_tier":      "0.3%",
        "apy":           14.8,
        "tvl_usd":       1_200_000,
        "volume_24h":    87_000,
        "price_token1":  46.30,      # OKB/USD
        "liquidity":     2_100_000,
        "tick_spacing":  60,
        "whale_alert":   True,
        "recent_large_tx": {"amount_usd": 50_000, "type": "withdraw", "age_minutes": 12},
        "hourly_vol_change": 0.18,
        "subgraph_url":  f"{UNISWAP_SUBGRAPH}",
        "last_updated":  _now(),
    },
    "ETH/OKB": {
        "pool_address":  "0xAbC1230000000000000000000000000000000003",
        "token0":        "ETH",
        "token1":        "OKB",
        "fee_tier":      "0.3%",
        "apy":           11.1,
        "tvl_usd":       2_700_000,
        "volume_24h":    195_000,
        "price_token1":  46.30,
        "liquidity":     5_400_000,
        "tick_spacing":  60,
        "whale_alert":   False,
        "recent_large_tx": None,
        "hourly_vol_change": 0.07,
        "subgraph_url":  f"{UNISWAP_SUBGRAPH}",
        "last_updated":  _now(),
    },
    "USDC/USDT": {
        "pool_address":  "0xAbC1230000000000000000000000000000000004",
        "token0":        "USDC",
        "token1":        "USDT",
        "fee_tier":      "0.01%",
        "apy":           2.9,
        "tvl_usd":       9_100_000,
        "volume_24h":    1_500_000,
        "price_token1":  1.00,
        "liquidity":     18_000_000,
        "tick_spacing":  1,
        "whale_alert":   False,
        "recent_large_tx": None,
        "hourly_vol_change": 0.01,
        "subgraph_url":  f"{UNISWAP_SUBGRAPH}",
        "last_updated":  _now(),
    },
}

# Mock token prices (USD) for swap simulation
MOCK_PRICES: dict[str, float] = {
    "USDC":  1.00,
    "USDT":  1.00,
    "ETH":   3_210.50,
    "OKB":   46.30,
    "WBTC":  67_000.00,
}




# ─────────────────────────────────────────────
# GraphQL Query Templates (Uniswap V3 Subgraph)
# ─────────────────────────────────────────────
POOL_QUERY = """
query GetPool($token0: String!, $token1: String!) {
  pools(
    where: {
      token0_: {symbol: $token0},
      token1_: {symbol: $token1}
    }
    orderBy: totalValueLockedUSD
    orderDirection: desc
    first: 1
  ) {
    id
    feeTier
    totalValueLockedUSD
    volumeUSD
    token0Price
    token1Price
    liquidity
    poolDayData(first: 7, orderBy: date, orderDirection: desc) {
      date
      volumeUSD
      feesUSD
      tvlUSD
    }
  }
}
"""

ALL_POOLS_QUERY = """
query TopPools {
  pools(
    orderBy: totalValueLockedUSD
    orderDirection: desc
    first: 20
  ) {
    id
    token0 { symbol }
    token1 { symbol }
    feeTier
    totalValueLockedUSD
    volumeUSD
    liquidity
  }
}
"""


# ─────────────────────────────────────────────
# Data Fetcher
# ─────────────────────────────────────────────
class OnChainDataFetcher:
    """
    Onchain OS Integration: Uses OS-standard data indexing & caching pattern.
    Provides a unified interface over mock and live data sources.
    """

    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode
        self._cache: dict[str, tuple[float, dict]] = {}   # key → (timestamp, data)
        self._cache_ttl = 30  # seconds

    # ── Internal helpers ────────────────────

    def _cache_get(self, key: str) -> Optional[dict]:
        if key in self._cache:
            ts, data = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                return data
        return None

    def _cache_set(self, key: str, data: dict) -> None:
        self._cache[key] = (time.time(), data)

    async def _gql(self, query: str, variables: dict | None = None) -> Optional[dict]:
        """Execute a GraphQL query against the Uniswap V3 subgraph."""
        if not AIOHTTP_AVAILABLE:
            logger.error("aiohttp not installed. Run: pip install aiohttp")
            return None

        payload = {"query": query, "variables": variables or {}}
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        UNISWAP_SUBGRAPH,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        if resp.status == 200:
                            body = await resp.json()
                            return body.get("data")
                        logger.warning("Subgraph HTTP %s (attempt %d)", resp.status, attempt + 1)
            except asyncio.TimeoutError:
                logger.warning("Subgraph timeout (attempt %d)", attempt + 1)
            except Exception as exc:
                logger.warning("Subgraph error: %s (attempt %d)", exc, attempt + 1)
            await asyncio.sleep(1.5 ** attempt)
        return None

    def _calculate_apy(self, pool_day_data: list[dict], tvl: float) -> float:
        """Uniswap Integration: pool-analytics APY estimation from 7d fees."""
        if not pool_day_data or tvl <= 0:
            return 0.0
        daily_fees = sum(float(d.get("feesUSD", 0)) for d in pool_day_data)
        avg_daily  = daily_fees / len(pool_day_data)
        return round((avg_daily * 365 / tvl) * 100, 2)

    # ── Public API ──────────────────────────

    async def fetch_pool_metrics(self, pool_name: str) -> Optional[dict]:
        """
        Onchain OS Integration: OS-standard data indexing & caching pattern.
        Returns pool metrics for a given pair (e.g. 'USDC/ETH').
        """
        cache_key = f"pool:{pool_name}"
        cached = self._cache_get(cache_key)
        if cached:
            logger.debug("Cache hit: %s", cache_key)
            return cached

        if self.mock_mode:
            result = MOCK_POOLS.get(pool_name)
            if result:
                self._cache_set(cache_key, result)
            return result

        # Live mode: GraphQL query
        tokens = pool_name.split("/")
        if len(tokens) != 2:
            return None

        token0, token1 = tokens
        data = await self._gql(POOL_QUERY, {"token0": token0, "token1": token1})

        if not data or not data.get("pools"):
            # Try reversed order
            data = await self._gql(POOL_QUERY, {"token0": token1, "token1": token0})

        if not data or not data.get("pools"):
            return None

        raw = data["pools"][0]
        tvl  = float(raw.get("totalValueLockedUSD", 0))
        vol  = float(raw.get("volumeUSD", 0))
        apy  = self._calculate_apy(raw.get("poolDayData", []), tvl)

        result = {
            "pool_address":     raw["id"],
            "token0":           token0,
            "token1":           token1,
            "fee_tier":         f"{int(raw['feeTier']) / 10000:.2f}%",
            "apy":              apy,
            "tvl_usd":          tvl,
            "volume_24h":       vol / 7,  # rough daily average
            "price_token1":     float(raw.get("token1Price", 0)),
            "liquidity":        float(raw.get("liquidity", 0)),
            "whale_alert":      False,
            "recent_large_tx":  None,
            "hourly_vol_change": 0.05,
            "subgraph_url":     UNISWAP_SUBGRAPH,
            "last_updated":     _now(),
        }

        self._cache_set(cache_key, result)
        return result

    async def fetch_all_pools(self) -> dict[str, dict]:
        """Return all tracked pools (mock or live)."""
        if self.mock_mode:
            return dict(MOCK_POOLS)

        data = await self._gql(ALL_POOLS_QUERY)
        if not data or not data.get("pools"):
            logger.warning("Live pool fetch failed; falling back to mock")
            return dict(MOCK_POOLS)

        result = {}
        for raw in data["pools"]:
            t0    = raw["token0"]["symbol"]
            t1    = raw["token1"]["symbol"]
            name  = f"{t0}/{t1}"
            tvl   = float(raw.get("totalValueLockedUSD", 0))
            result[name] = {
                "pool_address":     raw["id"],
                "token0":           t0,
                "token1":           t1,
                "fee_tier":         f"{int(raw['feeTier']) / 10000:.2f}%",
                "apy":              0.0,   # needs day data for full calc
                "tvl_usd":          tvl,
                "volume_24h":       float(raw.get("volumeUSD", 0)) / 7,
                "liquidity":        float(raw.get("liquidity", 0)),
                "whale_alert":      False,
                "hourly_vol_change": 0.05,
                "last_updated":     _now(),
            }

        return result or dict(MOCK_POOLS)

    async def calculate_slippage(
        self, token_from: str, token_to: str, amount_usd: float
    ) -> Optional[dict]:
        """
        Uniswap Integration: pool-analytics liquidity depth & slippage model.
        Uses constant-product AMM approximation: slippage ≈ amount / (2 × liquidity).
        """
        pair_key = f"{token_from}/{token_to}"
        alt_key  = f"{token_to}/{token_from}"

        metrics = await self.fetch_pool_metrics(pair_key)
        if metrics is None:
            metrics = await self.fetch_pool_metrics(alt_key)
        if metrics is None:
            # Best-effort: derive from individual token prices
            p_from = MOCK_PRICES.get(token_from)
            p_to   = MOCK_PRICES.get(token_to)
            if p_from is None or p_to is None:
                return None

            rate    = p_from / p_to
            output  = (amount_usd / p_from) * rate * p_to / p_to
            # Minimal slippage guess for unknown pairs
            slippage = min(0.5, (amount_usd / 1_000_000) * 100)

            return {
                "expected_output": output,
                "slippage":        slippage,
                "price_impact":    slippage * 0.8,
                "gas_gwei":        25,
                "route":           f"Direct: {token_from} → {token_to}",
                "fee_tier":        "0.3%",
                "pool_ref":        "",
            }

        # AMM-based slippage calculation
        liquidity_usd = metrics["tvl_usd"]
        fee_str = metrics.get("fee_tier", "0.3%")
        fee_pct = float(fee_str.replace("%", "")) / 100

        # Price impact ≈ trade_size / (2 × sqrt(liquidity)) — simplified constant-product model
        price_impact = (amount_usd / max(liquidity_usd, 1)) * 100
        slippage     = price_impact + fee_pct * 100

        # Estimate output
        p_from  = MOCK_PRICES.get(token_from, 1.0)
        p_to    = MOCK_PRICES.get(token_to,   1.0)
        output  = (amount_usd / p_from) * (p_from / p_to) * (1 - fee_pct - price_impact / 100)

        return {
            "expected_output": max(output, 0),
            "slippage":        round(slippage, 4),
            "price_impact":    round(price_impact, 4),
            "gas_gwei":        20 if "USDC/USDT" in [pair_key, alt_key] else 35,
            "route":           f"Uniswap V3: {token_from} → {token_to} ({fee_str} pool)",
            "fee_tier":        fee_str,
            "pool_ref":        metrics.get("subgraph_url", ""),
        }

    async def detect_whale_movement(self, pool_name: str) -> dict:
        """
        Onchain OS Integration: large-transaction detection aligned with
        OS anomaly-detection pattern.
        """
        metrics = await self.fetch_pool_metrics(pool_name)
        if metrics is None:
            return {"detected": False, "details": None}

        if metrics.get("whale_alert") and metrics.get("recent_large_tx"):
            tx = metrics["recent_large_tx"]
            return {
                "detected":       True,
                "amount_usd":     tx["amount_usd"],
                "type":           tx["type"],           # 'withdraw' | 'deposit'
                "age_minutes":    tx["age_minutes"],
                "risk_flag":      tx["type"] == "withdraw",
                "message": (
                    f"⚠️ Large {tx['type']} of "
                    f"${tx['amount_usd']:,} detected {tx['age_minutes']} min ago."
                ),
            }

        return {"detected": False, "details": None}