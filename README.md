# BTC15-Hedge: Autonomous Polymarket Trading Agent

Production-grade autonomous trading agent for Polymarket 15-minute BTC prediction markets with Bayesian probability estimation, fee-aware Kelly criterion, and continuous learning via SQLite memory.

> **Disclaimer:** This software is provided as-is for educational and experimental purposes. It is not financial advice. Trading prediction markets involves risk of loss. Use at your own risk and only with funds you can afford to lose.

## Features

- **Bayesian Probability Engine** - Calculates posterior probability from order book signals
- **Fee-Aware Kelly Criterion** - Accounts for Polymarket's March 2026 dynamic fee structure (3.12% peak drag)
- **3.5% Edge Threshold** - Mathematically filters trades to survive fee drag
- **SQLite Memory Persistence** - Stores trade history for continuous learning
- **Telegram Safety Controls** - /status, /halt, /resume, /memory commands
- **50% Drawdown Circuit Breaker** - Auto-halts on catastrophic losses
- **Backtest Framework** - Historical simulation with exact fee calculation

## Quick Start

### 1. Install

```bash
# Clone repository
git clone https://github.com/your-repo/btc15-hedge.git
cd btc15-hedge

# Install dependencies
uv sync
```

### 2. Configure Environment

Create `.env` file:

```bash
cp .env.example .env
```

Required variables:

```bash
# Polygon RPC & Wallet (required)
CHAINSTACK_NODE=https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY
POLYCLAW_PRIVATE_KEY=0xYOUR_PRIVATE_KEY

# Risk Limits
MAX_RISK_USD=2.0
EDGE_THRESHOLD=0.035
INITIAL_BANKROLL=20.0

# Optional: Telegram Bot
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
TELEGRAM_ALLOWED_CHAT_ID=YOUR_CHAT_ID
```

### 3. First-Time Wallet Setup

```bash
# Set Polymarket contract approvals (one-time, costs ~0.01 POL)
uv run python scripts/polyclaw.py wallet approve
```

### 4. Run

```bash
# Dry-run mode (recommended for testing)
uv run python scripts/heartbeat.py --dry-run

# Check system status
uv run python scripts/heartbeat.py --status

# Run backtest simulation
uv run python scripts/backtest.py --simulations 1000 --seed 42
```

## Usage

### Heartbeat (Autonomous Trading)

The main execution loop for 15-minute trading cycles:

```bash
# Dry-run (safe, no actual trades)
uv run python scripts/heartbeat.py --dry-run

# Live trading (requires wallet configuration)
uv run python scripts/heartbeat.py

# System status
uv run python scripts/heartbeat.py --status
```

**Output example:**
```json
{
  "status": "success",
  "market_id": "btc-15m-...",
  "p_posterior": 0.58,
  "q_market": 0.54,
  "edge": 0.04,
  "action": "BUY_YES",
  "trade_size_usd": 1.87,
  "bankroll": 18.13,
  "latency_ms": 2340
}
```

### Backtest

Historical simulation with exact Polymarket fee calculation:

```bash
uv run python scripts/backtest.py --simulations 1000 --seed 42
```

**Output:**
```
============================================================
Polymarket 15-Min BTC Backtest Results
============================================================
Simulations: 1000
Edge Threshold: 3.5%
------------------------------------------------------------
Total Trades Executed: 47
Win Rate: 53.2%
Avg Fee Drag: 1.02%
------------------------------------------------------------
Total Fees Surrendered: $0.48
Net PnL (USDC): $27.71
============================================================
```

### Telegram Safety Bot

Remote monitoring and control:

```bash
uv run python scripts/telegram_bot.py
```

**Commands:**
| Command | Description |
|---------|-------------|
| `/status` | Show wallet, bankroll, trade count, memory prior |
| `/halt` | Enter monitor-only mode (MAX_RISK=0) |
| `/resume` | Resume live trading |
| `/memory` | Show recent consolidation lessons |

### Cron Scheduling

For automated 15-minute execution:

```bash
# Add to crontab
*/15 * * * * cd /path/to/btc15-hedge && uv run python scripts/heartbeat.py >> /var/log/btc15.log 2>&1
```

## Wallet & Position Management

### Check Wallet Status

```bash
uv run python scripts/polyclaw.py wallet status
```

Shows address, POL balance (gas), and USDC.e balance.

### View Positions

```bash
uv run python scripts/polyclaw.py positions
```

Lists open positions with entry price, current price, and P&L.

### Browse Markets

```bash
# Trending markets
uv run python scripts/polyclaw.py markets trending

# Search markets
uv run python scripts/polyclaw.py markets search "bitcoin"

# Market details
uv run python scripts/polyclaw.py market <market_id>
```

### Manual Trading

```bash
# Buy YES position
uv run python scripts/polyclaw.py buy <market_id> YES 50

# Buy NO position
uv run python scripts/polyclaw.py buy <market_id> NO 50
```

## Architecture

```
btc15-hedge/
├── lib/
│   ├── bayesian.py       # Bayesian probability estimation
│   ├── kelly.py          # Fee-aware Kelly criterion sizing
│   ├── memory_db.py      # SQLite persistence layer
│   ├── market_discovery.py # BTC 15-min market finder
│   ├── clob_client.py    # Polymarket CLOB wrapper
│   ├── gamma_client.py   # Market data API
│   └── wallet_manager.py # Wallet operations
├── scripts/
│   ├── heartbeat.py      # Main 15-min execution loop
│   ├── backtest.py       # Historical simulation
│   ├── telegram_bot.py   # Telegram safety controls
│   └── polyclaw.py       # CLI dispatcher
├── tests/                # Test suite
├── IDENTITY.md          # Agent persona (MiroFish-Alpha)
├── SOUL.md               # Behavioral constraints
├── MEMORY.md             # Execution log
├── openclaw.json         # OpenClaw configuration
└── .env.example          # Environment template
```

