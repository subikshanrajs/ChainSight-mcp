"""
ChainSight – Test Suite
pytest tests for MCP tool responses, insight logic, and MCP compliance.
Run: pytest tests/ -v
"""

import asyncio
import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mcp_server   import ChainSightTools, build_response
from insight_engine import InsightEngine
from onchain_data   import OnChainDataFetcher, MOCK_POOLS, MOCK_PRICES


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────
@pytest.fixture
def tools():
    return ChainSightTools(mock_mode=True)

@pytest.fixture
def engine():
    return InsightEngine()

@pytest.fixture
def fetcher():
    return OnChainDataFetcher(mock_mode=True)


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ─────────────────────────────────────────────
# Response Schema Tests
# ─────────────────────────────────────────────
class TestResponseSchema:
    def test_build_response_success(self):
        r = build_response("success", {"key": "val"}, "All good")
        assert r["status"]      == "success"
        assert r["data"]        == {"key": "val"}
        assert r["explanation"] == "All good"
        assert "disclaimer"     in r
        assert "warnings"       in r

    def test_build_response_error(self):
        r = build_response("error", {}, "Something broke")
        assert r["status"] == "error"
        assert r["data"]   == {}

    def test_disclaimer_always_present(self):
        r = build_response("success", {}, "")
        assert "not financial advice" in r["disclaimer"].lower()

    def test_warnings_default_empty(self):
        r = build_response("success", {}, "")
        assert r["warnings"] == []

    def test_warnings_passthrough(self):
        r = build_response("success", {}, "", warnings=["⚠️ Watch out"])
        assert len(r["warnings"]) == 1


# ─────────────────────────────────────────────
# Tool 1: get_pool_health
# ─────────────────────────────────────────────
class TestGetPoolHealth:
    def test_valid_pool_returns_success(self, tools):
        r = run(tools.get_pool_health("USDC/ETH"))
        assert r["status"] == "success"
        assert r["data"]["pool"] == "USDC/ETH"

    def test_all_required_fields_present(self, tools):
        r = run(tools.get_pool_health("USDC/ETH"))
        required = [
            "pool", "apy_percent", "tvl_usd", "volume_24h_usd",
            "fee_tier", "risk_level", "volatility_score", "liquidity_depth",
            "last_updated",
        ]
        for field in required:
            assert field in r["data"], f"Missing field: {field}"

    def test_risk_level_valid_enum(self, tools):
        for pool in ["USDC/ETH", "USDT/OKB", "ETH/OKB", "USDC/USDT"]:
            r = run(tools.get_pool_health(pool))
            assert r["data"]["risk_level"] in ("LOW", "MEDIUM", "HIGH")

    def test_apy_is_positive_number(self, tools):
        r = run(tools.get_pool_health("USDC/ETH"))
        assert isinstance(r["data"]["apy_percent"], (int, float))
        assert r["data"]["apy_percent"] >= 0

    def test_tvl_is_positive(self, tools):
        r = run(tools.get_pool_health("USDC/ETH"))
        assert r["data"]["tvl_usd"] > 0

    def test_invalid_pool_returns_error(self, tools):
        r = run(tools.get_pool_health("FAKE/TOKEN"))
        assert r["status"] == "error"
        assert "not found" in r["explanation"].lower()

    def test_empty_pool_name_returns_error(self, tools):
        r = run(tools.get_pool_health(""))
        assert r["status"] == "error"

    def test_whitespace_pool_name_normalised(self, tools):
        r = run(tools.get_pool_health("  usdc/eth  "))
        assert r["status"] == "success"

    def test_lowercase_pool_name_normalised(self, tools):
        r = run(tools.get_pool_health("usdt/okb"))
        assert r["status"] == "success"

    def test_whale_alert_detected_for_usdt_okb(self, tools):
        r = run(tools.get_pool_health("USDT/OKB"))
        assert r["status"] == "success"
        assert r["data"]["whale_alert"] is True
        assert len(r["warnings"]) > 0

    def test_on_chain_ref_is_string(self, tools):
        r = run(tools.get_pool_health("USDC/ETH"))
        assert isinstance(r.get("on_chain_ref", ""), str)

    def test_explanation_is_non_empty_string(self, tools):
        r = run(tools.get_pool_health("USDC/ETH"))
        assert isinstance(r["explanation"], str)
        assert len(r["explanation"]) > 20

    def test_none_type_returns_error(self, tools):
        r = run(tools.get_pool_health(None))
        assert r["status"] == "error"


