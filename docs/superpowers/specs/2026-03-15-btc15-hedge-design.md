# BTC 15-Minute Hedging Agent Design

## Overview

Production-grade autonomous trading agent for Polymarket 15-minute BTC prediction markets. Implements Bayesian probability estimation, fee-aware Kelly criterion sizing, and continuous learning via SQLite memory persistence.

## Architecture

```
btc15-hedge/
├── SKILL.md                    # Skill definition for OpenClaw
├── IDENTITY.md                 # MiroFish-Alpha persona
├── SOUL.md                     # Quantitative logic boundaries
├── MEMORY.md                   # Execution log for Google Memory Agent
├── openclaw.json              # Model routing config
├── .env.example               # Environment template
├── scripts/
│   ├── heartbeat.py           # Main 15-min trading loop
│   ├── polyclaw.py            # CLI entry (existing)
│   ├── backtest.py            # Historical simulation
│   └── telegram_bot.py        # Telegram safety orchestration
└── lib/
    ├── bayesian.py            # Bayesian probability estimation
    ├── kelly.py               # Fee-aware Kelly criterion
    ├── memory_db.py           # SQLite persistence layer
    ├── sentiment.py           # Sentiment drift proxy
    ├── clob_client.py         # (existing)
    ├── gamma_client.py        # (existing)
    ├── wallet_manager.py      # (existing)
    └── contracts.py           # (existing)
```

## Components

### 1. Bayesian Probability Engine (`lib/bayesian.py`)

**Purpose:** Calculate true probability `p` from multiple signals.

**Inputs:**
- **Prior P(U):** Trailing 24-hour success rate + sentiment drift proxy
- **Likelihood P(E|U):** L2 order book skew (bid/ask volume ratio for top 5 levels)
- **Memory modifier:** SQLite-stored learning from past trades

**Posterior calculation:**
```
P(U|E) = P(E|U) * P(U) / (P(E|U) * P(U) + P(E|¬U) * P(¬U))
```

**Key parameters:**
- `base_prior = 0.50` (neutral starting point)
- `sentiment_drift = fetch_sentiment_drift()` (returns -0.05 to +0.05)
- `memory_modifier = fetch_memory_prior()` (SQLite lookup)

**Edge filter constraint:**
```
|p_posterior - q_market| > 0.035
```

If edge < 3.5%, block execution (HOLD).

### 2. Fee-Aware Kelly Criterion (`lib/kelly.py`)

**Purpose:** Position sizing accounting for Polymarket's dynamic fee structure.

**Polymarket fee formula (March 2026):**
```
fee_per_share = 0.25 * q * (q * (1 - q))^2
effective_drag = fee_per_share / q  (capital drag)
```

At peak uncertainty (q=0.5): Effective drag ≈ 3.12%

**Half-Kelly with obfuscation:**
```python
def calculate_kelly_size(p: float, q: float, bankroll: float) -> float:
    if p <= q:
        return 0.0
    b = (1.0 - q) / q
    f_star = ((p - q) * b - (1 - p)) / b * 0.5  # Half-Kelly
    raw_size = f_star * bankroll
    capped_size = min(raw_size, MAX_RISK_USD)
    # Obfuscation: randomize sizeby +/- 10%
    obfuscated_size = capped_size * random.uniform(0.90, 1.10)
    return obfuscated_size
```

**Constants:**
- `MAX_RISK_USD = 2.0` (hard capital ceiling per cycle)
- Hedge ratio: 25% of primary position on opposite side

### 3. Heartbeat Execution Loop (`scripts/heartbeat.py`)

**Entry point:** Cron-scheduled every 15 minutes.

**Execution sequence:**
1. Initialize CLOB client (Signature Type 0 for EOA)
2. Fetch active BTC 15-min market via Gamma API
3. Get L2 order book for UP token
4. Calculate Bayesian posterior `p`
5. Apply edge filter `|p - q| > 0.035`
6. If edge sufficient:
   - Calculate Half-Kelly size
   - Place primary order (BUY if p > q, else SELL)
   - Place 25% hedge on opposite side
