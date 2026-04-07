"""
ChainSight – Insight Engine
Converts raw on-chain numbers into beginner-friendly explanations
with risk scoring, safety disclaimers, and actionable summaries.
"""

import logging
from typing import Optional

logger = logging.getLogger("chainsight.insight")

# ─────────────────────────────────────────────
# Risk Thresholds
# ─────────────────────────────────────────────
TVL_HIGH   = 3_000_000   # >$3M TVL → well-established pool
TVL_MEDIUM = 500_000     # $500K–$3M  → moderate
                          # <$500K     → low liquidity / risky

VOL_CHANGE_HIGH   = 0.15  # >15% hourly swing → volatile
VOL_CHANGE_MEDIUM = 0.06  # 6-15%             → moderate
                           # <6%              → stable

APY_VERY_HIGH = 30.0      # >30% → likely unsustainable / high risk
APY_HIGH      = 15.0      # 15-30% → elevated risk
APY_LOW       = 4.0       # <4% → stable, conservative


# ─────────────────────────────────────────────
# Insight Engine
# ─────────────────────────────────────────────
class InsightEngine:
    """
    Translates numeric on-chain metrics into human-readable insights.
    All outputs include:
      - risk_level: LOW | MEDIUM | HIGH
      - explanation: plain-English summary (no jargon, or jargon explained)
      - warnings: list of actionable caution flags
    """

    # ── Pool Analysis ────────────────────────

    def analyze_pool(self, metrics: dict) -> dict:
        """Score and explain a pool's health."""
        tvl             = metrics.get("tvl_usd", 0)
        apy             = metrics.get("apy", 0)
        vol_change      = metrics.get("hourly_vol_change", 0)
        whale_alert     = metrics.get("whale_alert", False)
        recent_tx       = metrics.get("recent_large_tx")
        fee_tier        = metrics.get("fee_tier", "0.3%")

        warnings: list[str] = []
        risk_points = 0

        # ── Liquidity depth ─────────────────
        if tvl >= TVL_HIGH:
            liquidity_depth = "Deep"
            liq_note        = f"${tvl/1_000_000:.1f}M in the pool means your trade won't move the price much"
        elif tvl >= TVL_MEDIUM:
            liquidity_depth = "Moderate"
            liq_note        = f"${tvl/1_000_000:.2f}M TVL — decent liquidity, but larger trades may see slippage"
            risk_points    += 1
        else:
            liquidity_depth = "Shallow"
            liq_note        = f"Only ${tvl/1_000:.0f}K in this pool — small trades could move prices significantly"
            risk_points    += 3
            warnings.append(f"⚠️ Low TVL (${tvl:,.0f}) — high slippage risk for large trades")

        # ── APY check ───────────────────────
        if apy > APY_VERY_HIGH:
            risk_points += 3
            warnings.append(
                f"🚨 Very high APY ({apy}%) often signals impermanent loss risk or unsustainable rewards"
            )
        elif apy > APY_HIGH:
            risk_points += 1
            warnings.append(f"⚠️ APY {apy}% is above average — higher reward usually means higher risk")
        apy_note = f"Earning ~{apy}% annually means $1,000 invested could earn ~${apy * 10:.0f}/yr in fees"

        # ── Volatility ──────────────────────
        if vol_change > VOL_CHANGE_HIGH:
            risk_points += 2
            volatility_score = 8
            warnings.append(
                f"⚠️ Price moved {vol_change*100:.0f}% in the last hour — this pool is volatile right now"
            )
        elif vol_change > VOL_CHANGE_MEDIUM:
            risk_points += 1
            volatility_score = 5
        else:
            volatility_score = 2

        # ── Whale alert ─────────────────────
        if whale_alert and recent_tx:
            t = recent_tx
            risk_points += 2
            if t["type"] == "withdraw":
                warnings.append(
                    f"🐋 Large withdrawal of ${t['amount_usd']:,} spotted {t['age_minutes']}min ago — "
                    "liquidity dropped; wait for stability"
                )
            else:
                warnings.append(
                    f"🐋 Large deposit of ${t['amount_usd']:,} detected — pool may rebalance soon"
                )

        # ── Final risk level ─────────────────
        if risk_points <= 1:
            risk_level = "LOW"
            emoji      = "✅"
            summary    = "This pool looks healthy and stable for most users"
        elif risk_points <= 4:
            risk_level = "MEDIUM"
            emoji      = "⚠️"
            summary    = "This pool is reasonably solid, but keep an eye on it"
        else:
            risk_level = "HIGH"
            emoji      = "🚨"
            summary    = "This pool has multiple risk factors — proceed with caution"

        explanation = (
            f"{emoji} **{risk_level} RISK** — {summary}.\n\n"
            f"📊 Liquidity: {liq_note}.\n"
            f"💰 Returns: {apy_note}.\n"
            f"📉 Volatility score: {volatility_score}/10 — "
            + ("calm and steady" if volatility_score <= 3 else
               "moderate movement" if volatility_score <= 6 else "highly active")
            + f".\n💸 Fee tier: {fee_tier} — "
            + ("very low fees, ideal for stablecoin swaps" if "0.01%" in fee_tier else
               "standard fee — good for most pairs" if "0.05%" in fee_tier else
               "higher fee — trades are less frequent but earn more per swap")
            + "."
        )

        return {
            "risk_level":       risk_level,
            "volatility_score": volatility_score,
            "liquidity_depth":  liquidity_depth,
            "explanation":      explanation,
            "warnings":         warnings,
        }

    # ── Swap Analysis ────────────────────────

    def analyze_swap(self, swap_data: dict, amount_usd: float) -> dict:
        """Evaluate a swap's quality and flag issues."""
        slippage     = swap_data.get("slippage", 0)
        price_impact = swap_data.get("price_impact", 0)
        gas_gwei     = swap_data.get("gas_gwei", 30)
        warnings: list[str] = []

        # Slippage classification
        if slippage < 0.5:
            quality   = "Excellent"
            slip_note = f"Only {slippage:.2f}% slippage — you'll get almost exactly the displayed price"
        elif slippage < 1.5:
            quality   = "Good"
            slip_note = f"{slippage:.2f}% slippage is normal and acceptable for this trade size"
        elif slippage < 3.0:
            quality   = "Fair"
            slip_note = f"{slippage:.2f}% slippage is noticeable — consider splitting into smaller trades"
            warnings.append(f"⚠️ Slippage {slippage:.2f}% — set your wallet slippage tolerance to ~{slippage+0.5:.1f}%")
        else:
            quality   = "Poor"
            slip_note = f"High slippage ({slippage:.2f}%) — this trade could cost significantly more than expected"
            warnings.append(f"🚨 Slippage {slippage:.2f}% is very high — try a smaller amount or a deeper pool")

        # Price impact
        if price_impact > 1.0:
            warnings.append(
                f"📉 Your ${amount_usd:,.0f} trade moves the market price by ~{price_impact:.2f}% "
                "— consider splitting the swap"
            )

        # Gas sanity check
        gas_usd_estimate = (gas_gwei * 21_000 * 1e-9) * 3_210  # rough ETH price
        gas_note = (
            f"Gas cost is very low (~${gas_usd_estimate:.2f}) on X Layer"
            if gas_gwei < 30 else
            f"Gas: ~{gas_gwei} gwei (~${gas_usd_estimate:.2f})"
        )

        explanation = (
            f"🔄 Swap quality: **{quality}**\n\n"
            f"📊 {slip_note}.\n"
            f"⛽ {gas_note}.\n"
            f"✅ Best route: {swap_data.get('route', 'Direct swap')}.\n\n"
            "💡 Tip: Always set a slippage tolerance in your wallet to protect against "
            "price changes during confirmation."
        )

        return {
            "execution_quality": quality,
            "explanation":       explanation,
            "warnings":          warnings,
        }

    # ── Beginner Recommendation ──────────────

    def recommend_for_beginner(
        self, pools: dict[str, dict], risk_tolerance: str
    ) -> dict:
        """
        Pick the single best pool for a beginner given their risk tolerance.

        Scoring weights (total 100):
          - APY fit to tolerance: 35
          - Liquidity safety:     35
          - Volatility penalty:   -20
          - Whale alert penalty:  -10
        """
        TOLERANCE_APY_RANGE = {
            "LOW":    (0,    6),
            "MEDIUM": (6,    16),
            "HIGH":   (16,   100),
        }

        best_pool  = None
        best_score = -9999
        best_meta  = {}

        apy_min, apy_max = TOLERANCE_APY_RANGE[risk_tolerance]

        for name, m in pools.items():
            apy             = m.get("apy", 0)
            tvl             = m.get("tvl_usd", 0)
            vol_change      = m.get("hourly_vol_change", 0.05)
            whale           = m.get("whale_alert", False)

            score = 0

            # APY fit
            if apy_min <= apy <= apy_max:
                score += 35
            elif apy < apy_min:
                score += 35 - (apy_min - apy) * 5   # penalise for being below range
            else:
                score += 35 - (apy - apy_max) * 3   # penalise excess risk

            # Liquidity safety
            if tvl >= TVL_HIGH:
                score += 35
            elif tvl >= TVL_MEDIUM:
                score += 20
            else:
                score += 5

            # Volatility penalty
            score -= int(vol_change * 100)   # 0.15 → -15

            # Whale penalty
            if whale:
                score -= 15

            if score > best_score:
                best_score = score
                best_pool  = name
                best_meta  = m

        if best_pool is None:
            return {
                "pool": "USDC/USDT",
                "apy":  2.9,
                "tvl_usd": 9_100_000,
                "risk_level": "LOW",
                "confidence": 0.85,
                "explanation": "✅ USDC/USDT is the safest choice — both tokens hold $1.00.",
                "why_safe": "Both tokens are stablecoins — no big price swings.",
                "watch_out": "Very low APY (~2.9%) — not for high-growth seekers.",
                "warnings": [],
                "ref": "",
            }

        insight    = self.analyze_pool(best_meta)
        confidence = min(0.95, best_score / 100)

        # Risk-specific narrative
        if risk_tolerance == "LOW":
            why_safe = (
                "This pool prioritises capital preservation. "
                "Stablecoin pairs or major tokens mean your deposit value won't swing wildly."
            )
            watch_out = "Lower APY is the trade-off for safety — you won't get rich quick, but you won't lose sleep either."
        elif risk_tolerance == "MEDIUM":
            why_safe = (
                "Good balance of returns and safety. "
                f"${best_meta.get('tvl_usd', 0)/1_000_000:.1f}M in the pool "
                "means plenty of liquidity for your trade."
            )
            watch_out = (
                "Keep an eye on APY — if it spikes or drops sharply, "
                "re-check the pool health before adding more funds."
            )
        else:
            why_safe  = "Higher APY comes with higher risk — this pool suits users comfortable with volatility."
            watch_out = "Monitor this pool daily. High APY can disappear quickly if liquidity shifts."

        explanation = (
            f"{'✅' if insight['risk_level'] == 'LOW' else '⚠️' if insight['risk_level'] == 'MEDIUM' else '🚨'} "
            f"**Best match for {risk_tolerance} risk: {best_pool}**\n\n"
            f"💰 APY: ~{best_meta.get('apy', 0)}% | "
            f"💦 TVL: ${best_meta.get('tvl_usd', 0)/1_000_000:.2f}M | "
            f"🔒 Risk: {insight['risk_level']}\n\n"
            f"Why this pool? {why_safe}\n\n"
            f"Watch out: {watch_out}"
        )

        return {
            "pool":       best_pool,
            "apy":        best_meta.get("apy", 0),
            "tvl_usd":    best_meta.get("tvl_usd", 0),
            "risk_level": insight["risk_level"],
            "confidence": round(confidence, 2),
            "explanation": explanation,
            "why_safe":   why_safe,
            "watch_out":  watch_out,
            "warnings":   insight.get("warnings", []),
            "ref":        best_meta.get("subgraph_url", ""),
        }