# ─────────────────────────────────────────────
# Tool 2: analyze_swap_impact
# ─────────────────────────────────────────────
class TestAnalyzeSwapImpact:
    def test_valid_swap_returns_success(self, tools):
        r = run(tools.analyze_swap_impact("USDC", "ETH", 50.0))
        assert r["status"] == "success"

    def test_all_required_fields_present(self, tools):
        r = run(tools.analyze_swap_impact("USDC", "ETH", 50.0))
        required = [
            "token_from", "token_to", "amount_in",
            "expected_output", "slippage_percent", "price_impact",
            "gas_estimate_gwei", "best_route", "fee_tier",
        ]
        for field in required:
            assert field in r["data"], f"Missing field: {field}"

    def test_expected_output_positive(self, tools):
        r = run(tools.analyze_swap_impact("USDC", "ETH", 100.0))
        assert r["data"]["expected_output"] > 0

    def test_slippage_in_reasonable_range(self, tools):
        r = run(tools.analyze_swap_impact("USDC", "ETH", 50.0))
        assert 0 <= r["data"]["slippage_percent"] <= 100

    def test_small_trade_lower_slippage(self, tools):
        small = run(tools.analyze_swap_impact("USDC", "ETH", 10.0))
        large = run(tools.analyze_swap_impact("USDC", "ETH", 100_000.0))
        if small["status"] == "success" and large["status"] == "success":
            assert small["data"]["slippage_percent"] <= large["data"]["slippage_percent"]

    def test_zero_amount_returns_error(self, tools):
        r = run(tools.analyze_swap_impact("USDC", "ETH", 0.0))
        assert r["status"] == "error"

    def test_negative_amount_returns_error(self, tools):
        r = run(tools.analyze_swap_impact("USDC", "ETH", -10.0))
        assert r["status"] == "error"

    def test_empty_token_returns_error(self, tools):
        r = run(tools.analyze_swap_impact("", "ETH", 50.0))
        assert r["status"] == "error"

    def test_gas_estimate_is_positive(self, tools):
        r = run(tools.analyze_swap_impact("USDC", "ETH", 50.0))
        assert r["data"]["gas_estimate_gwei"] > 0

    def test_stablecoin_pair_low_slippage(self, tools):
        r = run(tools.analyze_swap_impact("USDC", "USDT", 1000.0))
        if r["status"] == "success":
            assert r["data"]["slippage_percent"] < 2.0

    def test_execution_quality_valid_enum(self, tools):
        r = run(tools.analyze_swap_impact("USDC", "ETH", 50.0))
        assert r["data"]["execution_quality"] in (
            "Excellent", "Good", "Fair", "Poor"
        )


# ─────────────────────────────────────────────
# Tool 3: get_beginner_recommendation
# ─────────────────────────────────────────────
class TestGetBeginnerRecommendation:
    def test_low_risk_returns_success(self, tools):
        r = run(tools.get_beginner_recommendation("LOW"))
        assert r["status"] == "success"

    def test_medium_risk_returns_success(self, tools):
        r = run(tools.get_beginner_recommendation("MEDIUM"))
        assert r["status"] == "success"

    def test_high_risk_returns_success(self, tools):
        r = run(tools.get_beginner_recommendation("HIGH"))
        assert r["status"] == "success"

    def test_all_required_fields(self, tools):
        r = run(tools.get_beginner_recommendation("LOW"))
        required = [
            "recommended_pool", "risk_tolerance", "expected_apy",
            "tvl_usd", "risk_level", "confidence_score",
            "why_safe", "what_to_watch",
        ]
        for field in required:
            assert field in r["data"], f"Missing: {field}"

    def test_invalid_tolerance_returns_error(self, tools):
        r = run(tools.get_beginner_recommendation("EXTREME"))
        assert r["status"] == "error"

    def test_lowercase_tolerance_normalised(self, tools):
        r = run(tools.get_beginner_recommendation("low"))
        assert r["status"] == "success"

    def test_low_risk_pool_is_low_or_medium_risk(self, tools):
        r = run(tools.get_beginner_recommendation("LOW"))
        assert r["data"]["risk_level"] in ("LOW", "MEDIUM")

    def test_confidence_score_between_0_and_1(self, tools):
        r = run(tools.get_beginner_recommendation("MEDIUM"))
        c = r["data"]["confidence_score"]
        assert 0.0 <= c <= 1.0

    def test_apy_is_positive(self, tools):
        r = run(tools.get_beginner_recommendation("MEDIUM"))
        assert r["data"]["expected_apy"] >= 0

    def test_recommended_pool_exists_in_known_pools(self, tools):
        for tol in ["LOW", "MEDIUM", "HIGH"]:
            r = run(tools.get_beginner_recommendation(tol))
            pool = r["data"]["recommended_pool"]
            assert pool in MOCK_POOLS, f"Unknown pool recommended: {pool}"