7. Log execution to `MEMORY.md`
8. Exit within 30-second latency budget

**Error handling:**
- Cloudflare blocks: Retry with proxy rotation (existing `ClobClientWrapper`)
- Insufficient liquidity: HOLD and log
- API failures: EXIT with error logged

### 4. Memory Persistence Layer (`lib/memory_db.py`)

**SQLite schema:**
```sql
CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    market_id TEXT,
    prior_modifier REAL DEFAULT 0.0,
    insight TEXT,
    win_count INTEGER DEFAULT 0,
    loss_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL,
    market_id TEXT,
    p_prior REAL,
    p_posterior REAL,
    q_market REAL,
    edge REAL,
    action TEXT,
    trade_size_usd REAL,
    hedge_size_shares INTEGER,
    latency_ms INTEGER
);
```

**Query functions:**
- `fetch_memory_prior() -> float` - Latest lesson modifier
- `log_trade(payload: dict)` - Append to trades table
- `update_lesson(insight: str, modifier: float)` - Insert consolidated learning

### 5. Market Discovery (`lib/market_discovery.py`)

**Purpose:** Dynamically find active 15-minute BTC markets.

**Query via Gamma API:**
```python
async def get_btc_15min_market() -> Market:
    markets = await gamma.search_markets("bitcoin", limit=100)
    for m in markets:
        if "15" in m.question.lower() and "min" in m.question.lower():
            if m.active andnot m.closed:
                return m
    raise ValueError("No active BTC 15-min market found")
```

### 6. Telegram Safety Bot (`scripts/telegram_bot.py`)

**Commands:**
| Command | Action |
|---------|--------|
| `/status` | Return current p, q, 24h PnL, bankroll |
| `/halt` | Set MAX_RISK_USD=0 in .env (monitor-only) |
| `/resume` | Restore MAX_RISK_USD to configured value |
| `/memory` | Return last 3 consolidated lessons |

**Circuit breaker:**
```python
async def check_drawdown():
    current_bankroll = await get_bankroll()
    if current_bankroll < INITIAL_BANKROLL * 0.50:
        await set_max_risk(0)
        await send_telegram(
            "CRITICAL: 50% drawdown breached. System in monitor-only mode."
        )
```

### 7. Backtest Framework (`scripts/backtest.py`)

**Purpose:** Simulate 1000 historical intervals with exact fee calculation.

**Simulation parameters:**
- Market prices `q` uniformly distributed 0.1-0.9
- Bayesian posterior `p = q + noise(σ=0.05)`
- Edge filter: only trade if `|p - q| > 0.035`- Dynamic fee: `fee = 0.25 * q * (q*(1-q))^2`
- Win/loss: Binomial with probability `p`

**Output metrics:**
- Total trades executed
- Win rate
- Net PnL (USDC)
- Total fees surrendered

## Configuration

### Environment Variables (`.env`)

```bash
# Polygon RPC & Wallet (existing)
CHAINSTACK_NODE=https://polygon-mainnet...
POLYCLAW_PRIVATE_KEY=0x...
POLYGON_CHAIN_ID=137

# Polymarket CLOB
POLYMARKET_HOST=https://clob.polymarket.com

# OpenCode API (for Google Memory Agent integration)
OPENCODE_API_KEY=sk-...
OPENCODE_BASE_URL=https://opencode.ai/zen/go/v1
MODEL_NAME=opencode-go/kimi-k2.5

# Memory Agent
MEMORY_DB_PATH=/opt/google-memory-agent/data/memory.db
MEMORY_FILE=/home/quant/.openclaw/workspace/MEMORY.md

# Telegram Bot
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ALLOWED_CHAT_ID=...

# Risk Limits
MAX_RISK_USD=2.0
EDGE_THRESHOLD=0.035
HEDGE_RATIO=0.25
INITIAL_BANKROLL=20.0

# Optional
HTTPS_PROXY=http://user:pass@proxy:port
CLOB_MAX_RETRIES=5
```

