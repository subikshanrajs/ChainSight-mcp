"""
ChainSight – Streamlit Demo Interface
Clean, beginner-friendly UI for querying all 3 MCP tools.
Optimised for screen recording and hackathon demos.
"""

import asyncio
import json
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import streamlit as st
from mcp_server import ChainSightTools

# ─────────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="ChainSight MCP",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;600&display=swap');

  html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
  }
  h1, h2, h3, .stMarkdown h1, .stMarkdown h2 {
    font-family: 'Space Mono', monospace;
  }

  /* Dark sidebar */
  section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1117 0%, #161b22 100%);
    border-right: 1px solid #30363d;
  }
  section[data-testid="stSidebar"] * { color: #e6edf3 !important; }

  /* Card style */
  .cs-card {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    font-family: 'DM Sans', sans-serif;
  }
  .cs-header {
    font-family: 'Space Mono', monospace;
    font-size: 0.78rem;
    color: #7d8590;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 0.4rem;
  }
  .cs-value {
    font-size: 1.4rem;
    font-weight: 600;
    color: #e6edf3;
  }
  .risk-LOW    { color: #3fb950; }
  .risk-MEDIUM { color: #d29922; }
  .risk-HIGH   { color: #f85149; }

  /* Status badges */
  .badge-success { background:#1a3c2a; color:#3fb950; padding:3px 10px; border-radius:20px; font-size:0.8rem; font-weight:600; }
  .badge-error   { background:#3c1a1a; color:#f85149; padding:3px 10px; border-radius:20px; font-size:0.8rem; font-weight:600; }
  .badge-warn    { background:#3c2d0a; color:#d29922; padding:3px 10px; border-radius:20px; font-size:0.8rem; font-weight:600; }

  /* JSON panel */
  .json-block {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 1rem;
    font-family: 'Space Mono', monospace;
    font-size: 0.78rem;
    color: #79c0ff;
    overflow-x: auto;
  }

  /* Main background */
  .main .block-container { background: #0a0e14; padding-top: 1.5rem; }

  /* Buttons */
  .stButton > button {
    background: linear-gradient(135deg, #238636, #1a7f37) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.85rem !important;
    padding: 0.6rem 1.4rem !important;
    transition: all 0.2s ease !important;
  }
  .stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(35, 134, 54, 0.4) !important;
  }

  /* Disclaimer */
  .disclaimer {
    border-left: 3px solid #d29922;
    background: #1c1a0e;
    padding: 0.6rem 1rem;
    border-radius: 0 6px 6px 0;
    font-size: 0.82rem;
    color: #d29922;
    margin-top: 1rem;
  }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Async helper
# ─────────────────────────────────────────────
def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔍 ChainSight")
    st.markdown("*On-chain Intelligence for Everyone*")
    st.divider()

    mock_mode = st.toggle("🧪 Test Mode (mock data)", value=True, help="Use mock data for demos — no API key needed")
    tools = ChainSightTools(mock_mode=mock_mode)

    st.divider()
    st.markdown("**🌐 Network**")
    st.markdown("`X Layer Testnet`")
    st.markdown("**Chain ID:** `195`")
    st.divider()
    st.markdown("**🔌 MCP Tools**")
    st.markdown("✅ `get_pool_health`")
    st.markdown("✅ `analyze_swap_impact`")
    st.markdown("✅ `get_beginner_recommendation`")
    st.divider()

    # Wallet info
    wallet_info = run_async(tools.wallet.get_balance())
    st.markdown("**🪙 Agentic Wallet**")
    st.code(tools.wallet.address[:20] + "...", language=None)
    st.markdown(f"Balance: `{wallet_info['balance']:.4f} OKB`")
    st.markdown(f"[View on Explorer ↗](https://www.okx.com/explorer/xlayer-test)")


# ─────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────
st.markdown("""
<div style="background:linear-gradient(135deg,#0d1117,#161b22);border:1px solid #30363d;
     border-radius:16px;padding:2rem;margin-bottom:1.5rem;text-align:center">
  <h1 style="font-family:'Space Mono',monospace;color:#e6edf3;margin:0;font-size:2rem">
    🔍 ChainSight MCP
  </h1>
  <p style="color:#7d8590;margin:0.5rem 0 0;font-size:1rem">
    On-chain data analyst skill · X Layer + Uniswap V3 · Beginner-friendly insights
  </p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "🏊 Pool Health",
    "🔄 Swap Impact",
    "🎯 Beginner Rec",
    "⛓️ Multi-Tool Demo",
])


# ── TAB 1: Pool Health ───────────────────────
with tab1:
    st.markdown("### 🏊 Pool Health Analyser")
    st.markdown("Get a complete health check on any X Layer / Uniswap V3 pool.")

    col1, col2 = st.columns([2, 1])
    with col1:
        pool_name = st.selectbox(
            "Select Pool", ["USDC/ETH", "USDT/OKB", "ETH/OKB", "USDC/USDT"],
            help="Pick a liquidity pool to analyse"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run_pool = st.button("🔍 Analyse Pool", key="btn_pool")

    if run_pool:
        with st.spinner("Fetching on-chain data..."):
            result = run_async(tools.get_pool_health(pool_name))

        status = result.get("status", "error")
        badge  = '<span class="badge-success">✅ success</span>' if status == "success" else '<span class="badge-error">❌ error</span>'
        st.markdown(f"**Status:** {badge}", unsafe_allow_html=True)

        if status == "success":
            d = result["data"]
            risk = d.get("risk_level", "MEDIUM")

            # Metric cards
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("APY", f"{d['apy_percent']}%")
            c2.metric("TVL", f"${d['tvl_usd']/1_000_000:.2f}M")
            c3.metric("24h Volume", f"${d['volume_24h_usd']/1_000:.0f}K")
            c4.metric("Risk", risk, delta=None)

            # Explanation
            st.markdown(f"""
<div class="cs-card">
  <div class="cs-header">AI Explanation</div>
  <div style="color:#c9d1d9;line-height:1.7">{result['explanation'].replace(chr(10), '<br>')}</div>
</div>""", unsafe_allow_html=True)

            # Warnings
            if result.get("warnings"):
                for w in result["warnings"]:
                    st.warning(w)

            # On-chain ref
            if result.get("on_chain_ref"):
                st.markdown(f"🔗 [Verify on Subgraph]({result['on_chain_ref']})")

        # Raw JSON
        with st.expander("📦 Raw MCP Response (JSON)"):
            st.markdown(f'<div class="json-block">{json.dumps(result, indent=2)}</div>', unsafe_allow_html=True)

        # Disclaimer
        st.markdown('<div class="disclaimer">⚠️ This is data analysis only — not financial advice.</div>', unsafe_allow_html=True)


# ── TAB 2: Swap Impact ───────────────────────
with tab2:
    st.markdown("### 🔄 Swap Impact Analyser")
    st.markdown("Predict the outcome of your swap *before* you execute it.")

    c1, c2, c3 = st.columns(3)
    with c1:
        token_from = st.selectbox("From Token", ["USDC", "USDT", "ETH", "OKB"], key="swap_from")
    with c2:
        token_to = st.selectbox("To Token", ["ETH", "USDC", "OKB", "USDT"], key="swap_to")
    with c3:
        amount = st.number_input("Amount (USD)", min_value=1.0, max_value=1_000_000.0, value=50.0, step=10.0)

    run_swap = st.button("🔄 Analyse Swap", key="btn_swap")

    if run_swap:
        if token_from == token_to:
            st.error("Token From and Token To must be different.")
        else:
            with st.spinner("Calculating swap impact..."):
                result = run_async(tools.analyze_swap_impact(token_from, token_to, amount))

            status = result.get("status", "error")
            badge  = '<span class="badge-success">✅ success</span>' if status == "success" else '<span class="badge-error">❌ error</span>'
            st.markdown(f"**Status:** {badge}", unsafe_allow_html=True)

            if status == "success":
                d = result["data"]
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Expected Output", f"{d['expected_output']:.6f} {token_to}")
                c2.metric("Slippage", f"{d['slippage_percent']:.3f}%")
                c3.metric("Price Impact", f"{d['price_impact']:.3f}%")
                c4.metric("Quality", d.get("execution_quality", "—"))

                st.markdown(f"""
<div class="cs-card">
  <div class="cs-header">AI Explanation</div>
  <div style="color:#c9d1d9;line-height:1.7">{result['explanation'].replace(chr(10), '<br>')}</div>
</div>""", unsafe_allow_html=True)

                st.info(f"⛽ Gas estimate: ~{d['gas_estimate_gwei']} gwei on X Layer\n\n🛤️ Route: {d['best_route']}")

                for w in result.get("warnings", []):
                    st.warning(w)

            with st.expander("📦 Raw MCP Response (JSON)"):
                st.markdown(f'<div class="json-block">{json.dumps(result, indent=2)}</div>', unsafe_allow_html=True)

            st.markdown('<div class="disclaimer">⚠️ This is data analysis only — not financial advice.</div>', unsafe_allow_html=True)


# ── TAB 3: Beginner Recommendation ──────────
with tab3:
    st.markdown("### 🎯 Beginner Pool Recommendation")
    st.markdown("Tell me your risk comfort level and I'll find your best pool.")

    risk_labels = {
        "LOW – Safety first (stablecoins, slow & steady)":    "LOW",
        "MEDIUM – Balanced (some risk, decent returns)":      "MEDIUM",
        "HIGH – Thrill seeker (max APY, higher volatility)":  "HIGH",
    }
    choice = st.radio("My risk tolerance is:", list(risk_labels.keys()), key="risk_radio")
    risk_tolerance = risk_labels[choice]

    run_rec = st.button("🎯 Get My Recommendation", key="btn_rec")

    if run_rec:
        with st.spinner("Analysing all pools for you..."):
            result = run_async(tools.get_beginner_recommendation(risk_tolerance))

        if result.get("status") == "success":
            d = result["data"]
            risk = d.get("risk_level", "MEDIUM")

            st.markdown(f"""
<div class="cs-card" style="border-color:{'#238636' if risk=='LOW' else '#d29922' if risk=='MEDIUM' else '#f85149'}">
  <div class="cs-header">Recommended Pool</div>
  <div class="cs-value">{d['recommended_pool']}</div>
  <div style="margin-top:0.8rem;display:flex;gap:1rem;flex-wrap:wrap">
    <span style="color:#79c0ff">APY: {d['expected_apy']}%</span>
    <span style="color:#7d8590">|</span>
    <span style="color:#79c0ff">TVL: ${d['tvl_usd']/1_000_000:.2f}M</span>
    <span style="color:#7d8590">|</span>
    <span class="risk-{risk}">{risk} RISK</span>
    <span style="color:#7d8590">|</span>
    <span style="color:#c9d1d9">Confidence: {d['confidence_score']*100:.0f}%</span>
  </div>
</div>""", unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
<div class="cs-card">
  <div class="cs-header">✅ Why It's Safe</div>
  <div style="color:#c9d1d9">{d['why_safe']}</div>
</div>""", unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
<div class="cs-card">
  <div class="cs-header">👀 What To Watch</div>
  <div style="color:#c9d1d9">{d['what_to_watch']}</div>
</div>""", unsafe_allow_html=True)

            st.markdown(f"""
<div class="cs-card">
  <div class="cs-header">Full Explanation</div>
  <div style="color:#c9d1d9;line-height:1.7">{result['explanation'].replace(chr(10), '<br>')}</div>
</div>""", unsafe_allow_html=True)

            for w in result.get("warnings", []):
                st.warning(w)

        with st.expander("📦 Raw MCP Response (JSON)"):
            st.markdown(f'<div class="json-block">{json.dumps(result, indent=2)}</div>', unsafe_allow_html=True)

        st.markdown('<div class="disclaimer">⚠️ This is data analysis only — not financial advice.</div>', unsafe_allow_html=True)


# ── TAB 4: Multi-Tool Demo ───────────────────
with tab4:
    st.markdown("### ⛓️ Multi-Tool Chaining Demo")
    st.markdown(
        "Watch ChainSight chain three tools together:\n"
        "`get_pool_health` → `analyze_swap_impact` → `get_beginner_recommendation`"
    )

    demo_pool   = st.selectbox("Demo Pool", ["USDC/ETH", "USDT/OKB", "ETH/OKB"], key="demo_pool")
    demo_amount = st.slider("Swap Amount (USD)", 10, 5000, 100, step=10)
    run_chain   = st.button("🚀 Run Full Chain", key="btn_chain")

    if run_chain:
        progress = st.progress(0, text="Step 1/3 — Checking pool health...")
        result1 = run_async(tools.get_pool_health(demo_pool))
        progress.progress(33, text="Step 2/3 — Analysing swap impact...")

        tokens = demo_pool.split("/")
        result2 = run_async(tools.analyze_swap_impact(tokens[0], tokens[1], demo_amount))
        progress.progress(66, text="Step 3/3 — Getting beginner recommendation...")

        # Infer risk tolerance from pool health
        risk_map = {"LOW": "LOW", "MEDIUM": "MEDIUM", "HIGH": "HIGH"}
        inferred = risk_map.get(result1.get("data", {}).get("risk_level", "MEDIUM"), "MEDIUM")
        result3 = run_async(tools.get_beginner_recommendation(inferred))
        progress.progress(100, text="✅ Analysis complete!")

        st.divider()

        # Step 1 summary
        with st.container():
            st.markdown("#### 1️⃣ Pool Health")
            if result1.get("status") == "success":
                d = result1["data"]
                col1, col2, col3 = st.columns(3)
                col1.metric("APY", f"{d['apy_percent']}%")
                col2.metric("TVL", f"${d['tvl_usd']/1_000_000:.2f}M")
                col3.metric("Risk", d["risk_level"])

        st.divider()

        # Step 2 summary
        with st.container():
            st.markdown("#### 2️⃣ Swap Impact")
            if result2.get("status") == "success":
                d = result2["data"]
                col1, col2, col3 = st.columns(3)
                col1.metric("Expected Out", f"{d['expected_output']:.5f} {tokens[1]}")
                col2.metric("Slippage", f"{d['slippage_percent']:.3f}%")
                col3.metric("Quality", d.get("execution_quality", "—"))

        st.divider()

        # Step 3 summary
        with st.container():
            st.markdown("#### 3️⃣ Recommendation")
            if result3.get("status") == "success":
                d = result3["data"]
                st.markdown(f"""
<div class="cs-card">
  <div class="cs-header">Best Pool for You</div>
  <div class="cs-value" style="font-size:1.2rem">{d['recommended_pool']} — {d['expected_apy']}% APY</div>
  <div style="color:#7d8590;margin-top:0.5rem">{d['why_safe']}</div>
</div>""", unsafe_allow_html=True)

        # Full JSON collapsibles
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            with st.expander("Pool Health JSON"):
                st.json(result1)
        with col_b:
            with st.expander("Swap Impact JSON"):
                st.json(result2)
        with col_c:
            with st.expander("Recommendation JSON"):
                st.json(result3)

        st.markdown('<div class="disclaimer">⚠️ This is data analysis only — not financial advice.</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────
st.divider()
st.markdown(
    '<p style="text-align:center;color:#484f58;font-size:0.8rem;font-family:Space Mono,monospace">'
    'ChainSight MCP v1.0.0 · Built for X Layer Hackathon · '
    '<a href="https://github.com/your-org/chainsight-mcp" style="color:#58a6ff">GitHub</a>'
    '</p>',
    unsafe_allow_html=True
)