# ─────────────────────────────────────────────
# Insight Engine Unit Tests
# ─────────────────────────────────────────────
class TestInsightEngine:
    def test_low_tvl_high_risk(self, engine):
        metrics = {**MOCK_POOLS["USDC/ETH"], "tvl_usd": 10_000, "apy": 5.0,
                   "hourly_vol_change": 0.02, "whale_alert": False}
        result = engine.analyze_pool(metrics)
        assert result["risk_level"] in ("MEDIUM", "HIGH")
        assert result["liquidity_depth"] == "Shallow"

    def test_high_tvl_low_risk(self, engine):
        metrics = {**MOCK_POOLS["USDC/USDT"], "tvl_usd": 9_000_000, "apy": 2.9,
                   "hourly_vol_change": 0.01, "whale_alert": False}
        result = engine.analyze_pool(metrics)
        assert result["risk_level"] == "LOW"
        assert result["liquidity_depth"] == "Deep"

    def test_very_high_apy_triggers_warning(self, engine):
        metrics = {**MOCK_POOLS["USDC/ETH"], "apy": 150.0,
                   "hourly_vol_change": 0.02, "whale_alert": False}
        result = engine.analyze_pool(metrics)
        assert any("very high" in w.lower() for w in result["warnings"])

    def test_whale_alert_adds_warning(self, engine):
        metrics = MOCK_POOLS["USDT/OKB"]
        result  = engine.analyze_pool(metrics)
        assert any("🐋" in w for w in result["warnings"])

    def test_explanation_is_non_empty(self, engine):
        result = engine.analyze_pool(MOCK_POOLS["USDC/ETH"])
        assert len(result["explanation"]) > 50

    def test_volatility_score_0_to_10(self, engine):
        for pool in MOCK_POOLS.values():
            r = engine.analyze_pool(pool)
            assert 0 <= r["volatility_score"] <= 10

    def test_swap_excellent_quality_low_slippage(self, engine):
        swap_data = {"slippage": 0.2, "price_impact": 0.1, "gas_gwei": 20,
                     "route": "Direct", "fee_tier": "0.05%"}
        r = engine.analyze_swap(swap_data, 50.0)
        assert r["execution_quality"] == "Excellent"

    def test_swap_poor_quality_high_slippage(self, engine):
        swap_data = {"slippage": 5.0, "price_impact": 4.0, "gas_gwei": 40,
                     "route": "Multi-hop", "fee_tier": "1%"}
        r = engine.analyze_swap(swap_data, 50.0)
        assert r["execution_quality"] == "Poor"
        assert len(r["warnings"]) > 0

    def test_recommend_low_risk_not_high_apy_pool(self, engine):
        r = engine.recommend_for_beginner(MOCK_POOLS, "LOW")
        # LOW risk should not recommend a >20% APY pool
        assert r["apy"] <= 20.0

    def test_recommend_high_risk_higher_apy(self, engine):
        low_rec  = engine.recommend_for_beginner(MOCK_POOLS, "LOW")
        high_rec = engine.recommend_for_beginner(MOCK_POOLS, "HIGH")
        # High risk should have same or higher APY than low risk
        assert high_rec["apy"] >= low_rec["apy"]

    def test_recommend_always_returns_pool(self, engine):
        for tol in ["LOW", "MEDIUM", "HIGH"]:
            r = engine.recommend_for_beginner(MOCK_POOLS, tol)
            assert "pool" in r
            assert r["pool"] != ""

    def test_recommend_confidence_0_to_1(self, engine):
        r = engine.recommend_for_beginner(MOCK_POOLS, "MEDIUM")
        assert 0.0 <= r["confidence"] <= 1.0


