"""
ChainSight MCP Server
Exposes 3 standardized MCP-compliant tools for X Layer + Uniswap on-chain analysis.
"""

import asyncio
import json
import logging
from typing import Any

try:
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    from mcp.server.stdio import stdio_server
    from mcp import types
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

from onchain_data import OnChainDataFetcher
from insight_engine import InsightEngine
from agentic_wallet import AgenticWallet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chainsight-mcp")

# ─────────────────────────────────────────────
# Tool Response Schema
# ─────────────────────────────────────────────
def build_response(
    status: str,
    data: dict,
    explanation: str,
    on_chain_ref: str = "",
    warnings: list[str] | None = None
) -> dict:
    return {
        "status": status,
        "data": data,
        "explanation": explanation,
        "on_chain_ref": on_chain_ref,
        "warnings": warnings or [],
        "disclaimer": "⚠️ This is data analysis only — not financial advice."
    }


# ─────────────────────────────────────────────
# Core Tool Logic (framework-agnostic)
# ─────────────────────────────────────────────
class ChainSightTools:
    def __init__(self, mock_mode: bool = True):
        self.fetcher = OnChainDataFetcher(mock_mode=mock_mode)
        self.engine  = InsightEngine()
        self.wallet  = AgenticWallet()
        self.mock_mode = mock_mode

    # ── Tool 1 ──────────────────────────────
    async def get_pool_health(self, pool_name: str) -> dict:
        """
        Returns APY, liquidity depth, volatility score, and risk level
        for a named pool on X Layer / Uniswap V3.
        """
        if not pool_name or not isinstance(pool_name, str):
            return build_response(
                status="error",
                data={},
                explanation="Invalid pool name. Try 'USDC/ETH', 'USDT/OKB', or 'ETH/OKB'."
            )

        pool_name = pool_name.upper().strip()
        metrics = await self.fetcher.fetch_pool_metrics(pool_name)

        if metrics is None:
            return build_response(
                status="error",
                data={},
                explanation=f"Pool '{pool_name}' not found. Available: USDC/ETH, USDT/OKB, ETH/OKB, USDC/USDT."
            )

        insight = self.engine.analyze_pool(metrics)

        return build_response(
            status="success",
            data={
                "pool":            pool_name,
                "apy_percent":     metrics["apy"],
                "tvl_usd":         metrics["tvl_usd"],
                "volume_24h_usd":  metrics["volume_24h"],
                "fee_tier":        metrics["fee_tier"],
                "risk_level":      insight["risk_level"],
                "volatility_score": insight["volatility_score"],
                "liquidity_depth": insight["liquidity_depth"],
                "whale_alert":     metrics.get("whale_alert", False),
                "last_updated":    metrics["last_updated"],
            },
            explanation=insight["explanation"],
            on_chain_ref=metrics.get("subgraph_url", "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"),
            warnings=insight.get("warnings", [])
        )

    # ── Tool 2 ──────────────────────────────
    async def analyze_swap_impact(
        self, token_from: str, token_to: str, amount: float
    ) -> dict:
        """
        Returns expected output, slippage %, best route, and safety warnings
        for a token swap on X Layer.
        """
        if not token_from or not token_to:
            return build_response(
                status="error",
                data={},
                explanation="Both token_from and token_to are required (e.g. 'USDC', 'ETH')."
            )

        if not isinstance(amount, (int, float)) or amount <= 0:
            return build_response(
                status="error",
                data={},
                explanation="Amount must be a positive number (e.g. 50.0)."
            )

        token_from = token_from.upper().strip()
        token_to   = token_to.upper().strip()

        swap_data = await self.fetcher.calculate_slippage(token_from, token_to, amount)

        if swap_data is None:
            return build_response(
                status="error",
                data={},
                explanation=f"No liquidity route found for {token_from} → {token_to}."
            )

        insight = self.engine.analyze_swap(swap_data, amount)

        return build_response(
            status="success",
            data={
                "token_from":         token_from,
                "token_to":           token_to,
                "amount_in":          amount,
                "expected_output":    round(swap_data["expected_output"], 6),
                "slippage_percent":   round(swap_data["slippage"], 3),
                "price_impact":       round(swap_data["price_impact"], 3),
                "gas_estimate_gwei":  swap_data["gas_gwei"],
                "best_route":         swap_data["route"],
                "fee_tier":           swap_data["fee_tier"],
                "execution_quality":  insight["execution_quality"],
            },
            explanation=insight["explanation"],
            on_chain_ref=swap_data.get("pool_ref", ""),
            warnings=insight.get("warnings", [])
        )

    # ── Tool 3 ──────────────────────────────
    async def get_beginner_recommendation(self, risk_tolerance: str) -> dict:
        """
        Returns the single best pool suggestion for beginners,
        tailored to their risk tolerance: LOW, MEDIUM, or HIGH.
        """
        valid = {"LOW", "MEDIUM", "HIGH"}
        risk_tolerance = risk_tolerance.upper().strip()

        if risk_tolerance not in valid:
            return build_response(
                status="error",
                data={},
                explanation="risk_tolerance must be 'LOW', 'MEDIUM', or 'HIGH'."
            )

        pools = await self.fetcher.fetch_all_pools()
        recommendation = self.engine.recommend_for_beginner(pools, risk_tolerance)

        return build_response(
            status="success",
            data={
                "recommended_pool":   recommendation["pool"],
                "risk_tolerance":     risk_tolerance,
                "expected_apy":       recommendation["apy"],
                "tvl_usd":            recommendation["tvl_usd"],
                "risk_level":         recommendation["risk_level"],
                "confidence_score":   recommendation["confidence"],
                "why_safe":           recommendation["why_safe"],
                "what_to_watch":      recommendation["watch_out"],
            },
            explanation=recommendation["explanation"],
            on_chain_ref=recommendation.get("ref", ""),
            warnings=recommendation.get("warnings", [])
        )


