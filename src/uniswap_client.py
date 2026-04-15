"""
ChainSight – Uniswap Real Data Client
======================================
Integrates real Uniswap data sources following the uniswap-ai skill patterns:

  • uniswap-trading  → Trading API (check_approval → quote → swap)
  • uniswap-viem     → EVM reads via JSON-RPC (token prices, balances)
  • swap-integration → Universal Router quote flow
  • v4-security      → Pool risk assessment patterns

References:
  https://api-docs.uniswap.org/introduction
  https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3
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

logger = logging.getLogger("chainsight.uniswap")

# ─────────────────────────────────────────────────────────────────
# Uniswap Trading API  (uniswap-trading skill: swap-integration)
# 3-step flow: check_approval → quote → swap
# ─────────────────────────────────────────────────────────────────
TRADING_API_BASE  = "https://trade-api.gateway.uniswap.org/v1"
UNISWAP_API_KEY   = os.getenv("UNISWAP_API_KEY", "")          # register at developers.uniswap.org

# ─────────────────────────────────────────────────────────────────
# Uniswap V3 Subgraph  (The Graph – pool-analytics)
# ─────────────────────────────────────────────────────────────────
SUBGRAPH_V3_ETH   = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"
SUBGRAPH_V3_BASE  = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3-base"
SUBGRAPH_V3_ARB   = "https://api.thegraph.com/subgraphs/name/ianlapham/uniswap-arbitrum-one"

# ─────────────────────────────────────────────────────────────────
# DexScreener API (free, no key – used by uniswap-driver skills)
# ─────────────────────────────────────────────────────────────────
DEXSCREENER_BASE  = "https://api.dexscreener.com/latest/dex"

# ─────────────────────────────────────────────────────────────────
# DefiLlama API (free fallback for APY / TVL)
# ─────────────────────────────────────────────────────────────────
DEFILLAMA_BASE    = "https://api.llama.fi"

# ─────────────────────────────────────────────────────────────────
# Chain config  (following uniswap-driver chain name map)
# ─────────────────────────────────────────────────────────────────
CHAIN_CONFIG = {
    "ethereum": {"chain_id": 1,     "rpc": "https://cloudflare-eth.com",        "subgraph": SUBGRAPH_V3_ETH},
    "base":     {"chain_id": 8453,  "rpc": "https://mainnet.base.org",          "subgraph": SUBGRAPH_V3_BASE},
    "arbitrum": {"chain_id": 42161, "rpc": "https://arb1.arbitrum.io/rpc",      "subgraph": SUBGRAPH_V3_ARB},
    "xlayer":   {"chain_id": 196,   "rpc": "https://rpc.xlayer.tech",           "subgraph": SUBGRAPH_V3_ETH},
    "xlayer-test": {"chain_id": 195,"rpc": "https://testrpc.xlayer.tech",       "subgraph": SUBGRAPH_V3_ETH},
}

# ─────────────────────────────────────────────────────────────────
# Well-known token addresses (Ethereum mainnet)
# Used by swap-integration & viem-integration skills
# ─────────────────────────────────────────────────────────────────
TOKEN_ADDRESSES = {
    "ethereum": {
        "USDC":  "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "USDT":  "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "WETH":  "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "ETH":   "0x0000000000000000000000000000000000000000",
        "WBTC":  "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "DAI":   "0x6B175474E89094C44Da98b954EedeAC495271d0F",
        "UNI":   "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
    },
    "base": {
        "USDC":  "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "WETH":  "0x4200000000000000000000000000000000000006",
        "ETH":   "0x0000000000000000000000000000000000000000",
        "DAI":   "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
    },
}

# ─────────────────────────────────────────────────────────────────
# Routing types supported by the Trading API
# (from uniswap-trading swap-integration skill)
# ─────────────────────────────────────────────────────────────────
ROUTING_TYPES = {
    "CLASSIC":   "Standard AMM swap through Uniswap pools",
    "DUTCH_V2":  "UniswapX Dutch auction V2 — MEV-protected",
    "PRIORITY":  "MEV-protected priority order (Base, Unichain)",
    "WRAP":      "ETH → WETH conversion",
    "UNWRAP":    "WETH → ETH conversion",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─────────────────────────────────────────────────────────────────
# HTTP helpers
# ─────────────────────────────────────────────────────────────────
async def _get(url: str, params: dict | None = None, headers: dict | None = None,
               timeout: int = 10, retries: int = 3) -> Optional[dict]:
    """GET with retry logic (viem-integration pattern: retry on 429/5xx)."""
    if not AIOHTTP_AVAILABLE:
        logger.error("aiohttp required: pip install aiohttp")
        return None
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params=params, headers=headers or {},
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    if resp.status == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    logger.warning("GET %s → HTTP %s", url, resp.status)
                    return None
        except asyncio.TimeoutError:
            logger.warning("Timeout: %s (attempt %d)", url, attempt + 1)
        except Exception as exc:
            logger.warning("Request error: %s (attempt %d)", exc, attempt + 1)
        await asyncio.sleep(1.5 ** attempt)
    return None


async def _post(url: str, body: dict, headers: dict | None = None,
                timeout: int = 15) -> Optional[dict]:
    """POST for Trading API calls."""
    if not AIOHTTP_AVAILABLE:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=body, headers=headers or {},
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                data = await resp.json()
                if resp.status in (200, 201):
                    return data
                logger.warning("POST %s → HTTP %s: %s", url, resp.status, data)
                return {"error": data, "status_code": resp.status}
    except Exception as exc:
        logger.warning("POST error: %s", exc)
        return None


async def _gql(endpoint: str, query: str, variables: dict | None = None,
               retries: int = 3) -> Optional[dict]:
    """GraphQL query with retry (subgraph pattern from uniswap-trading)."""
    if not AIOHTTP_AVAILABLE:
        return None
    payload = {"query": query, "variables": variables or {}}
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint, json=payload,
                    timeout=aiohttp.ClientTimeout(total=12)
                ) as resp:
                    if resp.status == 200:
                        body = await resp.json()
                        if "errors" in body:
                            logger.warning("GQL errors: %s", body["errors"])
                        return body.get("data")
                    logger.warning("GQL %s → HTTP %s (attempt %d)", endpoint, resp.status, attempt + 1)
        except asyncio.TimeoutError:
            logger.warning("GQL timeout (attempt %d)", attempt + 1)
        except Exception as exc:
            logger.warning("GQL error: %s (attempt %d)", exc, attempt + 1)
        await asyncio.sleep(1.5 ** attempt)
    return None


# ─────────────────────────────────────────────────────────────────
# UNISWAP TRADING API CLIENT
# Following the uniswap-trading swap-integration skill:
#   Step 1 → check_approval
#   Step 2 → quote
#   Step 3 → swap
# ─────────────────────────────────────────────────────────────────
class UniswapTradingAPI:
    """
    Wraps the Uniswap Trading API.
    Register for an API key at: https://developers.uniswap.org/
    Set UNISWAP_API_KEY environment variable.
    """

    def __init__(self):
        self.api_key = UNISWAP_API_KEY
        self.base    = TRADING_API_BASE

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json", "Origin": "https://app.uniswap.org"}
        if self.api_key:
            h["x-api-key"] = self.api_key
        return h

    async def get_quote(
        self,
        token_in:   str,
        token_out:  str,
        amount:     str,          # in smallest unit (wei / USDC 6-dec)
        chain_id:   int = 1,
        trade_type: str = "EXACT_INPUT",   # or EXACT_OUTPUT
        swapper:    str | None = None,
    ) -> Optional[dict]:
        """
        Step 2 of swap-integration skill: get a swap quote.
        trade_type: EXACT_INPUT or EXACT_OUTPUT
        Returns routing type, quote amount, gas estimate, permit data.
        """
        body = {
            "tokenIn":        token_in,
            "tokenOut":       token_out,
            "amount":         amount,
            "type":           trade_type,
            "chainId":        chain_id,
            "routingPreference": "CLASSIC",   # or BEST_PRICE, BEST_PRICE_V2
        }
        if swapper:
            body["swapper"] = swapper

        return await _post(f"{self.base}/quote", body, headers=self._headers())

    async def check_approval(
        self,
        token:    str,
        amount:   str,
        walletAddress: str,
        chain_id: int = 1,
    ) -> Optional[dict]:
        """
        Step 1 of swap-integration skill: check if approval is needed.
        Returns: { needsApproval: bool, gasFee: str }
        """
        params = {
            "token":         token,
            "amount":        amount,
            "walletAddress": walletAddress,
            "chainId":       chain_id,
        }
        return await _get(f"{self.base}/check_approval", params=params, headers=self._headers())

    async def get_swap_calldata(
        self,
        quote:         dict,
        walletAddress: str,
        slippage_bps:  int = 50,     # 50 bps = 0.5%
    ) -> Optional[dict]:
        """
        Step 3 of swap-integration skill: build the swap transaction.
        Takes the quote response and builds Universal Router calldata.
        """
        body = {
            "quote":          quote.get("quote", quote),
            "walletAddress":  walletAddress,
            "slippageTolerance": str(slippage_bps / 100),
        }
        return await _post(f"{self.base}/swap", body, headers=self._headers())

    async def get_token_price(self, token_address: str, chain_id: int = 1) -> Optional[float]:
        """
        Fetch USD price for a token via the Trading API price endpoint.
        Used by viem-integration skill for read operations.
        """
        params = {"tokenAddress": token_address, "chainId": chain_id}
        data = await _get(f"{self.base}/token_stats_v2", params=params, headers=self._headers())
        if data and "price" in data:
            return float(data["price"])
        return None


# ─────────────────────────────────────────────────────────────────
# UNISWAP V3 SUBGRAPH CLIENT
# GraphQL queries following pool-analytics skill patterns
# ─────────────────────────────────────────────────────────────────
class UniswapSubgraphClient:
    """
    Queries the Uniswap V3 subgraph for pool metrics.
    Implements pool-analytics patterns from uniswap-trading skill.
    """

    # Pool query — matches uniswap-trading pool-analytics pattern
    POOL_BY_TOKENS_QUERY = """
    query PoolByTokens($token0: String!, $token1: String!) {
      pools(
        where: {
          token0_: { symbol_in: [$token0, $token1] }
          token1_: { symbol_in: [$token0, $token1] }
        }
        orderBy: totalValueLockedUSD
        orderDirection: desc
        first: 5
      ) {
        id
        feeTier
        token0 { id symbol decimals }
        token1 { id symbol decimals }
        totalValueLockedUSD
        volumeUSD
        token0Price
        token1Price
        liquidity
        sqrtPrice
        tick
        poolDayData(first: 7, orderBy: date, orderDirection: desc) {
          date
          volumeUSD
          feesUSD
          tvlUSD
          open
          high
          low
          close
        }
        poolHourData(first: 24, orderBy: periodStartUnix, orderDirection: desc) {
          periodStartUnix
          volumeUSD
          feesUSD
          open
          close
        }
      }
    }
    """

    # Top pools query — used by get_beginner_recommendation
    TOP_POOLS_QUERY = """
    query TopPools($minTvl: String!) {
      pools(
        where: { totalValueLockedUSD_gt: $minTvl }
        orderBy: totalValueLockedUSD
        orderDirection: desc
        first: 30
      ) {
        id
        feeTier
        token0 { id symbol }
        token1 { id symbol }
        totalValueLockedUSD
        volumeUSD
        liquidity
        poolDayData(first: 7, orderBy: date, orderDirection: desc) {
          feesUSD
          tvlUSD
          volumeUSD
        }
      }
    }
    """

    # Pool by address
    POOL_BY_ADDRESS_QUERY = """
    query PoolByAddress($id: ID!) {
      pool(id: $id) {
        id
        feeTier
        token0 { id symbol decimals }
        token1 { id symbol decimals }
        totalValueLockedUSD
        volumeUSD
        token0Price
        token1Price
        liquidity
        poolDayData(first: 7, orderBy: date, orderDirection: desc) {
          date volumeUSD feesUSD tvlUSD
        }
        poolHourData(first: 2, orderBy: periodStartUnix, orderDirection: desc) {
          periodStartUnix volumeUSD open close
        }
      }
    }
    """

    def __init__(self, chain: str = "ethereum"):
        self.chain    = chain
        self.endpoint = CHAIN_CONFIG.get(chain, CHAIN_CONFIG["ethereum"])["subgraph"]

    async def get_pool_by_tokens(self, token0_sym: str, token1_sym: str) -> Optional[dict]:
        """Fetch the deepest pool for a token pair."""
        data = await _gql(
            self.endpoint,
            self.POOL_BY_TOKENS_QUERY,
            {"token0": token0_sym.upper(), "token1": token1_sym.upper()}
        )
        if not data or not data.get("pools"):
            return None
        return data["pools"][0]   # highest TVL pool

    async def get_pool_by_address(self, address: str) -> Optional[dict]:
        data = await _gql(self.endpoint, self.POOL_BY_ADDRESS_QUERY, {"id": address.lower()})
        return data.get("pool") if data else None

    async def get_top_pools(self, min_tvl_usd: float = 500_000) -> list[dict]:
        data = await _gql(
            self.endpoint,
            self.TOP_POOLS_QUERY,
            {"minTvl": str(int(min_tvl_usd))}
        )
        return data.get("pools", []) if data else []

    def calculate_apy(self, pool_day_data: list[dict], tvl: float) -> float:
        """
        7-day APY estimation from subgraph fee data.
        (pool-analytics skill standard method)
        """
        if not pool_day_data or tvl <= 0:
            return 0.0
        total_fees = sum(float(d.get("feesUSD", 0)) for d in pool_day_data)
        avg_daily  = total_fees / len(pool_day_data)
        return round((avg_daily * 365 / tvl) * 100, 2)

    def calculate_hourly_vol_change(self, hour_data: list[dict]) -> float:
        """Measure recent price volatility from hourly candles."""
        if len(hour_data) < 2:
            return 0.05
        try:
            latest  = float(hour_data[0].get("close", 1))
            prev    = float(hour_data[1].get("open", 1))
            if prev == 0:
                return 0.05
            return abs(latest - prev) / prev
        except (TypeError, ValueError):
            return 0.05

    def detect_whale_movement(self, pool_day_data: list[dict], tvl: float) -> dict:
        """
        Detect large single-day volume spikes relative to TVL.
        Adapted from Onchain OS anomaly-detection pattern.
        """
        if not pool_day_data or tvl <= 0:
            return {"detected": False}
        latest_vol = float(pool_day_data[0].get("volumeUSD", 0)) if pool_day_data else 0
        ratio      = latest_vol / tvl if tvl > 0 else 0
        if ratio > 0.3:   # volume > 30% of TVL in one day = unusual
            return {
                "detected": True,
                "amount_usd": latest_vol,
                "type": "high_volume_spike",
                "age_minutes": 0,
                "message": f"⚠️ Unusually high volume (${latest_vol:,.0f}) vs TVL (${tvl:,.0f})"
            }
        return {"detected": False}


# ─────────────────────────────────────────────────────────────────
# DEXSCREENER CLIENT
# Free API used by uniswap-driver swap-planner & liquidity-planner
# ─────────────────────────────────────────────────────────────────
class DexScreenerClient:
    """
    DexScreener API client.
    Used by uniswap-driver skills for token discovery and price feeds.
    No API key required.
    """

    async def search_pairs(self, query: str) -> list[dict]:
        """Search for token pairs by keyword (used in swap-planner skill)."""
        data = await _get(f"{DEXSCREENER_BASE}/search", params={"q": query})
        if not data:
            return []
        return data.get("pairs", [])[:10]

    async def get_token_pairs(self, chain: str, token_address: str) -> list[dict]:
        """Get all pairs for a token address."""
        data = await _get(f"{DEXSCREENER_BASE}/tokens/{token_address}")
        if not data:
            return []
        pairs = data.get("pairs", [])
        # Filter by chain and sort by liquidity
        return sorted(
            [p for p in pairs if p.get("chainId", "").lower() == chain.lower()],
            key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0),
            reverse=True
        )

    async def get_uniswap_pairs(self, token0: str, token1: str,
                                 chain: str = "ethereum") -> Optional[dict]:
        """Get the best Uniswap V3 pair for a token pair on a given chain."""
        results = await self.search_pairs(f"{token0} {token1}")
        uniswap_pairs = [
            p for p in results
            if "uniswap" in p.get("dexId", "").lower()
            and p.get("chainId", "").lower() == chain.lower()
        ]
        if not uniswap_pairs:
            return None
        # Return highest liquidity
        return sorted(
            uniswap_pairs,
            key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0),
            reverse=True
        )[0]

    def parse_pair_metrics(self, pair: dict) -> dict:
        """Extract standardised metrics from a DexScreener pair."""
        liquidity  = pair.get("liquidity", {})
        volume     = pair.get("volume", {})
        price_change = pair.get("priceChange", {})
        return {
            "pair_address":    pair.get("pairAddress", ""),
            "dex":             pair.get("dexId", ""),
            "chain":           pair.get("chainId", ""),
            "token0_symbol":   pair.get("baseToken", {}).get("symbol", ""),
            "token1_symbol":   pair.get("quoteToken", {}).get("symbol", ""),
            "price_usd":       float(pair.get("priceUsd", 0) or 0),
            "price_native":    float(pair.get("priceNative", 0) or 0),
            "liquidity_usd":   float(liquidity.get("usd", 0) or 0),
            "liquidity_base":  float(liquidity.get("base", 0) or 0),
            "volume_24h":      float(volume.get("h24", 0) or 0),
            "volume_6h":       float(volume.get("h6", 0) or 0),
            "price_change_24h": float(price_change.get("h24", 0) or 0),
            "price_change_1h":  float(price_change.get("h1", 0) or 0),
            "txns_24h":        pair.get("txns", {}).get("h24", {}),
            "url":             pair.get("url", ""),
            "last_updated":    _now(),
        }


# ─────────────────────────────────────────────────────────────────
# DEFILLAMA CLIENT
# Fallback for APY / TVL data (used by uniswap-driver liquidity-planner)
# ─────────────────────────────────────────────────────────────────
class DefiLlamaClient:
    """
    DefiLlama API — free APY/TVL fallback.
    Used by liquidity-planner skill for pool metrics on low-coverage chains.
    """

    async def get_uniswap_pools(self, chain: str = "Ethereum") -> list[dict]:
        """Fetch Uniswap V3 pool APY data from DefiLlama yield endpoint."""
        data = await _get(f"{DEFILLAMA_BASE}/pools")
        if not data or "data" not in data:
            return []
        return [
            p for p in data["data"]
            if "uniswap-v3" in p.get("project", "").lower()
            and p.get("chain", "").lower() == chain.lower()
        ]

    async def get_protocol_tvl(self) -> Optional[float]:
        """Get total Uniswap TVL."""
        data = await _get(f"{DEFILLAMA_BASE}/protocol/uniswap")
        if not data:
            return None
        return float(data.get("tvl", [{}])[-1].get("totalLiquidityUSD", 0))


# ─────────────────────────────────────────────────────────────────
# UNIFIED REAL DATA FETCHER
# Wraps all three sources with intelligent fallback chain:
#   1. Uniswap V3 Subgraph (richest data)
#   2. DexScreener (price + volume, no key)
#   3. DefiLlama (APY/TVL fallback)
# ─────────────────────────────────────────────────────────────────
class RealDataFetcher:
    """
    Production data fetcher combining Uniswap subgraph,
    DexScreener, and DefiLlama — with 30s TTL caching.
    """

    def __init__(self, chain: str = "ethereum"):
        self.chain       = chain
        self.subgraph    = UniswapSubgraphClient(chain)
        self.dexscreener = DexScreenerClient()
        self.defillama   = DefiLlamaClient()
        self.trading_api = UniswapTradingAPI()
        self._cache: dict[str, tuple[float, dict]] = {}
        self._cache_ttl = 30

    def _cache_get(self, key: str) -> Optional[dict]:
        if key in self._cache:
            ts, data = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                return data
        return None

    def _cache_set(self, key: str, data: dict) -> None:
        self._cache[key] = (time.time(), data)

    async def fetch_pool_metrics(self, token0: str, token1: str) -> Optional[dict]:
        """
        Fetch real pool metrics with fallback chain.
        Returns normalised dict compatible with InsightEngine.
        """
        cache_key = f"pool:{self.chain}:{token0}/{token1}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        # ── Source 1: Uniswap V3 Subgraph ────────────────────────
        pool = await self.subgraph.get_pool_by_tokens(token0, token1)

        if pool:
            tvl        = float(pool.get("totalValueLockedUSD", 0))
            day_data   = pool.get("poolDayData", [])
            hour_data  = pool.get("poolHourData", [])
            apy        = self.subgraph.calculate_apy(day_data, tvl)
            vol_change = self.subgraph.calculate_hourly_vol_change(hour_data)
            vol_24h    = float(day_data[0].get("volumeUSD", 0)) if day_data else 0
            whale      = self.subgraph.detect_whale_movement(day_data, tvl)
            fee_tier   = self._fee_tier_label(int(pool.get("feeTier", 3000)))

            result = {
                "pool_address":      pool["id"],
                "token0":            pool["token0"]["symbol"],
                "token1":            pool["token1"]["symbol"],
                "fee_tier":          fee_tier,
                "apy":               apy,
                "tvl_usd":           tvl,
                "volume_24h":        vol_24h,
                "price_token1":      float(pool.get("token1Price", 0)),
                "liquidity":         float(pool.get("liquidity", 0)),
                "hourly_vol_change": vol_change,
                "whale_alert":       whale.get("detected", False),
                "recent_large_tx":   {"amount_usd": whale.get("amount_usd", 0),
                                      "type": whale.get("type", ""), "age_minutes": 0}
                                      if whale.get("detected") else None,
                "subgraph_url":      self.subgraph.endpoint,
                "data_source":       "uniswap_subgraph",
                "last_updated":      _now(),
            }
            self._cache_set(cache_key, result)
            return result

        # ── Source 2: DexScreener fallback ───────────────────────
        logger.info("Subgraph returned no data, trying DexScreener for %s/%s", token0, token1)
        pair = await self.dexscreener.get_uniswap_pairs(token0, token1, self.chain)

        if pair:
            metrics = self.dexscreener.parse_pair_metrics(pair)
            tvl     = metrics["liquidity_usd"]
            vol_24h = metrics["volume_24h"]
            # Estimate APY from 24h fees (fee ~ 0.3% of volume, rough estimate)
            est_daily_fees = vol_24h * 0.003
            apy            = round((est_daily_fees * 365 / max(tvl, 1)) * 100, 2)
            vol_change     = abs(metrics["price_change_1h"]) / 100

            result = {
                "pool_address":      metrics["pair_address"],
                "token0":            token0.upper(),
                "token1":            token1.upper(),
                "fee_tier":          "0.3%",
                "apy":               apy,
                "tvl_usd":           tvl,
                "volume_24h":        vol_24h,
                "price_token1":      metrics["price_usd"],
                "liquidity":         tvl,
                "hourly_vol_change": vol_change,
                "whale_alert":       abs(metrics["price_change_24h"]) > 10,
                "recent_large_tx":   None,
                "subgraph_url":      metrics["url"],
                "data_source":       "dexscreener",
                "last_updated":      _now(),
            }
            self._cache_set(cache_key, result)
            return result

        logger.warning("No real data found for %s/%s on %s", token0, token1, self.chain)
        return None

    async def fetch_swap_quote(
        self,
        token_from:  str,
        token_to:    str,
        amount_usd:  float,
        chain:       str = "ethereum",
    ) -> Optional[dict]:
        """
        Fetch real swap quote via Uniswap Trading API.
        Follows swap-integration skill: quote step.
        Falls back to subgraph-based AMM estimate if no API key.
        """
        chain_cfg  = CHAIN_CONFIG.get(chain, CHAIN_CONFIG["ethereum"])
        chain_id   = chain_cfg["chain_id"]
        tokens     = TOKEN_ADDRESSES.get(chain, TOKEN_ADDRESSES["ethereum"])
        addr_from  = tokens.get(token_from.upper())
        addr_to    = tokens.get(token_to.upper())

        # ── Live Trading API quote ────────────────────────────────
        if self.trading_api.api_key and addr_from and addr_to:
            # Convert amount to token units (USDC = 6 decimals, ETH = 18)
            decimals   = 6 if token_from.upper() in ("USDC", "USDT") else 18
            amount_raw = str(int(amount_usd * (10 ** decimals)))

            quote = await self.trading_api.get_quote(
                token_in=addr_from,
                token_out=addr_to,
                amount=amount_raw,
                chain_id=chain_id,
            )

            if quote and "quote" in quote:
                q          = quote["quote"]
                out_dec    = 6 if token_to.upper() in ("USDC", "USDT") else 18
                output     = float(q.get("output", {}).get("amount", 0)) / (10 ** out_dec)
                slippage   = float(q.get("slippage", 0.5))
                routing    = q.get("routing", "CLASSIC")
                gas_usd    = float(q.get("gasUseEstimateUSD", 0))
                return {
                    "expected_output": round(output, 6),
                    "slippage":        round(slippage, 3),
                    "price_impact":    round(float(q.get("priceImpact", 0)), 3),
                    "gas_gwei":        35,
                    "gas_usd":         round(gas_usd, 4),
                    "route":           f"Uniswap {routing}: {token_from} → {token_to}",
                    "fee_tier":        "varies",
                    "routing_type":    routing,
                    "routing_desc":    ROUTING_TYPES.get(routing, routing),
                    "pool_ref":        f"https://app.uniswap.org/swap?chain={chain}"
                                       f"&inputCurrency={addr_from}&outputCurrency={addr_to}",
                    "data_source":     "trading_api",
                }

        # ── Fallback: subgraph-based AMM estimate ─────────────────
        logger.info("No Trading API key or token addresses; using subgraph AMM estimate")
        pool = await self.fetch_pool_metrics(token_from, token_to)
        if pool:
            tvl      = pool["tvl_usd"]
            fee_str  = pool["fee_tier"]
            fee_pct  = float(fee_str.replace("%", "")) / 100
            impact   = (amount_usd / max(tvl, 1)) * 100
            slip     = round(impact + fee_pct * 100, 4)
            # Use DexScreener price if available
            price    = pool.get("price_token1", 0)
            output   = (amount_usd / max(price, 0.0001)) * (1 - fee_pct - impact / 100) \
                       if price else amount_usd * 0.0003
            return {
                "expected_output": round(max(output, 0), 6),
                "slippage":        round(slip, 3),
                "price_impact":    round(impact, 3),
                "gas_gwei":        30,
                "gas_usd":         0.0,
                "route":           f"Uniswap V3: {token_from} → {token_to} ({fee_str} pool)",
                "fee_tier":        fee_str,
                "routing_type":    "CLASSIC",
                "routing_desc":    ROUTING_TYPES["CLASSIC"],
                "pool_ref":        pool.get("subgraph_url", ""),
                "data_source":     "subgraph_estimate",
            }

        return None

    async def fetch_top_pools(self, min_tvl: float = 500_000) -> dict[str, dict]:
        """Fetch top Uniswap V3 pools ranked by TVL."""
        cache_key = f"top_pools:{self.chain}:{min_tvl}"
        cached    = self._cache_get(cache_key)
        if cached:
            return cached

        raw_pools = await self.subgraph.get_top_pools(min_tvl)
        result    = {}

        for p in raw_pools:
            t0   = p["token0"]["symbol"]
            t1   = p["token1"]["symbol"]
            name = f"{t0}/{t1}"
            tvl  = float(p.get("totalValueLockedUSD", 0))
            day  = p.get("poolDayData", [])
            apy  = self.subgraph.calculate_apy(day, tvl)
            vol  = float(day[0].get("volumeUSD", 0)) if day else 0
            whale = self.subgraph.detect_whale_movement(day, tvl)

            result[name] = {
                "pool_address":      p["id"],
                "token0":            t0,
                "token1":            t1,
                "fee_tier":          self._fee_tier_label(int(p.get("feeTier", 3000))),
                "apy":               apy,
                "tvl_usd":           tvl,
                "volume_24h":        vol,
                "liquidity":         float(p.get("liquidity", 0)),
                "hourly_vol_change": 0.05,
                "whale_alert":       whale.get("detected", False),
                "recent_large_tx":   None,
                "subgraph_url":      self.subgraph.endpoint,
                "data_source":       "uniswap_subgraph",
                "last_updated":      _now(),
            }

        if result:
            self._cache_set(cache_key, result)
        return result

    @staticmethod
    def _fee_tier_label(fee_tier_raw: int) -> str:
        """
        Convert raw fee tier (100/500/3000/10000) to percentage string.
        (Uniswap V3 fee tier constants from uniswap-hooks skill)
        """
        mapping = {100: "0.01%", 500: "0.05%", 3000: "0.3%", 10000: "1%"}
        return mapping.get(fee_tier_raw, f"{fee_tier_raw / 10000:.2f}%")

    def build_uniswap_deep_link(
        self,
        token_from:  str,
        token_to:    str,
        amount:      float,
        chain:       str = "ethereum",
        field:       str = "INPUT",
    ) -> str:
        """
        Generate a Uniswap deep link following the uniswap-driver swap-planner skill.
        Opens app.uniswap.org with parameters pre-filled.
        """
        tokens = TOKEN_ADDRESSES.get(chain, {})
        addr_from = tokens.get(token_from.upper(), "NATIVE")
        addr_to   = tokens.get(token_to.upper(), "NATIVE")

        return (
            f"https://app.uniswap.org/swap"
            f"?chain={chain}"
            f"&inputCurrency={addr_from}"
            f"&outputCurrency={addr_to}"
            f"&value={amount}"
            f"&field={field}"
        )