# ─────────────────────────────────────────────
# On-Chain Data Fetcher Tests
# ─────────────────────────────────────────────
class TestOnChainDataFetcher:
    def test_fetch_known_pool(self, fetcher):
        r = run(fetcher.fetch_pool_metrics("USDC/ETH"))
        assert r is not None
        assert r["tvl_usd"] > 0

    def test_fetch_unknown_pool_returns_none(self, fetcher):
        r = run(fetcher.fetch_pool_metrics("FAKE/COIN"))
        assert r is None

    def test_cache_returns_same_data(self, fetcher):
        r1 = run(fetcher.fetch_pool_metrics("USDC/ETH"))
        r2 = run(fetcher.fetch_pool_metrics("USDC/ETH"))
        assert r1 == r2

    def test_fetch_all_pools_returns_dict(self, fetcher):
        pools = run(fetcher.fetch_all_pools())
        assert isinstance(pools, dict)
        assert len(pools) >= 4

    def test_slippage_calc_returns_dict(self, fetcher):
        r = run(fetcher.calculate_slippage("USDC", "ETH", 50.0))
        assert r is not None
        assert "expected_output" in r
        assert "slippage" in r

    def test_slippage_output_positive(self, fetcher):
        r = run(fetcher.calculate_slippage("USDC", "ETH", 50.0))
        assert r["expected_output"] > 0

    def test_whale_movement_detected_usdt_okb(self, fetcher):
        r = run(fetcher.detect_whale_movement("USDT/OKB"))
        assert r["detected"] is True

    def test_whale_movement_not_detected_usdc_eth(self, fetcher):
        r = run(fetcher.detect_whale_movement("USDC/ETH"))
        assert r["detected"] is False

    def test_all_mock_pools_have_required_keys(self):
        required = ["apy", "tvl_usd", "volume_24h", "fee_tier", "last_updated"]
        for name, pool in MOCK_POOLS.items():
            for key in required:
                assert key in pool, f"Pool {name} missing key: {key}"


# ─────────────────────────────────────────────
# MCP Compliance Tests
# ─────────────────────────────────────────────
class TestMCPCompliance:
    """Verify responses follow the MCP tool output contract."""

    REQUIRED_TOP_LEVEL = {"status", "data", "explanation", "warnings", "disclaimer"}

    def _check_contract(self, result: dict):
        for key in self.REQUIRED_TOP_LEVEL:
            assert key in result, f"MCP response missing field: {key}"
        assert result["status"] in ("success", "error")
        assert isinstance(result["explanation"], str)
        assert isinstance(result["warnings"], list)
        assert isinstance(result["data"], dict)

    def test_pool_health_mcp_contract(self, tools):
        r = run(tools.get_pool_health("USDC/ETH"))
        self._check_contract(r)

    def test_swap_impact_mcp_contract(self, tools):
        r = run(tools.analyze_swap_impact("USDC", "ETH", 50.0))
        self._check_contract(r)

    def test_recommendation_mcp_contract(self, tools):
        r = run(tools.get_beginner_recommendation("LOW"))
        self._check_contract(r)

    def test_error_response_mcp_contract(self, tools):
        r = run(tools.get_pool_health("INVALID/POOL"))
        self._check_contract(r)
        assert r["status"] == "error"

    def test_json_serializable(self, tools):
        """All responses must be JSON-serializable."""
        for coro in [
            tools.get_pool_health("USDC/ETH"),
            tools.analyze_swap_impact("USDC", "ETH", 50.0),
            tools.get_beginner_recommendation("MEDIUM"),
        ]:
            r = run(coro)
            # Should not raise
            json.dumps(r)