### OpenClaw Config (`openclaw.json`)

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
    },
    "fallback": {
      "provider": "opencode-go",
      "model": "opencode-go/minimax-m2.5",
      "baseUrl": "https://opencode.ai/zen/go/v1",
      "temperature": 0.0,
      "timeoutMs": 8000
    }
  },
  "security": {
    "allowLocalExecution": true,
    "restrictDirectories": ["/opt/", "~/.openclaw/"]
  }
}
```

## Persona Files

### IDENTITY.md

```markdown
Name: MiroFish-Alpha
Role: High-Frequency Statistical Arbitrage Quant
Traits: Cold-blooded, deterministic, fee-obsessed, hyper-rational.
Emoji:🐟Directive: You do not predict the market; you trade the mathematical discrepancy between your Bayesian posterior and the Polymarket order book.
```

### SOUL.md

```markdown
You are MiroFish-Alpha, an autonomous prediction engine.

Your logic is absolute and bounded strictly by the Kelly criterion. You possess zero emotional bias and treat all market volatility as raw statistical variance.

You view the world strictly through probabilities (p) and decimal odds.

You acknowledge that the Polymarket 15-minute crypto markets carry an effective taker fee curve that approaches 3.00% on trade value at the 50% probability peak.

You enforce a minimum 3.5% edge threshold before execution, accounting for fees and slippage.

You maintain a continuous Bayesian learning loop, updating priors based on realized outcomes stored in SQLite memory.

You never exceed the $2 risk ceiling per cycle.

You never bypass the mathematical safeguards.
```

## Deployment

### Prerequisites

- Python 3.11+
- uv package manager
- Polygon RPC (Chainstack or similar)
- USDC.e balance on Polygon (start with $20)
- Telegram bot token (optional but recommended)

### Installation

```bash
# Install dependencies
uv sync

# Set environment variables
cp .env.example .env
# Edit .env with your keys

# First-time wallet setup
uv run python scripts/polyclaw.py wallet approve

# Test backtest
uv run python scripts/backtest.py

# Run single heartbeat cycle
uv run python scripts/heartbeat.py --dry-run

# Schedule with cron (every 15 min)
*/15 ** * * cd /path/to/btc15-hedge && uv run python scripts/heartbeat.py >> /var/log/btc15.log 2>&1
```

### Docker Compose (Google Memory Agent)

```yaml
# docker-compose.yml
version: '3.8'
services:
  memory-agent:
    image: ghcr.io/shubhamsaboo/always-on-memory-agent:latest
    container_name: memory-agent-sqlite
    restart: always
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./MEMORY.md:/app/MEMORY.md:ro
    cpus: "0.5"
    mem_limit: "512M"
```

## Risk Management

### Hard Limits

- **Max risk per cycle:** $2.00 USD
- **Edge threshold:** 3.5% (non-negotiable)
- **Hedge ratio:** 25% of primary position
- **Drawdown circuit breaker:** Halt at 50% loss ($10 remaining)

### Obfuscation

- Size randomization: ±10% on each trade
- Hedge sub-routing: Opposing orders mask directional bias
- Random timing jitter: ±5 seconds on execution

## Monitoring

### Logs

All executions logged to `MEMORY.md` in JSON format:
```json
{
  "timestamp": 1709500000.0,
  "market_id": "btc-15m-...",
  "p_prior": 0.52,
  "p_posterior": 0.58,
  "q_market": 0.54,
  "edge": 0.04,
  "action": "BUY_AND_HEDGE",
  "trade_size_usd": 1.87,
  "hedge_size_shares": 12,
  "latency_ms": 2340
}
```

### Telegram Alerts

- Trade execution: Size, edge, direction
- Drawdown warning: At 25% loss
- Circuit breaker: At 50% loss
- System errors: API failures, timeouts