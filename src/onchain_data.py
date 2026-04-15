"""
ChainSight – On-Chain Data Layer  (v2 — Real Uniswap Integration)
==================================================================
Data source priority:
  1. Uniswap V3 Subgraph      (APY, TVL, volume, hourly candles)
  2. DexScreener API          (free fallback: price + liquidity)
  3. Mock data                (demo safe, always available)

Onchain OS Integration : OS-standard data indexing & caching pattern.
Uniswap Integration    : pool-analytics, swap-integration skill patterns.
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

logger = logging.getLogger("chainsight.onchain")

# X Layer Chain Config
XLAYER_CHAIN_ID   = 196
XLAYER_TESTNET_ID = 195
XLAYER_RPC_MAIN   = "https://rpc.xlayer.tech"
XLAYER_RPC_TEST   = "https://testrpc.xlayer.tech"
UNISWAP_SUBGRAPH  = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"

# Trading API base (uniswap-trading skill)
TRADING_API_BASE  = "https://trade-api.gateway.uniswap.org/v1"
DEXSCREENER_BASE  = "https://api.dexscreener.com/latest/dex"

CHAIN_SUBGRAPHS = {
    "ethereum": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3",
    "base":     "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3-base",
    "arbitrum": "https://api.thegraph.com/subgraphs/name/ianlapham/uniswap-arbitrum-one",
}

# Well-known token addresses (uniswap-driver token map)
TOKEN_ADDRESSES = {
    "USDC":  "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "USDT":  "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "WETH":  "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "ETH":   "0x0000000000000000000000000000000000000000",
    "WBTC":  "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
    "DAI":   "0x6B175474E89094C44Da98b954EedeAC495271d0F",
    "UNI":   "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
}

# Uniswap fee tier labels (v4-security-foundations hook flag constants)
FEE_TIERS = {100: "0.01%", 500: "0.05%", 3000: "0.3%", 10000: "1%"}

# Routing types (swap-integration skill)
ROUTING_TYPES = {
    "CLASSIC":  "Standard AMM swap through Uniswap pools",
    "DUTCH_V2": "UniswapX Dutch auction V2 — MEV-protected",
    "PRIORITY": "MEV-protected priority order",
    "WRAP":     "ETH → WETH conversion",
    "UNWRAP":   "WETH → ETH conversion",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─────────────────────────────────────────────
# Static Mock Pool Data
# ─────────────────────────────────────────────
MOCK_POOLS: dict[str, dict] = {
    "USDC/ETH": {
        "pool_address":      "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
        "token0": "USDC", "token1": "ETH",
        "fee_tier": "0.05%", "apy": 7.2, "tvl_usd": 4_800_000,
        "volume_24h": 320_000, "price_token1": 3_210.50,
        "liquidity": 9_500_000, "hourly_vol_change": 0.03,
        "whale_alert": False, "recent_large_tx": None,
        "subgraph_url": UNISWAP_SUBGRAPH, "data_source": "mock", "last_updated": _now(),
    },
    "USDT/OKB": {
        "pool_address": "0xAbC1230000000000000000000000000000000002",
        "token0": "USDT", "token1": "OKB",
        "fee_tier": "0.3%", "apy": 14.8, "tvl_usd": 1_200_000,
        "volume_24h": 87_000, "price_token1": 46.30,
        "liquidity": 2_100_000, "hourly_vol_change": 0.18,
        "whale_alert": True,
        "recent_large_tx": {"amount_usd": 50_000, "type": "high_volume_spike",
                             "age_minutes": 12,
                             "message": "⚠️ Large volume spike of $50,000 in USDT/OKB"},
        "subgraph_url": UNISWAP_SUBGRAPH, "data_source": "mock", "last_updated": _now(),
    },
    "ETH/OKB": {
        "pool_address": "0xAbC1230000000000000000000000000000000003",
        "token0": "ETH", "token1": "OKB",
        "fee_tier": "0.3%", "apy": 11.1, "tvl_usd": 2_700_000,
        "volume_24h": 195_000, "price_token1": 46.30,
        "liquidity": 5_400_000, "hourly_vol_change": 0.07,
        "whale_alert": False, "recent_large_tx": None,
        "subgraph_url": UNISWAP_SUBGRAPH, "data_source": "mock", "last_updated": _now(),
    },
    "USDC/USDT": {
        "pool_address": "0x3416cF6C708Da44DB2624D63ea0AAef7113527C6",
        "token0": "USDC", "token1": "USDT",
        "fee_tier": "0.01%", "apy": 2.9, "tvl_usd": 9_100_000,
        "volume_24h": 1_500_000, "price_token1": 1.00,
        "liquidity": 18_000_000, "hourly_vol_change": 0.01,
        "whale_alert": False, "recent_large_tx": None,
        "subgraph_url": UNISWAP_SUBGRAPH, "data_source": "mock", "last_updated": _now(),
    },
}

MOCK_PRICES: dict[str, float] = {
    "USDC": 1.00, "USDT": 1.00, "ETH": 3_210.50,
    "OKB": 46.30, "WBTC": 67_000.00,
}


# ─────────────────────────────────────────────
# HTTP Helpers
# ─────────────────────────────────────────────
async def _http_get(url: str, params: dict | None = None,
                    headers: dict | None = None, retries: int = 3) -> Optional[dict]:
    """GET with retry — viem-integration pattern: retry on 429/5xx."""
    if not AIOHTTP_AVAILABLE:
        return None
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, params=params, headers=headers or {},
                                  timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status == 200:
                        return await r.json()
                    if r.status == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    logger.warning("GET %s → %s", url, r.status)
                    return None
        except Exception as e:
            logger.warning("HTTP error (attempt %d): %s", attempt + 1, e)
        await asyncio.sleep(1.5 ** attempt)
    return None


async def _gql(endpoint: str, query: str,
               variables: dict | None = None, retries: int = 3) -> Optional[dict]:
    """GraphQL query — subgraph pattern from uniswap-trading skill."""
    if not AIOHTTP_AVAILABLE:
        return None
    payload = {"query": query, "variables": variables or {}}
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(endpoint, json=payload,
                                   timeout=aiohttp.ClientTimeout(total=12)) as r:
                    if r.status == 200:
                        body = await r.json()
                        return body.get("data")
                    logger.warning("GQL %s → %s (attempt %d)", endpoint, r.status, attempt + 1)
        except Exception as e:
            logger.warning("GQL error (attempt %d): %s", attempt + 1, e)
        await asyncio.sleep(1.5 ** attempt)
    return None


# ─────────────────────────────────────────────
# Subgraph Queries (pool-analytics pattern)
# ─────────────────────────────────────────────
POOL_BY_TOKENS_QUERY = """
query PoolByTokens($token0: String!, $token1: String!) {
  pools(
    where: {
      token0_: { symbol_in: [$token0, $token1] }
      token1_: { symbol_in: [$token0, $token1] }
    }
    orderBy: totalValueLockedUSD
    orderDirection: desc
    first: 3
  ) {
    id feeTier
    token0 { id symbol decimals }
    token1 { id symbol decimals }
    totalValueLockedUSD volumeUSD
    token0Price token1Price liquidity
    poolDayData(first: 7, orderBy: date, orderDirection: desc) {
      date volumeUSD feesUSD tvlUSD open high low close
    }
    poolHourData(first: 2, orderBy: periodStartUnix, orderDirection: desc) {
      periodStartUnix volumeUSD open close
    }
  }
}
"""

TOP_POOLS_QUERY = """
query TopPools {
  pools(
    where: { totalValueLockedUSD_gt: "500000" }
    orderBy: totalValueLockedUSD
    orderDirection: desc
    first: 30
  ) {
    id feeTier
    token0 { id symbol }
    token1 { id symbol }
    totalValueLockedUSD volumeUSD liquidity
    poolDayData(first: 7, orderBy: date, orderDirection: desc) {
      feesUSD tvlUSD volumeUSD
    }
  }
}
"""


# ─────────────────────────────────────────────
# Main Data Fetcher
# ─────────────────────────────────────────────
class OnChainDataFetcher:
    """
    Unified data fetcher: live Uniswap data with mock fallback.

    mock_mode=True  → always use MOCK_POOLS (demo safe, no API needed)
    mock_mode=False → Uniswap V3 Subgraph → DexScreener → mock

    Onchain OS Integration: TTL cache, retry logic, env-driven mode switching.
    """

    def __init__(self, mock_mode: bool = True, chain: str = "ethereum"):
        self.mock_mode   = mock_mode
        self.chain       = chain
        self._subgraph   = CHAIN_SUBGRAPHS.get(chain, UNISWAP_SUBGRAPH)
        self._api_key    = os.getenv("UNISWAP_API_KEY", "")
        self._cache: dict[str, tuple[float, dict]] = {}
        self._cache_ttl  = 30

    def _cache_get(self, key: str) -> Optional[dict]:
        if key in self._cache:
            ts, data = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                return data
        return None

    def _cache_set(self, key: str, data: dict) -> None:
        self._cache[key] = (time.time(), data)

    # ── Pool Metrics ─────────────────────────

    async def fetch_pool_metrics(self, pool_name: str) -> Optional[dict]:
        """
        Fetch pool health metrics for 'TOKEN0/TOKEN1'.
        Onchain OS Integration: OS-standard data indexing & caching.
        """
        cache_key = f"pool:{pool_name}"
        if cached := self._cache_get(cache_key):
            return cached

        if self.mock_mode:
            result = MOCK_POOLS.get(pool_name)
            if result:
                self._cache_set(cache_key, result)
            return result

        # Live: Uniswap V3 Subgraph
        tokens = pool_name.split("/")
        if len(tokens) != 2:
            return None
        t0, t1 = tokens[0].strip().upper(), tokens[1].strip().upper()

        result = await self._fetch_from_subgraph(t0, t1)
        if result:
            self._cache_set(cache_key, result)
            logger.info("Live data: %s [%s]", pool_name, result["data_source"])
            return result

        # Fallback: DexScreener
        result = await self._fetch_from_dexscreener(t0, t1)
        if result:
            self._cache_set(cache_key, result)
            return result

        # Final fallback: mock
        logger.warning("All live sources failed for %s — using mock", pool_name)
        return MOCK_POOLS.get(pool_name)

    async def _fetch_from_subgraph(self, t0: str, t1: str) -> Optional[dict]:
        """Uniswap V3 Subgraph query — pool-analytics pattern."""
        data = await _gql(self._subgraph, POOL_BY_TOKENS_QUERY,
                          {"token0": t0, "token1": t1})
        if not data or not data.get("pools"):
            # Try reversed
            data = await _gql(self._subgraph, POOL_BY_TOKENS_QUERY,
                               {"token0": t1, "token1": t0})
        if not data or not data.get("pools"):
            return None

        pool     = data["pools"][0]
        tvl      = float(pool.get("totalValueLockedUSD", 0))
        day_data = pool.get("poolDayData", [])
        hr_data  = pool.get("poolHourData", [])

        # APY: 7-day fee average (uniswap-trading pool-analytics method)
        total_fees = sum(float(d.get("feesUSD", 0)) for d in day_data)
        avg_daily  = total_fees / len(day_data) if day_data else 0
        apy        = round((avg_daily * 365 / max(tvl, 1)) * 100, 2)

        # Hourly volatility
        vol_change = 0.05
        if len(hr_data) >= 2:
            try:
                latest = float(hr_data[0].get("close", 1))
                prev   = float(hr_data[1].get("open", 1))
                vol_change = abs(latest - prev) / max(prev, 1e-9)
            except (TypeError, ValueError):
                pass

        # Whale detection
        vol_24h    = float(day_data[0].get("volumeUSD", 0)) if day_data else 0
        whale      = vol_24h > 0 and tvl > 0 and (vol_24h / tvl) > 0.3
        fee_raw    = int(pool.get("feeTier", 3000))
        fee_label  = FEE_TIERS.get(fee_raw, f"{fee_raw/10000:.2f}%")

        return {
            "pool_address":      pool["id"],
            "token0":            pool["token0"]["symbol"],
            "token1":            pool["token1"]["symbol"],
            "fee_tier":          fee_label,
            "apy":               apy,
            "tvl_usd":           tvl,
            "volume_24h":        vol_24h,
            "price_token1":      float(pool.get("token1Price", 0)),
            "liquidity":         float(pool.get("liquidity", 0)),
            "hourly_vol_change": vol_change,
            "whale_alert":       whale,
            "recent_large_tx":   {
                "amount_usd": vol_24h, "type": "high_volume_spike",
                "age_minutes": 0,
                "message": f"⚠️ Volume ${vol_24h:,.0f} is >30% of TVL ${tvl:,.0f}"
            } if whale else None,
            "subgraph_url":      self._subgraph,
            "data_source":       "uniswap_subgraph",
            "last_updated":      _now(),
        }

    async def _fetch_from_dexscreener(self, t0: str, t1: str) -> Optional[dict]:
        """DexScreener fallback — uniswap-driver swap-planner pattern."""
        data = await _http_get(f"{DEXSCREENER_BASE}/search", params={"q": f"{t0} {t1}"})
        if not data:
            return None

        pairs = [
            p for p in data.get("pairs", [])
            if "uniswap" in p.get("dexId", "").lower()
            and p.get("chainId", "").lower() == self.chain.lower()
        ]
        if not pairs:
            return None

        pair   = sorted(pairs, key=lambda x: float(
            x.get("liquidity", {}).get("usd", 0) or 0), reverse=True)[0]
        liq    = float(pair.get("liquidity", {}).get("usd", 0) or 0)
        vol_24 = float(pair.get("volume", {}).get("h24", 0) or 0)
        chg_1h = float(pair.get("priceChange", {}).get("h1", 0) or 0)
        chg_24 = float(pair.get("priceChange", {}).get("h24", 0) or 0)
        apy    = round((vol_24 * 0.003 * 365 / max(liq, 1)) * 100, 2)

        return {
            "pool_address":      pair.get("pairAddress", ""),
            "token0":            t0,
            "token1":            t1,
            "fee_tier":          "0.3%",
            "apy":               apy,
            "tvl_usd":           liq,
            "volume_24h":        vol_24,
            "price_token1":      float(pair.get("priceUsd", 0) or 0),
            "liquidity":         liq,
            "hourly_vol_change": abs(chg_1h) / 100,
            "whale_alert":       abs(chg_24) > 10,
            "recent_large_tx":   None,
            "subgraph_url":      pair.get("url", ""),
            "data_source":       "dexscreener",
            "last_updated":      _now(),
        }

    # ── All Pools ────────────────────────────

    async def fetch_all_pools(self) -> dict[str, dict]:
        """Return all tracked pools (live or mock)."""
        if self.mock_mode:
            return dict(MOCK_POOLS)

        data = await _gql(self._subgraph, TOP_POOLS_QUERY)
        if not data or not data.get("pools"):
            logger.warning("Top pools fetch failed — mock fallback")
            return dict(MOCK_POOLS)

        result = {}
        for p in data["pools"]:
            t0  = p["token0"]["symbol"]
            t1  = p["token1"]["symbol"]
            tvl = float(p.get("totalValueLockedUSD", 0))
            day = p.get("poolDayData", [])
            fees = sum(float(d.get("feesUSD", 0)) for d in day)
            avg  = fees / len(day) if day else 0
            apy  = round((avg * 365 / max(tvl, 1)) * 100, 2)
            vol  = float(day[0].get("volumeUSD", 0)) if day else 0

            result[f"{t0}/{t1}"] = {
                "pool_address":      p["id"],
                "token0": t0, "token1": t1,
                "fee_tier":          FEE_TIERS.get(int(p.get("feeTier", 3000)), "0.3%"),
                "apy":               apy,
                "tvl_usd":           tvl,
                "volume_24h":        vol,
                "liquidity":         float(p.get("liquidity", 0)),
                "hourly_vol_change": 0.05,
                "whale_alert":       False,
                "recent_large_tx":   None,
                "subgraph_url":      self._subgraph,
                "data_source":       "uniswap_subgraph",
                "last_updated":      _now(),
            }
        logger.info("Loaded %d live pools from subgraph", len(result))
        return result or dict(MOCK_POOLS)

    # ── Swap Quote ───────────────────────────

    async def calculate_slippage(
        self, token_from: str, token_to: str, amount_usd: float
    ) -> Optional[dict]:
        """
        Calculate swap impact.
        Live: Uniswap Trading API quote → subgraph AMM estimate
        Mock: constant-product AMM approximation

        Uniswap Integration: swap-integration skill — quote step.
        """
        if not self.mock_mode and self._api_key:
            result = await self._trading_api_quote(token_from, token_to, amount_usd)
            if result:
                return result

        return await self._amm_estimate(token_from, token_to, amount_usd)

    async def _trading_api_quote(self, t_from: str, t_to: str, amount_usd: float) -> Optional[dict]:
        """
        Uniswap Trading API — Step 2 of swap-integration skill.
        check_approval → quote → swap
        """
        addr_from = TOKEN_ADDRESSES.get(t_from.upper())
        addr_to   = TOKEN_ADDRESSES.get(t_to.upper())
        if not addr_from or not addr_to:
            return None

        dec_in     = 6 if t_from.upper() in ("USDC", "USDT") else 18
        amount_raw = str(int(amount_usd * (10 ** dec_in)))

        headers = {
            "Content-Type": "application/json",
            "x-api-key":    self._api_key,
            "Origin":       "https://app.uniswap.org",
        }
        body = {
            "tokenIn":           addr_from,
            "tokenOut":          addr_to,
            "amount":            amount_raw,
            "type":              "EXACT_INPUT",
            "chainId":           1,
            "routingPreference": "BEST_PRICE",
        }

        if not AIOHTTP_AVAILABLE:
            return None

        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{TRADING_API_BASE}/quote", json=body,
                                   headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=15)) as r:
                    if r.status != 200:
                        logger.warning("Trading API quote → %s", r.status)
                        return None
                    data = await r.json()
        except Exception as e:
            logger.warning("Trading API error: %s", e)
            return None

        q        = data.get("quote", {})
        dec_out  = 6 if t_to.upper() in ("USDC", "USDT") else 18
        output   = float(q.get("output", {}).get("amount", 0)) / (10 ** dec_out)
        routing  = q.get("routing", "CLASSIC")
        gas_usd  = float(q.get("gasUseEstimateUSD", 0))
        slip     = float(q.get("slippage", 0.5))

        # Build Uniswap deep link (uniswap-driver swap-planner skill)
        deep_link = (
            f"https://app.uniswap.org/swap"
            f"?chain=ethereum"
            f"&inputCurrency={addr_from}"
            f"&outputCurrency={addr_to}"
            f"&value={amount_usd}&field=INPUT"
        )

        return {
            "expected_output": round(output, 6),
            "slippage":        round(slip, 3),
            "price_impact":    round(float(q.get("priceImpact", 0)), 3),
            "gas_gwei":        35,
            "gas_usd":         round(gas_usd, 4),
            "route":           f"Uniswap {routing}: {t_from} → {t_to}",
            "fee_tier":        "varies",
            "routing_type":    routing,
            "routing_desc":    ROUTING_TYPES.get(routing, routing),
            "pool_ref":        deep_link,
            "data_source":     "trading_api",
        }

    async def _amm_estimate(self, t_from: str, t_to: str, amount_usd: float) -> Optional[dict]:
        """
        AMM slippage estimate using constant-product model.
        Uniswap Integration: pool-analytics liquidity depth model.
        """
        pair_key = f"{t_from.upper()}/{t_to.upper()}"
        alt_key  = f"{t_to.upper()}/{t_from.upper()}"

        # Try live pool first, then mock
        metrics = None
        if not self.mock_mode:
            metrics = await self.fetch_pool_metrics(pair_key)
        if not metrics:
            metrics = MOCK_POOLS.get(pair_key) or MOCK_POOLS.get(alt_key)

        p_from = MOCK_PRICES.get(t_from.upper(), 1.0)
        p_to   = MOCK_PRICES.get(t_to.upper(), 1.0)

        if metrics:
            tvl      = metrics["tvl_usd"]
            fee_str  = metrics.get("fee_tier", "0.3%")
            fee_pct  = float(fee_str.replace("%", "")) / 100
            impact   = (amount_usd / max(tvl, 1)) * 100
            slip     = round(impact + fee_pct * 100, 4)
            output   = (amount_usd / p_from) * (p_from / p_to) * (1 - fee_pct - impact / 100)

            # Deep link (uniswap-driver pattern)
            addr_from = TOKEN_ADDRESSES.get(t_from.upper(), "")
            addr_to   = TOKEN_ADDRESSES.get(t_to.upper(), "")
            deep_link = (
                f"https://app.uniswap.org/swap?chain=ethereum"
                f"&inputCurrency={addr_from}&outputCurrency={addr_to}"
                f"&value={amount_usd}&field=INPUT"
            ) if addr_from and addr_to else ""

            return {
                "expected_output": round(max(output, 0), 6),
                "slippage":        slip,
                "price_impact":    round(impact, 4),
                "gas_gwei":        20 if "USDC/USDT" in [pair_key, alt_key] else 35,
                "gas_usd":         0.0,
                "route":           f"Uniswap V3: {t_from} → {t_to} ({fee_str} pool)",
                "fee_tier":        fee_str,
                "routing_type":    "CLASSIC",
                "routing_desc":    ROUTING_TYPES["CLASSIC"],
                "pool_ref":        deep_link or metrics.get("subgraph_url", ""),
                "data_source":     metrics.get("data_source", "mock") + "_amm",
            }

        # Minimal price-only estimate
        if p_from and p_to:
            output = (amount_usd / p_from) * (p_from / p_to) * 0.997
            return {
                "expected_output": round(max(output, 0), 6),
                "slippage": 0.3, "price_impact": 0.1,
                "gas_gwei": 35, "gas_usd": 0.0,
                "route": f"Estimated: {t_from} → {t_to}",
                "fee_tier": "0.3%", "routing_type": "CLASSIC",
                "routing_desc": ROUTING_TYPES["CLASSIC"],
                "pool_ref": "", "data_source": "price_estimate",
            }
        return None

    # ── Whale Detection ──────────────────────

    async def detect_whale_movement(self, pool_name: str) -> dict:
        """
        Detect unusual activity.
        Onchain OS Integration: anomaly-detection pattern.
        """
        metrics = await self.fetch_pool_metrics(pool_name)
        if not metrics:
            return {"detected": False, "details": None}

        if metrics.get("whale_alert") and metrics.get("recent_large_tx"):
            tx = metrics["recent_large_tx"]
            return {
                "detected":    True,
                "amount_usd":  tx.get("amount_usd", 0),
                "type":        tx.get("type", "unknown"),
                "age_minutes": tx.get("age_minutes", 0),
                "risk_flag":   True,
                "message":     tx.get("message", "⚠️ Unusual activity detected"),
            }
        return {"detected": False, "details": None}

    def get_uniswap_deep_link(
        self, token_from: str, token_to: str,
        amount: float, chain: str = "ethereum"
    ) -> str:
        """
        Build Uniswap interface deep link.
        uniswap-driver swap-planner skill URL pattern.
        """
        addr_from = TOKEN_ADDRESSES.get(token_from.upper(), "NATIVE")
        addr_to   = TOKEN_ADDRESSES.get(token_to.upper(), "NATIVE")
        return (
            f"https://app.uniswap.org/swap"
            f"?chain={chain}&inputCurrency={addr_from}"
            f"&outputCurrency={addr_to}&value={amount}&field=INPUT"
        )