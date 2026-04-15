# 🔍 ChainSight MCP Skill

> *On-chain data analyst skill for X Layer + Uniswap V3 — beginner-friendly, MCP-compliant, AI-agent ready.*

[![Tests](https://img.shields.io/badge/tests-passing-3fb950)](#-running-tests)
[![MCP](https://img.shields.io/badge/MCP-compliant-79c0ff)](#-mcp-tools)
[![Network](https://img.shields.io/badge/X%20Layer-Testnet-d29922)](#-deployment-address)
[![License](https://img.shields.io/badge/license-MIT-7d8590)](LICENSE)

---

## 📖 Project Intro

ChainSight is a **reusable MCP-compliant data analyst skill** that turns X Layer on-chain activity and Uniswap V3 pool metrics into **beginner-friendly, actionable insights** for AI agents.

**The problem it solves:** DeFi is overwhelming. Before making a swap or adding liquidity, users must check APY dashboards, slippage calculators, liquidity trackers, and whale movement alerts — across 5+ different tools. ChainSight consolidates all of this into 3 standardized MCP tools that any AI agent can call in seconds.

**Who it's for:** AI agents (Eliza, CrewAI, custom bots), DeFi beginners, and developers building on-chain tooling for the X Layer ecosystem.

---

## 🏗️ Architecture Overview

```
AI Agent / Streamlit UI
        │  MCP (stdio)
        ▼
ChainSight MCP Server  (src/mcp_server.py)
  ├── get_pool_health
  ├── analyze_swap_impact
  └── get_beginner_recommendation
        │
  ┌─────┴──────────────────────┐
  ▼                            ▼
OnChain Data Layer         Insight Engine
(src/onchain_data.py)      (src/insight_engine.py)
  │                            │
  ├── X Layer Testnet RPC      ├── Risk scoring (LOW/MEDIUM/HIGH)
  ├── Uniswap V3 Subgraph      ├── APY calculation
  ├── Mock mode (demo safe)    ├── Plain-English explanations
  └── 30s TTL cache            └── Beginner recommendations
                                        │
                               Agentic Wallet
                               (src/agentic_wallet.py)
                                 ├── X Layer Testnet EOA
                                 ├── Receive micro-tips
                                 ├── Sign data payloads
                                 └── Activity logging
```

- **MCP Server** exposes 3 standardized tools (stdio transport)
- **On-chain data layer** fetches X Layer + Uniswap V3 metrics (mock or live)
- **Insight engine** converts raw numbers into plain-English risk/APY reports
- **Agentic Wallet** provides on-chain identity + tip reception on X Layer Testnet
- **Streamlit UI** enables 1-click querying + hackathon demo recording

Full architecture diagram: [docs/architecture.md](docs/architecture.md)

---

## 🌐 Deployment Address

| Component | Value |
|---|---|
| **Agentic Wallet (X Layer Testnet)** | `0x0000000000000000000000000000000000000000` *(replace after deployment)* |
| **Network** | X Layer Testnet (Chain ID: 195) |
| **Explorer** | https://www.okx.com/explorer/xlayer-test |
| **Subgraph Endpoint** | https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3 |
| **MCP Server (local)** | `http://localhost:8080` |
| **Faucet** | https://www.okx.com/xlayer/faucet |

> To deploy your own wallet: `bash scripts/deploy_wallet.sh`

---

## 🔌 Onchain OS / Uniswap Skill Usage

### Onchain OS Integration
- **Pattern used:** `mcp-data-query` — standardized data indexing & caching
- `OnChainDataFetcher` implements OS-standard TTL caching (30s), retry logic (3×), and environment-driven mock/live switching
- `detect_whale_movement()` mirrors the OS anomaly-detection pattern
- See: `# Onchain OS Integration` comments in `src/onchain_data.py`

### Uniswap V3 Integration
- **Pattern used:** `pool-analytics` skill architecture
- `calculate_slippage()` implements constant-product AMM slippage model
- `_calculate_apy()` uses 7-day fee averaging (industry-standard method)
- GraphQL queries use official Uniswap V3 Subgraph schema
- Fee tier mapping: 100 (0.01%) / 500 (0.05%) / 3000 (0.3%) / 10000 (1%)
- See: `# Uniswap Integration` comments in `src/onchain_data.py`

### Multi-Tool Chaining
The Streamlit **Multi-Tool Demo** tab chains all 3 tools:
```
get_pool_health → analyze_swap_impact → get_beginner_recommendation
```
This demonstrates real-world AI agent orchestration where each tool's output informs the next.

---

## ⚙️ Working Mechanics

1. **User or AI agent** calls an MCP tool with parameters (e.g. `get_pool_health("USDC/ETH")`)
2. **Input validation** — parameters are sanitized and normalized (uppercase, strip whitespace)
3. **Data layer** fetches real-time or mock X Layer / Uniswap V3 metrics (with 30s TTL cache)
4. **Insight engine** calculates risk score, APY, slippage, and liquidity depth
5. **Response** is returned as structured JSON + plain-English explanation + on-chain verification link
6. **Optional:** Agentic wallet receives micro-tips for premium queries; signs data for tamper-proof attestation

### Response Schema (all tools)
```json
{
  "status":       "success | error",
  "data":         { ... tool-specific fields ... },
  "explanation":  "Plain-English summary of findings",
  "on_chain_ref": "https://... subgraph or explorer link",
  "warnings":     ["⚠️ Actionable caution flags"],
  "disclaimer":   "⚠️ This is data analysis only — not financial advice."
}
```

---

## 🔧 MCP Tools

### `get_pool_health(pool_name: str)`
Returns APY, TVL, fee tier, volatility score, and risk level for an X Layer pool.

```json
// Request
{ "pool_name": "USDC/ETH" }

// Response
{
  "status": "success",
  "data": {
    "pool": "USDC/ETH",
    "apy_percent": 7.2,
    "tvl_usd": 4800000,
    "volume_24h_usd": 320000,
    "fee_tier": "0.05%",
    "risk_level": "LOW",
    "volatility_score": 2,
    "liquidity_depth": "Deep",
    "whale_alert": false
  },
  "explanation": "✅ LOW RISK — This pool looks healthy and stable..."
}
```

### `analyze_swap_impact(token_from, token_to, amount)`
Predicts swap output, slippage, price impact, best route, and gas cost.

```json
// Request
{ "token_from": "USDC", "token_to": "ETH", "amount": 50 }

// Response
{
  "data": {
    "expected_output": 0.015569,
    "slippage_percent": 0.102,
    "price_impact": 0.001,
    "gas_estimate_gwei": 20,
    "best_route": "Uniswap V3: USDC → ETH (0.05% pool)",
    "execution_quality": "Excellent"
  }
}
```

### `get_beginner_recommendation(risk_tolerance: "LOW"|"MEDIUM"|"HIGH")`
Returns the single best pool for a beginner with plain-English rationale.

```json
// Request
{ "risk_tolerance": "LOW" }

// Response
{
  "data": {
    "recommended_pool": "USDC/USDT",
    "expected_apy": 2.9,
    "tvl_usd": 9100000,
    "risk_level": "LOW",
    "confidence_score": 0.91,
    "why_safe": "Both tokens are stablecoins — no big price swings.",
    "what_to_watch": "Very low APY — not for high-growth seekers."
  }
}
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- (Optional) X Layer Testnet OKB for wallet features

### 1. Install

```bash
git clone https://github.com/your-org/chainsight-mcp.git
cd chainsight-mcp
pip install -e ".[dev]"
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — set CHAINSIGHT_MOCK_MODE=true for demo (no API key needed)
```

### 3. Run the Streamlit UI

```bash
streamlit run ui/app.py
# Opens http://localhost:8501
```

### 4. Run the MCP Server

```bash
bash scripts/run_mcp_server.sh
# MCP server starts in stdio mode — connect with any MCP client
```

### 5. Setup Agentic Wallet (optional)

```bash
bash scripts/deploy_wallet.sh
# Generates EOA, writes to .env, provides faucet link
```

---

## 🧪 Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Specific test class
pytest tests/test_mcp_tools.py::TestGetPoolHealth -v
```

**Test coverage includes:**
- ✅ MCP response schema compliance (all 3 tools)
- ✅ Valid + invalid inputs for every tool
- ✅ Risk scoring logic (LOW/MEDIUM/HIGH)
- ✅ Slippage & APY calculation accuracy
- ✅ Whale detection
- ✅ Cache behaviour
- ✅ JSON serialization of all responses
- ✅ Mock data integrity

---

## 📁 Project Structure

```
chainsight-mcp/
├── src/
│   ├── mcp_server.py       # MCP tool definitions & routing
│   ├── onchain_data.py     # X Layer + Uniswap data fetchers
│   ├── agentic_wallet.py   # Wallet manager (X Layer Testnet)
│   └── insight_engine.py   # Data → plain-English + risk scoring
├── ui/
│   └── app.py              # Streamlit demo interface
├── tests/
│   └── test_mcp_tools.py   # Full test suite (50+ tests)
├── scripts/
│   ├── deploy_wallet.sh    # Wallet creation & faucet helper
│   └── run_mcp_server.sh   # MCP server launcher
├── docs/
│   ├── architecture.md     # System diagram & data flow
│   └── demo_script.md      # 60-90s video recording guide
├── .env.example            # Environment variable template
├── pyproject.toml          # Dependencies + MCP manifest
└── README.md               # This file
```

---

## 👥 Team Members

- Subikshan Raj — Lead Developer / AI Agent Architecture / MCP Integration
               
---

## 🌍 Project Positioning in X Layer Ecosystem

ChainSight lowers the barrier to entry for X Layer DeFi by translating complex on-chain data into simple, verifiable insights. It:

- **Empowers beginners** — No charts, no jargon, just clear answers with actionable warnings
- **Accelerates AI agents** — Any MCP-compatible agent gains crypto intelligence in one `pip install`
- **Reduces failed transactions** — Slippage and price impact checks before any swap
- **Promotes transparency** — Every insight links to public on-chain data the user can verify
- **Integrates natively** — Built on X Layer Testnet with Uniswap V3 data, aligned with the ecosystem's DeFi infrastructure

---

## 🏆 Hackathon Rubric Alignment

| Criterion (25% each) | How ChainSight delivers |
|---|---|
| **Technical Implementation** | 3 MCP tools, real subgraph integration, mock/live mode, full test suite, clean layered architecture |
| **Innovation & Creativity** | First "insight-as-a-service" MCP skill for X Layer; beginner-first UX design; multi-tool chaining demo |
| **Ecosystem Impact** | Lowers DeFi entry barrier; reusable by any agent; promotes X Layer adoption |
| **Presentation & Documentation** | Streamlit demo UI, 60s video script, architecture diagrams, 50+ tests, complete README |


## 📄 License

MIT © 2024 ChainSight Team

---

<p align="center">
  <strong>ChainSight</strong> · Built for the X Layer Hackathon · 
  <a href="docs/architecture.md">Architecture</a> · 
  <a href="docs/demo_script.md">Demo Script</a>
</p>