## Risk Management

### Hard Limits

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MAX_RISK_USD` | 2.0 | Maximum per-cycle capital risk |
| `EDGE_THRESHOLD` | 0.035 | Minimum edge after fees (3.5%) |
| `DRAWDOWN_THRESHOLD` | 0.50 | Halt at 50% loss |
| `HEDGE_RATIO` | 0.25 | Opposite-side hedge size |

### Circuit Breakers

1. **Drawdown Halt** - Auto-stops when bankroll <50% of initial
2. **Telegram /halt** - Manual safety mode
3. **Edge Filter** - Blocks trades below 3.5% threshold

### Polymarket Fee Structure (March 2026)

```
fee_per_share = 0.25 × q× (q × (1-q))²
effective_drag = fee_per_share / q
```

Peak drag: **3.12%** at q=0.50

## Configuration

### Agent Persona

- `IDENTITY.md` - MiroFish-Alpha persona definition
- `SOUL.md` - Quantitative logic boundaries and constraints
- `MEMORY.md` - Execution log (appended by heartbeat, read by consolidation)

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CHAINSTACK_NODE` | Yes | Polygon RPC URL |
| `POLYCLAW_PRIVATE_KEY` | Yes | EVM private key (hex) |
| `MAX_RISK_USD` | No | Max risk/cycle (default: 2.0) |
| `EDGE_THRESHOLD` | No | Min edge (default: 0.035) |
| `INITIAL_BANKROLL` | No | Starting capital (default: 20.0) |
| `TELEGRAM_BOT_TOKEN` | No | Telegram bot token |
| `TELEGRAM_ALLOWED_CHAT_ID` | No | Authorized chat ID |
| `MEMORY_DB_PATH` | No | SQLite path (default: /opt/.../memory.db) |

## OpenClaw Integration

This repository is an OpenClaw skill. To integrate with an OpenClaw agent:

### 1. Install Skill

```bash
cp -r btc15-hedge ~/.openclaw/skills/
```

### 2. Configure Agent

`~/.openclaw/workspace/openclaw.json`:

```json
{
  "agent": {
    "workspace": "~/.openclaw/workspace",
    "skipBootstrap": true
  },
  "models": {
    "primary": {
      "provider": "opencode-go",
      "model": "opencode-go/kimi-k2.5",
      "baseUrl": "https://opencode.ai/zen/go/v1",
      "temperature": 0.0,
      "maxTokens": 1024,
      "timeoutMs": 8000
    }
  },
  "security": {
    "allowLocalExecution": true,
    "restrictDirectories": ["/opt/", "~/.openclaw/"]
  }
}
```

### 3. Set Environment

`/opt/openclaw.env` (chmod600):

```bash
POLYGON_PRIVATE_KEY=0x...
POLYGON_CHAIN_ID=137
POLYMARKET_HOST=https://clob.polymarket.com
MAX_RISK_USD=2.0
EDGE_THRESHOLD=0.035
INITIAL_BANKROLL=20.0
```

### 4. Run as OpenClaw Skill

The agent will execute `heartbeat.py` on a 15-minute schedule and log to `MEMORY.md` for continuous learning.

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific module
uv run pytest tests/test_bayesian.py -v
uv run pytest tests/test_kelly.py -v
uv run pytest tests/test_memory_db.py -v
```

## Troubleshooting

### "Wallet not configured"

Set the `POLYCLAW_PRIVATE_KEY` environment variable:

```bash
export POLYCLAW_PRIVATE_KEY="0x..."
```

### "Insufficient USDC.e"

Check wallet balance:

```bash
uv run python scripts/polyclaw.py wallet status
```

You need USDC.e (bridged USDC) on Polygon.

### "Approvals not set"

Run one-time approval setup:

```bash
uv run python scripts/polyclaw.py wallet approve
```

### "No active BTC 15-min market found"

The Gamma API returns no active 15-min BTC markets. Wait for market creation or check Polymarket directly.

### Telegram bot not responding

1. Verify `TELEGRAM_BOT_TOKEN` is set
2. Check `TELEGRAM_ALLOWED_CHAT_ID` matches your chat ID
3. Ensure bot has been started with `/start`

### "CLOB order failed" / "IP blocked by Cloudflare"

Use a rotating residential proxy:

```bash
export HTTPS_PROXY="http://user:pass@geo.iproyal.com:12321"
export CLOB_MAX_RETRIES=10
```

## Polymarket Contracts (Polygon Mainnet)

| Contract | Address |
|----------|---------|
| USDC.e | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` |
| CTF | `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045` |
| CTF Exchange | `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E` |
| Neg Risk CTF Exchange | `0xC5d563A36AE78145C45a50134d48A1215220f80a` |

## License

Apache 2.0

## Credits

Based on [PolyClaw](https://github.com/chainstacklabs/polyclaw) by Chainstack.

- **Chainstack** — Polygon RPC infrastructure  
- **Polymarket** — Prediction market platform