# ─────────────────────────────────────────────
# MCP Server Wiring (official SDK)
# ─────────────────────────────────────────────
def create_mcp_server(mock_mode: bool = True) -> "Server | None":
    if not MCP_AVAILABLE:
        logger.warning("MCP SDK not installed. Run: pip install mcp")
        return None

    server = Server("chainsight-mcp")
    tools  = ChainSightTools(mock_mode=mock_mode)

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="get_pool_health",
                description=(
                    "Analyze health of a Uniswap V3 pool on X Layer. "
                    "Returns APY, TVL, volatility score, and beginner-friendly risk summary."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pool_name": {
                            "type": "string",
                            "description": "Pool pair, e.g. 'USDC/ETH' or 'USDT/OKB'",
                        }
                    },
                    "required": ["pool_name"],
                },
            ),
            types.Tool(
                name="analyze_swap_impact",
                description=(
                    "Predict the outcome of a token swap on X Layer. "
                    "Returns expected output tokens, slippage %, best route, and gas cost."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "token_from": {"type": "string", "description": "Source token, e.g. 'USDC'"},
                        "token_to":   {"type": "string", "description": "Target token, e.g. 'ETH'"},
                        "amount":     {"type": "number", "description": "Amount to swap in USD"},
                    },
                    "required": ["token_from", "token_to", "amount"],
                },
            ),
            types.Tool(
                name="get_beginner_recommendation",
                description=(
                    "Get a single best pool recommendation for a beginner, "
                    "tailored to their risk tolerance (LOW / MEDIUM / HIGH)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "risk_tolerance": {
                            "type": "string",
                            "enum": ["LOW", "MEDIUM", "HIGH"],
                            "description": "Your risk comfort level",
                        }
                    },
                    "required": ["risk_tolerance"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        try:
            if name == "get_pool_health":
                result = await tools.get_pool_health(arguments.get("pool_name", ""))
            elif name == "analyze_swap_impact":
                result = await tools.analyze_swap_impact(
                    arguments.get("token_from", ""),
                    arguments.get("token_to", ""),
                    arguments.get("amount", 0),
                )
            elif name == "get_beginner_recommendation":
                result = await tools.get_beginner_recommendation(
                    arguments.get("risk_tolerance", "LOW")
                )
            else:
                result = {"status": "error", "explanation": f"Unknown tool: {name}"}
        except Exception as exc:
            logger.exception("Tool execution failed")
            result = {"status": "error", "explanation": str(exc)}

        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    return server


async def run_server(mock_mode: bool = True):
    server = create_mcp_server(mock_mode)
    if server is None:
        return
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="chainsight-mcp",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={}
                ),
            ),
        )


if __name__ == "__main__":
    import os
    mock = os.getenv("CHAINSIGHT_MOCK_MODE", "true").lower() == "true"
    asyncio.run(run_server(mock_mode=mock))