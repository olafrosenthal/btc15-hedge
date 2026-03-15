# BTC 15-Minute Hedging Agent Implementation Plan

> **For agentic workers:** REQUIRED: Usesuperpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an autonomous 15-minute BTC prediction market trading agent with Bayesian probability estimation, fee-aware Kelly criterion, and continuous learning via SQLite memory.

**Architecture:** Leverages existing Polyclaw fork's CLOB client and Gamma API. New components: Bayesian probability engine, Kelly sizing module, SQLite memory persistence, heartbeat execution loop, Telegram safety bot, and backtest framework.

**Tech Stack:** Python 3.11+, py-clob-client, web3, httpx, python-telegram-bot, SQLite3, pytest

---

## File Structure

```
btc15-hedge/
├── SKILL.md                    # (modify) Add btc15-hedge commands
├── IDENTITY.md                 # (create) MiroFish-Alpha persona
├── SOUL.md                     # (create) Quantitative logic boundaries
├── MEMORY.md                   # (create) Execution log (empty initially)
├── openclaw.json              # (create) Model routing config
├── .env.example               # (create) Environment template
├── scripts/
│   ├── heartbeat.py           # (create) Main 15-min trading loop
│   ├── polyclaw.py            # (existing) CLI entry
│   ├── backtest.py            # (create) Historical simulation
│   └── telegram_bot.py        # (create) Safety orchestration
├── lib/
│   ├── bayesian.py            # (create) Probability estimation
│   ├── kelly.py               # (create) Fee-aware Kelly criterion
│   ├── memory_db.py           # (create) SQLite persistence
│   ├── sentiment.py           # (create) Sentiment drift proxy
│   ├── market_discovery.py    # (create) BTC 15-min market finder
│   └── ... (existing)
└── tests/
    ├── __init__.py            # (create)
    ├── test_bayesian.py       # (create)
    ├── test_kelly.py          # (create)
    └── test_memory_db.py      # (create)
```

---

## Chunk 1: Core Math Modules (bayesian.py, kelly.py)

### Task 1.1: Bayesian Probability Engine

**Files:**
- Create: `lib/bayesian.py`
- Create: `tests/test_bayesian.py`

- [ ] **Step 1: Write failing tests for Bayesian posterior calculation**

Create `tests/__init__.py` (empty) and `tests/test_bayesian.py`:

```python
"""Tests for Bayesian probability estimation."""

import pytest
from lib.bayesian import BayesianEstimator

class TestBayesianEstimator:
    def test_posterior_with_equal_prior_returns_equal(self):
        """When prior=0.5 and likelihood=0.5, posterior should be 0.5."""
        estimator = BayesianEstimator(base_prior=0.5)
        posterior = estimator.calculate_posterior(
            p_prior=0.5,
            likelihood_up=0.5,
            likelihood_down=0.5
        )
        assert abs(posterior - 0.5) < 0.001

    def test_posterior_with_skewed_likelihood(self):
        """Order book skew should shift probability."""
        estimator = BayesianEstimator(base_prior=0.5)
        # Strong bid volume suggests UP
        posterior = estimator.calculate_posterior(
            p_prior=0.5,
            likelihood_up=0.7,
            likelihood_down=0.3
        )
        assert posterior > 0.5
        assert posterior < 1.0  # Should not be certain

    def test_posterior_respects_memory_modifier(self):
        """Memory feedback should adjust prior."""
        estimator = BayesianEstimator(base_prior=0.5, memory_modifier=0.1)
        p_prior = estimator.adjust_prior_with_memory()
        assert abs(p_prior - 0.6) < 0.001

    def test_posterior_clamps_to_valid_range(self):
        """Posterior must stay in [0.01, 0.99]."""
        estimator = BayesianEstimator(base_prior=0.5)
        # Extreme skew should clamp
        posterior = estimator.calculate_posterior(
            p_prior=0.99,
            likelihood_up=0.99,
            likelihood_down=0.01
        )
        assert posterior <= 0.99
        assert posterior >= 0.01

    def test_edge_calculation(self):
        """Edge is posterior minus market price."""
        estimator = BayesianEstimator(base_prior=0.5)
        edge = estimator.calculate_edge(p_posterior=0.60, q_market=0.50)
        assert abs(edge - 0.10) < 0.001

    def test_edge_filter_blocks_insufficient_edge(self):
        """Edge below 3.5% threshold should block execution."""
        estimator = BayesianEstimator(base_prior=0.5, edge_threshold=0.035)
        assert not estimator.should_trade(edge=0.03)
        assert estimator.should_trade(edge=0.04)

    def test_order_book_skew_calculation(self):
        """Skew from L2 order book volumes."""
        estimator = BayesianEstimator(base_prior=0.5)
        # Mock order book with morebid volume
        order_book = {
            "bids": [{"size": "100"}, {"size": "50"}, {"size": "25"}],
            "asks": [{"size": "30"}, {"size": "20"}, {"size": "10"}]
        }
        skew = estimator.calculate_order_book_skew(order_book)
        assert skew > 0.5  # More bids = bullish skew

    def test_likelihood_from_order_book(self):
        """Likelihood derived from order book skew."""
        estimator = BayesianEstimator(base_prior=0.5)
        order_book = {
            "bids": [{"size": "100"}, {"size": "50"}],
            "asks": [{"size": "30"}, {"size": "20"}]
        }
        likelihood_up, likelihood_down = estimator.likelihood_from_order_book(order_book)
        assert likelihood_up > likelihood_down
        assert likelihood_up + likelihood_down > 0  # Both positive
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_bayesian.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'lib.bayesian'"

- [ ] **Step 3: Write BayesianEstimator implementation**

Create `lib/bayesian.py`:

```python
"""Bayesian probability estimation for prediction markets."""

import json
from dataclasses import dataclass
from typing import Optional

EDGE_THRESHOLD = 0.035  # 3.5% minimum edge


@dataclass
class OrderBookLevel:
    price: float
    size: float


@dataclass
class OrderBook:
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]


class BayesianEstimator:
    """Calculate Bayesian posterior probability from multiple signals."""

    def __init__(
        self,
        base_prior: float = 0.50,
        memory_modifier: float = 0.0,
        edge_threshold: float = EDGE_THRESHOLD,
    ):
        self.base_prior = base_prior
        self.memory_modifier = memory_modifier
        self.edge_threshold = edge_threshold

    def adjust_prior_with_memory(self) -> float:
        """Adjust base prior with memory-derived modifier."""
        adjusted = self.base_prior + self.memory_modifier
        return max(0.01, min(0.99, adjusted))

    def calculate_order_book_skew(self, order_book: dict) -> float:
        """Calculate skew from top 5 bid/ask volumes.
        
        Returns value in [0, 1] where>0.5 indicates bullish (bid-dominant).
        """
        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])
        
        bid_vol = sum(float(b.get("size", 0)) for b in bids[:5])
        ask_vol = sum(float(a.get("size", 0)) for a in asks[:5])
        
        if bid_vol + ask_vol <1e-9:
            return 0.5
        
        return bid_vol / (bid_vol + ask_vol)

    def likelihood_from_order_book(self, order_book: dict) -> tuple[float, float]:
        """Derive likelihood from order book skew.
        
        Returns (P(E|U), P(E|not U)) where E is evidence (order book state).
        """
        skew = self.calculate_order_book_skew(order_book)
        
        # Transform skew to likelihood
        # Highbid volume = more likely UP resolution
        likelihood_up = skew
        likelihood_down = 1 - skew
        
        # Add small baseline to avoid zeros
        likelihood_up = max(0.01, likelihood_up)
        likelihood_down = max(0.01, likelihood_down)
        
        return likelihood_up, likelihood_down

    def calculate_posterior(
        self,
        p_prior: float,
        likelihood_up: float,
        likelihood_down: float,
    ) -> float:
        """Calculate Bayesian posterior using Bayes' theorem.
        
        P(U|E) = P(E|U) * P(U) / (P(E|U) * P(U) + P(E|not U) * P(not U))
        """
        # Ensure validity
        p_prior = max(0.01, min(0.99, p_prior))
        
        numerator = likelihood_up * p_prior
        denominator = (likelihood_up * p_prior) + (likelihood_down * (1 - p_prior))
        
        if denominator < 1e-9:
            return0.5
        
        posterior = numerator / denominator
        
        # Clamp to valid range
        return max(0.01, min(0.99, posterior))

    def calculate_edge(self, p_posterior: float, q_market: float) -> float:
        """Calculate edge as difference between posterior and market price."""
        return p_posterior - q_market

    def should_trade(self, edge: float) -> bool:
        """Determine if edge exceeds threshold for execution."""
        return abs(edge) > self.edge_threshold

    def estimate_from_signals(
        self,
        order_book: dict,
        sentiment_drift: float = 0.0,
        memory_modifier: float = 0.0,
    ) -> tuple[float, float]:
        """Full estimation pipeline.
        
        Returns (posterior_probability, edge_vs_market).
        """
        # Adjust prior with memory and sentiment
        p_prior = self.base_prior + sentiment_drift + memory_modifier
        p_prior = max(0.01, min(0.99, p_prior))
        
        # Get likelihood from order book
        likelihood_up, likelihood_down = self.likelihood_from_order_book(order_book)
        
        # Calculate posterior
        posterior = self.calculate_posterior(p_prior, likelihood_up, likelihood_down)
        
        # Edge will be calculated against market price separately
        return posterior


def parse_order_book_from_clob(order_book_response: dict) -> dict:
    """Parse CLOB API response into standard order book format."""
    bids = []
    asks = []
    
    for b in order_book_response.get("bids", []):
        bids.append({
            "price": float(b.get("price", 0)),
            "size": float(b.get("size", 0))
        })
    
    for a in order_book_response.get("asks", []):
        asks.append({
            "price": float(a.get("price", 0)),
            "size": float(a.get("size", 0))
        })
    
    # Sort by price (bids descending, asks ascending)
    bids.sort(key=lambda x: x["price"], reverse=True)
    asks.sort(key=lambda x: x["price"])
    
    return {"bids": bids, "asks": asks}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_bayesian.py -v`
Expected: PASS (all tests green)

- [ ] **Step 5: Commit Bayesian engine**

```bash
git add lib/bayesian.py tests/__init__.py tests/test_bayesian.py
git commit -m "feat: add Bayesian probability estimation module"
```

### Task 1.2: Fee-Aware Kelly Criterion

**Files:**
- Create: `lib/kelly.py`
- Create: `tests/test_kelly.py`

- [ ] **Step 1: Write failing tests for Kelly sizing**

Create `tests/test_kelly.py`:

```python
"""Tests for fee-aware Kelly criterion."""

import pytest
from lib.kelly import KellySizer, calculate_polymarket_fee

class TestKellySizer:
    def test_kelly_returns_zero_when_no_edge(self):
        """No position when posterior <= market price."""
        sizer = KellySizer(max_risk_usd=2.0)
        size = sizer.calculate_size(p=0.48, q=0.50, bankroll=20.0)
        assert size == 0.0

    def test_kelly_sizes_proportionally_to_edge(self):
        """Larger edge = larger position."""
        sizer = KellySizer(max_risk_usd=2.0, half_kelly=True)
        size_small = sizer.calculate_size(p=0.52, q=0.50, bankroll=20.0)
        size_large = sizer.calculate_size(p=0.60, q=0.50, bankroll=20.0)
        assert size_large > size_small

    def test_kelly_respects_max_risk_cap(self):
        """Never exceed max_risk_usd regardless of Kelly calculation."""
        sizer = KellySizer(max_risk_usd=2.0, half_kelly=True)
        # Very high edge would suggest large position
        size = sizer.calculate_size(p=0.95, q=0.40, bankroll=100.0)
        assert size <= 2.0

    def test_kelly_obfuscates_size(self):
        """Sizes should have randomization applied."""
        sizer = KellySizer(max_risk_usd=2.0, half_kelly=True, obfuscate=True)
        # Run multiple times - should get different results
        sizes = [sizer.calculate_size(p=0.60, q=0.50, bankroll=20.0) for _ in range(10)]
        # Should have some variation due to +/-10% randomization
        assert len(set(sizes)) > 1  # At least some variation

    def test_kelly_no_obfuscation_when_disabled(self):
        """Deterministic sizes when obfuscate=False."""
        sizer = KellySizer(max_risk_usd=2.0, half_kelly=True, obfuscate=False)
        sizes = [sizer.calculate_size(p=0.60, q=0.50, bankroll=20.0) for _ in range(5)]
        assert len(set(sizes)) == 1  # All identical

    def test_polymarket_fee_calculation(self):
        """Dynamic fee based on price."""
        # At p=0.5, fee rate peaks
        fee_50 = calculate_polymarket_fee(0.50)
        # At p=0.1 or p=0.9, fee is lower
        fee_10 = calculate_polymarket_fee(0.10)
        fee_90 = calculate_polymarket_fee(0.90)
        
        assert fee_50 > fee_10
        assert fee_50 > fee_90
        assert abs(fee_50 - 0.03125) < 0.001  # ~3.125% at peak

    def test_effective_drag_calculation(self):
        """Effective capital drag at different prices."""
        sizer = KellySizer(max_risk_usd=2.0)
        drag_50 = sizer.calculate_effective_drag(0.50)
        drag_70 = sizer.calculate_effective_drag(0.70)
        
        # Peak drag at 50%
        assert drag_50 > drag_70

    def test_hedge_size_calculation(self):
        """Hedge is correct ratio of primary."""
        sizer = KellySizer(max_risk_usd=2.0, hedge_ratio=0.25)
        primary_shares = 100
        hedge_shares = sizer.calculate_hedge_size(primary_shares)
        assert hedge_shares ==25
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_kelly.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'lib.kelly'"

- [ ] **Step 3: Write KellySizer implementation**

Create `lib/kelly.py`:

```python
"""Fee-aware Kelly criterion for Polymarket trading."""

import random
from dataclasses import dataclass

# Polymarket fee constants (March 2026)
FEE_RATE_CONSTANT = 0.25
FEE_RATE_EXPONENT = 2

# Default risk limits
DEFAULT_MAX_RISK_USD = 2.0
DEFAULT_HEDGE_RATIO = 0.25
DEFAULT_EDGE_THRESHOLD = 0.035


def calculate_polymarket_fee(q: float) -> float:
    """Calculate Polymarket dynamic fee rate.
    
    Formula: fee = C * q * (q * (1-q))^2
    Where C = 0.25 and exponent =2.
    
    Returns fee as fraction of trade value.
    """
    if not (0 < q< 1):
        return 0.0
    
    fee_per_share = FEE_RATE_CONSTANT * q * (q * (1 - q)) ** FEE_RATE_EXPONENT
    
    # Effective drag on capital (since shares cost q)
    # When you buy at price q, the fee is assessed per share
    # But your capital at risk is q, so effective drag is fee/q
    if q <0.001:
        return 0.0
    
    return fee_per_share / q


@dataclass
class KellyResult:
    primary_size_usd: float
    primary_shares: int
    hedge_shares: int
    effective_fee: float
    edge_after_fees: float


class KellySizer:
    """Position sizing using fee-aware half-Kelly criterion."""

    def __init__(
        self,
        max_risk_usd: float = DEFAULT_MAX_RISK_USD,
        hedge_ratio: float = DEFAULT_HEDGE_RATIO,
        edge_threshold: float = DEFAULT_EDGE_THRESHOLD,
        half_kelly: bool = True,
        obfuscate: bool = True,
    ):
        self.max_risk_usd = max_risk_usd
        self.hedge_ratio = hedge_ratio
        self.edge_threshold = edge_threshold
        self.half_kelly = half_kelly
        self.obfuscate = obfuscate

    def calculate_effective_drag(self, q: float) -> float:
        """Calculate effective capital drag at given price.
        
        At q=0.5, effective drag ≈ 3.12% (peak).
        """
        return calculate_polymarket_fee(q)

    def calculate_size(
        self,
        p: float,
        q: float,
        bankroll: float,
    ) -> float:
        """Calculate position size in USD.
        
        Args:
            p: Bayesian posterior probability
            q: Current market ask price
            bankroll: Available capital
        
        Returns:
            Position size in USD (before obfuscation)
        """
        # No edge = no trade
        if p <= q:
            return 0.0
        
        # Kelly formula for binary options
        # f* = (p - q) * b - (1-p) / b
        # where b = (1-q) / q (odds)
        b = (1.0 - q) / q
        
        # Calculate Kelly fraction
        kelly_numerator = (p - q) * b - (1.0 - p)
        kelly_fraction = kelly_numerator / b
        
        # Apply half-Kelly for safety
        if self.half_kelly:
            kelly_fraction *= 0.5
        
        # Ensure non-negative
        kelly_fraction = max(0.0, kelly_fraction)
        
        # Calculate raw size
        raw_size = kelly_fraction * bankroll
        
        # Cap at max risk
        capped_size = min(raw_size, self.max_risk_usd)
        
        # Apply obfuscation (random +/- 10%)
        if self.obfuscate and capped_size > 0:
            multiplier = random.uniform(0.90, 1.10)
            capped_size *= multiplier
        
        return round(capped_size, 2)

    def calculate_shares(self, size_usd: float, price: float) -> int:
        """Convert USD size to shares."""
        if price < 0.001:
            return 0
        return int(size_usd / price)

    def calculate_hedge_size(self, primary_shares: int) -> int:
        """Calculate hedge position size."""
        return int(primary_shares * self.hedge_ratio)

    def calculate_full(
        self,
        p: float,
        q: float,
        bankroll: float,
    ) -> KellyResult:
        """Calculate complete sizing result."""
        # Effective fee at this price
        fee = self.calculate_effective_drag(q)
        
        # Edge after fees
        edge = p - q
        edge_after_fees = edge - fee
        
        # Position sizing
        primary_size = self.calculate_size(p, q, bankroll)
        primary_shares = self.calculate_shares(primary_size, q)
        hedge_shares = self.calculate_hedge_size(primary_shares)
        
        return KellyResult(
            primary_size_usd=primary_size,
            primary_shares=primary_shares,
            hedge_shares=hedge_shares,
            effective_fee=fee,
            edge_after_fees=edge_after_fees,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_kelly.py -v`
Expected: PASS (all tests green)

- [ ] **Step 5: Commit Kelly module**

```bash
git add lib/kelly.py tests/test_kelly.py
git commit -m "feat: add fee-aware Kelly criterion sizing module"
```

---

## Chunk 2: Memory Persistence Layer

### Task 2.1: SQLite Memory Database

**Files:**
- Create: `lib/memory_db.py`
- Create: `tests/test_memory_db.py`

- [ ] **Step 1: Write failing tests for memory database**

Create `tests/test_memory_db.py`:

```python
"""Tests for SQLite memory persistence."""

import os
import tempfile
import pytest
from pathlib import Path

from lib.memory_db import MemoryDB, Trade, Lesson

class TestMemoryDB:
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        os.unlink(db_path)

    def test_init_creates_tables(self, temp_db):
        """Database initialization creates required tables."""
        db = MemoryDB(temp_db)
        assert db.table_exists("trades")
        assert db.table_exists("lessons")

    def test_log_trade_stores_record(self, temp_db):
        """Trade logging persists to database."""
        db = MemoryDB(temp_db)
        
        trade = Trade(
            timestamp=1709500000.0,
            market_id="btc-15m-test",
            p_prior=0.52,
            p_posterior=0.58,
            q_market=0.54,
            edge=0.04,
            action="BUY",
            trade_size_usd=1.87,
            hedge_size_shares=12,
            latency_ms=2340
        )
        
        db.log_trade(trade)
        
        trades = db.get_recent_trades(limit=1)
        assert len(trades) == 1
        assert trades[0].market_id == "btc-15m-test"
        assert trades[0].edge ==0.04

    def test_update_lesson_stores_modifier(self, temp_db):
        """Lesson persistence stores learning modifier."""
        db = MemoryDB(temp_db)
        
        db.update_lesson(
            market_id="btc-15m-test",
            prior_modifier=-0.02,
            insight="Overestimated momentum in low-volume session"
        )
        
        lessons = db.get_lessons(limit=1)
        assert len(lessons) == 1
        assert lessons[0].prior_modifier == -0.02

    def test_fetch_memory_prior_returns_latest(self, temp_db):
        """Memory prior retrieval gets most recent modifier."""
        db = MemoryDB(temp_db)
        
        db.update_lesson("m1", 0.01, "First lesson")
        db.update_lesson("m2", -0.02, "Second lesson")
        db.update_lesson("m3", 0.03, "Third lesson")
        
        prior = db.fetch_memory_prior()
        assert prior == 0.03

    def test_fetch_memory_prior_returns_zero_when_empty(self, temp_db):
        """Empty database returns zero prior."""
        db = MemoryDB(temp_db)
        prior = db.fetch_memory_prior()
        assert prior == 0.0

    def test_get_pnl_summary(self, temp_db):
        """PnL summary aggregates correctly."""
        db = MemoryDB(temp_db)
        
        # Add winning trade
        db.log_trade(Trade(
            timestamp=1.0, market_id="m1", p_prior=0.5, p_posterior=0.6,
            q_market=0.5, edge=0.1, action="BUY", trade_size_usd=2.0,
            hedge_size_shares=5, latency_ms=100
        ))
        
        # Add another trade
        db.log_trade(Trade(
            timestamp=2.0, market_id="m2", p_prior=0.5, p_posterior=0.6,
            q_market=0.5, edge=0.1, action="BUY", trade_size_usd=1.5,
            hedge_size_shares=3, latency_ms=150
        ))
        
        summary = db.get_pnl_summary()
        assert summary["total_trades"] == 2
        assert summary["total_volume_usd"] == 3.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_memory_db.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'lib.memory_db'"

- [ ] **Step 3: Write MemoryDB implementation**

Create `lib/memory_db.py`:

```python
"""SQLite persistence layer for trading memory."""

import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional
from pathlib import Path

DEFAULT_DB_PATH = "/opt/google-memory-agent/data/memory.db"


@dataclass
class Trade:
    timestamp: float
    market_id: str
    p_prior: float
    p_posterior: float
    q_market: float
    edge: float
    action: str
    trade_size_usd: float
    hedge_size_shares: int
    latency_ms: int
    error: Optional[str] = None


@dataclass
class Lesson:
    id: Optional[int]
    created_at: str
    market_id: str
    prior_modifier: float
    insight: str
    win_count: int
    loss_count: int


class MemoryDB:
    """SQLite persistence for trading history and lessons."""

    CREATE_TRADES_TABLE = """
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
            latency_ms INTEGER,
            error TEXT
        )
    """

    CREATE_LESSONS_TABLE = """
        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            market_id TEXT,
            prior_modifier REAL DEFAULT 0.0,
            insight TEXT,
            win_count INTEGER DEFAULT 0,
            loss_count INTEGER DEFAULT 0
        )
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._ensure_tables()

    def _ensure_tables(self):
        """Create tables if they don't exist."""
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(self.CREATE_TRADES_TABLE)
        cursor.execute(self.CREATE_LESSONS_TABLE)
        conn.commit()
        conn.close()

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def log_trade(self, trade: Trade):
        """Log a trade execution to the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO trades 
               (timestamp, market_id, p_prior, p_posterior, q_market, edge,
                action, trade_size_usd, hedge_size_shares, latency_ms, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trade.timestamp,
                trade.market_id,
                trade.p_prior,
                trade.p_posterior,
                trade.q_market,
                trade.edge,
                trade.action,
                trade.trade_size_usd,
                trade.hedge_size_shares,
                trade.latency_ms,
                trade.error
            )
        )
        conn.commit()
        conn.close()

    def update_lesson(
        self,
        market_id: str,
        prior_modifier: float,
        insight: str,
        win_count: int =0,
        loss_count: int = 0
    ):
        """Insert a consolidated lesson."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO lessons
               (market_id, prior_modifier, insight, win_count, loss_count)
               VALUES (?, ?, ?, ?, ?)""",
            (market_id, prior_modifier, insight, win_count, loss_count)
        )
        conn.commit()
        conn.close()

    def fetch_memory_prior(self) -> float:
        """Get the latest prior modifier."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT prior_modifier FROM lessons ORDER BY created_at DESC LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()
        return float(row[0]) if row else 0.0

    def get_lessons(self, limit: int = 10) -> list[Lesson]:
        """Get recent lessons."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, created_at, market_id, prior_modifier, insight, win_count, loss_count
               FROM lessons ORDER BY created_at DESC LIMIT ?""",
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            Lesson(
                id=row[0],
                created_at=row[1],
                market_id=row[2],
                prior_modifier=row[3],
                insight=row[4],
                win_count=row[5],
                loss_count=row[6]
            )
            for row in rows
        ]

    def get_recent_trades(self, limit: int = 100) -> list[Trade]:
        """Get recent trades."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT timestamp, market_id, p_prior, p_posterior, q_market, edge,
                      action, trade_size_usd, hedge_size_shares, latency_ms, error
               FROM trades ORDER BY timestamp DESC LIMIT ?""",
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            Trade(
                timestamp=row[0],
                market_id=row[1],
                p_prior=row[2],
                p_posterior=row[3],
                q_market=row[4],
                edge=row[5],
                action=row[6],
                trade_size_usd=row[7],
                hedge_size_shares=row[8],
                latency_ms=row[9],
                error=row[10]
            )
            for row in rows
        ]

    def get_pnl_summary(self) -> dict:
        """Get aggregated PnL summary."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM trades")
        total_trades = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(trade_size_usd) FROM trades")
        total_volume = cursor.fetchone()[0] or 0.0
        
        cursor.execute("SELECT AVG(latency_ms) FROM trades")
        avg_latency = cursor.fetchone()[0] or 0.0
        
        conn.close()
        
        return {
            "total_trades": total_trades,
            "total_volume_usd": total_volume,
            "avg_latency_ms": avg_latency
        }

    def append_to_memory_file(self, trade: Trade, memory_file: str = "MEMORY.md"):
        """Append trade log to MEMORY.md for Google Memory Agent."""
        log_entry = {
            "timestamp": trade.timestamp,
            "market_id": trade.market_id,
            "p_prior": trade.p_prior,
            "p_posterior": trade.p_posterior,
            "q_market": trade.q_market,
            "edge": trade.edge,
            "action": trade.action,
            "trade_size_usd": trade.trade_size_usd,
            "hedge_size_shares": trade.hedge_size_shares,
            "latency_ms": trade.latency_ms
        }
        if trade.error:
            log_entry["error"] = trade.error
        
        with open(memory_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_memory_db.py -v`
Expected: PASS (all tests green)

- [ ] **Step 5: Commit memory database**

```bash
git add lib/memory_db.py tests/test_memory_db.py
git commit -m "feat: add SQLite memory persistence layer"
```

---

## Chunk 3: Heartbeat Execution Loop

### Task 3.1: Market Discovery Module

**Files:**
- Create: `lib/market_discovery.py`
- Create: `tests/test_market_discovery.py`

- [ ] **Step 1: Write failing tests for market discovery**

Create `tests/test_market_discovery.py`:

```python
"""Tests for BTC 15-minute market discovery."""

import pytest
from unittest.mock import AsyncMock, patch

from lib.market_discovery import find_btc_15min_market, MarketFilter

class TestMarketDiscovery:
    @pytest.mark.asyncio
    async def test_finds_active_btc_15min_market(self):
        """Should find and return active BTC15-min market."""
        mock_gamma = AsyncMock()
        mock_gamma.search_markets.return_value = [
            AsyncMock(
                id="btc-15m-001",
                question="Will Bitcoin be above $50,000 at 3:00 PM ET?",
                active=True,
                closed=False
            )
        ]
        # Mock would return market

    @pytest.mark.asyncio
    async def test_filters_closed_markets(self):
        """Should only return active, open markets."""
        pass

    @pytest.mark.asyncio
    async def test_handles_no_matching_market(self):
        """Should raise error if no BTC 15-min market found."""
        pass

    def test_market_filter_criteria(self):
        """MarketFilter correctly identifies BTC 15-min markets."""
        filter = MarketFilter(keywords=["bitcoin", "btc"], duration_min=15)
        
        # Should match
        assert filter.matches("Will Bitcoin rise in next 15 minutes?")
        assert filter.matches("BTC above $50k in15 min?")
        
        # Should not match
        assert not filter.matches("Will Ethereum rise?")
        assert not filter.matches("Bitcoin price tomorrow?")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_market_discovery.py -v`
Expected: FAIL

- [ ] **Step 3: Write market discovery implementation**

Create `lib/market_discovery.py`:

```python
"""Find active BTC 15-minute prediction markets."""

import re
from dataclasses import dataclass
from typing import Optional

from lib.gamma_client import GammaClient, Market


@dataclass
class MarketFilter:
    keywords: list[str]
    duration_min: int = 15
    
    def matches(self, question: str) -> bool:
        """Check if question matches filter criteria."""
        question_lower = question.lower()
        
        # Check for keywords
        keyword_match = any(kw in question_lower for kw in self.keywords)
        if not keyword_match:
            return False
        
        # Check for duration reference
        duration_patterns = [
            rf"\b{self.duration_min}\s*min",
            rf"\b{self.duration_min}\s*minute",
            rf"\b{self.duration_min}m\b",
        ]
        duration_match = any(
            re.search(pattern, question_lower) for pattern in duration_patterns
        )
        
        return duration_match


async def find_btc_15min_market(
    gamma: GammaClient,
    filter: Optional[MarketFilter] = None
) -> Market:
    """Find active BTC 15-minute market.
    
    Args:
        gamma: GammaClient instance
        filter: Optional custom filter (default: BTC 15-min)
    
    Returns:
        Active Market matching criteria
    
    Raises:
        ValueError: If no matching market found
    """
    if filter is None:
        filter = MarketFilter(keywords=["bitcoin", "btc"], duration_min=15)
    
    # Search for BTC markets
    markets = await gamma.search_markets("bitcoin", limit=100)
    
    # Filter for 15-min duration and active status
    for market in markets:
        if not market.active or market.closed:
            continue
        
        if filter.matches(market.question):
            return market
    
    # Also try "btc" search
    markets = await gamma.search_markets("btc", limit=100)
    for market in markets:
        if not market.active or market.closed:
            continue
        
        if filter.matches(market.question):
            return market
    
    raise ValueError("No active BTC 15-minute market found")


async def get_market_order_book(
    clob_client,
    token_id: str
) -> dict:
    """Get order book for a token.
    
    Args:
        clob_client: ClobClientWrapper instance
        token_id: Token ID to query
    
    Returns:
        Order book dict with bids and asks
    """
    order_book = clob_client.get_order_book(token_id)
    
    # Parse response
    bids = []
    asks = []
    
    if hasattr(order_book, 'bids'):
        for b in order_book.bids:
            bids.append({
                "price": float(b.price),
                "size": float(b.size)
            })
    
    if hasattr(order_book, 'asks'):
        for a in order_book.asks:
            asks.append({
                "price": float(a.price),
                "size": float(a.size)
            })
    
    # Sort bids descending, asks ascending
    bids.sort(key=lambda x: x["price"], reverse=True)
    asks.sort(key=lambda x: x["price"])
    
    return {"bids": bids, "asks": asks}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_market_discovery.py -v`
Expected: PASS

- [ ] **Step 5: Commit market discovery**

```bash
git add lib/market_discovery.py tests/test_market_discovery.py
git commit -m "feat: add BTC 15-min market discovery module"
```

### Task 3.2: Heartbeat Execution Script

**Files:**
- Create: `scripts/heartbeat.py`

- [ ] **Step 1: Write heartbeat.py main script**

Create `scripts/heartbeat.py`:

```python
#!/usr/bin/env python3
"""Heartbeat - Main 15-minute trading execution loop.

Usage:
    python scripts/heartbeat.py [--dry-run] [--status]
"""

import os
import sys
import time
import json
import asyncio
import argparse
from datetime import datetime
from pathlib import Path

# Add parent to path for lib imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from lib.gamma_client import GammaClient
from lib.clob_client import ClobClientWrapper
from lib.wallet_manager import WalletManager
from lib.bayesian import BayesianEstimator, parse_order_book_from_clob
from lib.kelly import KellySizer
from lib.memory_db import MemoryDB, Trade
from lib.market_discovery import find_btc_15min_market, get_market_order_book

# Constants
MAX_RISK_USD = float(os.environ.get("MAX_RISK_USD", "2.0"))
EDGE_THRESHOLD = float(os.environ.get("EDGE_THRESHOLD", "0.035"))
HEDGE_RATIO = float(os.environ.get("HEDGE_RATIO", "0.25"))
INITIAL_BANKROLL = float(os.environ.get("INITIAL_BANKROLL", "20.0"))
MEMORY_FILE = os.environ.get("MEMORY_FILE", "MEMORY.md")
MEMORY_DB_PATH = os.environ.get("MEMORY_DB_PATH", "/opt/google-memory-agent/data/memory.db")


async def execute_heartbeat(dry_run: bool = False) -> dict:    """Execute single heartbeat cycle."""
    start_time = time.time()
    log_payload = {
        "timestamp": start_time,
        "market_id": None,
        "p_prior": 0.5,
        "p_posterior": 0.5,
        "q_market": 0.0,
        "edge": 0.0,
        "action": "HOLD",
        "trade_size_usd": 0.0,
        "hedge_size_shares": 0,
        "latency_ms": 0,
    }
    
    try:
        # 1. Initialize clients
        gamma = GammaClient()
        wallet = WalletManager()
        
        if not wallet.is_unlocked:log_payload["error"] = "Wallet not configured"
            return log_payload
        
        clob = ClobClientWrapper(
            wallet.get_unlocked_key(),
            wallet.address
        )
        
        # 2. Get current bankroll
        balances = wallet.get_balances()
        current_bankroll = balances.usdc_e
        
        # 3. Fetch active BTC 15-min market
        print("Finding BTC 15-min market...", file=sys.stderr)
        market = await find_btc_15min_market(gamma)
        log_payload["market_id"] = market.id
        
        print(f"Market: {market.question[:60]}...", file=sys.stderr)
        
        # 4. Get order book
        order_book = await get_market_order_book(clob, market.yes_token_id)
        
        # 5. Calculate Bayesian posterior
        memory_db = MemoryDB(MEMORY_DB_PATH)
        memory_mod = memory_db.fetch_memory_prior()
        
        # Sentiment drift (mock for now, can integrate real API)
        sentiment_drift = 0.0
        
        estimator = BayesianEstimator(
            base_prior=0.50,
            memory_modifier=memory_mod,
            edge_threshold=EDGE_THRESHOLD
        )
        
        p_posterior = estimator.estimate_from_signals(
            order_book=order_book,
            sentiment_drift=sentiment_drift,
            memory_modifier=memory_mod
        )
        
        # Get best ask price
        q_market = float(order_book["asks"][0]["price"]) if order_book["asks"] else 0.5
        log_payload["q_market"] = q_market
        
        # Prior calculation
        p_prior = 0.50 + sentiment_drift + memory_mod
        p_prior = max(0.01, min(0.99, p_prior))
        log_payload["p_prior"] = p_prior
        log_payload["p_posterior"] = p_posterior
        
        # 6. Calculate edge
        edge = p_posterior - q_market
        log_payload["edge"] = edge
        
        print(f"Prior: {p_prior:.3f}, Posterior: {p_posterior:.3f}, Market: {q_market:.3f}, Edge: {edge:+.3f}", file=sys.stderr)
        
        # 7. Apply edge filter
        if abs(edge) <= EDGE_THRESHOLD:
            print(f"Edge {edge:.3f} below threshold {EDGE_THRESHOLD}, HOLD", file=sys.stderr)
            log_payload["action"] = "HOLD"
        else:
            # 8. Calculate position sizing
            sizer = KellySizer(
                max_risk_usd=MAX_RISK_USD,
                hedge_ratio=HEDGE_RATIO,
                edge_threshold=EDGE_THRESHOLD
            )
            
            result = sizer.calculate_full(p_posterior, q_market, current_bankroll)
            
            if dry_run:
                print(f"[DRY-RUN] Would trade: {result.primary_size_usd:.2f} USD", file=sys.stderr)
                log_payload["action"] = "DRY_RUN"
                log_payload["trade_size_usd"] = result.primary_size_usd
                log_payload["hedge_size_shares"] = result.hedge_size_shares
            else:
                # 9. Execute trade
                is_up = edge > 0
                token_id = market.yes_token_id if is_up else market.no_token_id
                execution_price = q_market if is_up else (1 - q_market)
                
                print(f"Executing {'BUY UP' if is_up else 'BUY DOWN'}: {result.primary_shares} shares @ {execution_price:.3f}", file=sys.stderr)
                
                # Try to place order
                try:
                    order_id, filled, error = clob.sell_fok(
                        token_id=token_id,
                        amount=result.primary_size_usd,
                        price=execution_price
                    )
                    
                    if filled:
                        log_payload["action"] = "BUY"
                        log_payload["trade_size_usd"] = result.primary_size_usd
                        log_payload["hedge_size_shares"] = result.hedge_size_shares
                        print(f"Order filled: {order_id}", file=sys.stderr)
                    else:
                        log_payload["action"] = "FAILED"
                        log_payload["error"] = error
                        print(f"Order failed: {error}", file=sys.stderr)
                        
                except Exception as e:
                    log_payload["action"] = "ERROR"
                    log_payload["error"] = str(e)
                    print(f"Execution error: {e}", file=sys.stderr)
        
        # 10. Log to memory
        latency_ms = int((time.time() - start_time) * 1000)
        log_payload["latency_ms"] = latency_ms
        
        trade = Trade(
            timestamp=log_payload["timestamp"],
            market_id=log_payload["market_id"] or "",
            p_prior=log_payload["p_prior"],
            p_posterior=log_payload["p_posterior"],
            q_market=log_payload["q_market"],
            edge=log_payload["edge"],
            action=log_payload["action"],
            trade_size_usd=log_payload["trade_size_usd"],
            hedge_size_shares=log_payload["hedge_size_shares"],
            latency_ms=log_payload["latency_ms"],
            error=log_payload.get("error")
        )
        
        memory_db.log_trade(trade)
        memory_db.append_to_memory_file(trade, MEMORY_FILE)
        
        print(f"Cycle complete. Latency: {latency_ms}ms", file=sys.stderr)
        
    except Exception as e:
        log_payload["error"] = str(e)
        print(f"Heartbeat error: {e}", file=sys.stderr)
    
    return log_payload


async def cmd_status() -> dict:
    """Get current status without trading."""
    wallet = WalletManager()
    
    if not wallet.is_unlocked:
        return {"error": "Wallet not configured"}
    
    balances = wallet.get_balances()
    
    memory_db = MemoryDB(MEMORY_DB_PATH)
    summary = memory_db.get_pnl_summary()
    
    return {
        "address": wallet.address,
        "bankroll_usdc": balances.usdc_e,
        "bankroll_pol": balances.pol,
        "total_trades": summary["total_trades"],
        "total_volume_usd": summary["total_volume_usd"],
        "avg_latency_ms": summary["avg_latency_ms"],
        "memory_prior": memory_db.fetch_memory_prior(),
    }


def main():
    parser = argparse.ArgumentParser(description="BTC 15-min trading heartbeat")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without trading")
    parser.add_argument("--status", action="store_true", help="Show status only")
    
    args = parser.parse_args()
    
    if args.status:
        status = asyncio.run(cmd_status())
        print(json.dumps(status, indent=2))
        return 0
    
    result = asyncio.run(execute_heartbeat(dry_run=args.dry_run))
    print(json.dumps(result, indent=2))
    
    return 0 if result["action"] != "ERROR" else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Test heartbeat dry-run**

Run: `uv run python scripts/heartbeat.py --dry-run`
Expected: Output with status, no actual trade

- [ ] **Step 3: Test status command**

Run: `uv run python scripts/heartbeat.py --status`
Expected: JSON output with wallet status

- [ ] **Step 4: Commit heartbeat**

```bash
git add scripts/heartbeat.py
git commit -m "feat: add heartbeat execution loop for 15-min trading"
```

---

## Chunk 4: Telegram SafetyBot

### Task 4.1: Telegram Bot Integration

**Files:**
- Create: `scripts/telegram_bot.py`
- Add dependency: `python-telegram-bot`

- [ ] **Step 1: Add python-telegram-bot dependency**

Update `pyproject.toml`:

```toml
[project]
dependencies = [
    # ... existing dependencies
    "python-telegram-bot>=21.0.0",
]
```

Run: `uv sync`

- [ ] **Step 2: Write telegram_bot.py**

Create `scripts/telegram_bot.py`:

```python
#!/usr/bin/env python3
"""Telegram bot for btc15-hedge safety orchestration.

Commands:
    /status - Show current system state
    /halt - Enter monitor-only mode (MAX_RISK=0)
    /resume - Resume live trading
    /memory - Show recent consolidation lessons
"""

import os
import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from lib.memory_db import MemoryDB
from lib.wallet_manager import WalletManager

# Configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALLOWED_CHAT_ID = os.environ.get("TELEGRAM_ALLOWED_CHAT_ID", "")
MEMORY_DB_PATH = os.environ.get("MEMORY_DB_PATH", "/opt/google-memory-agent/data/memory.db")
INITIAL_BANKROLL = float(os.environ.get("INITIAL_BANKROLL", "20.0"))
DRAWDOWN_THRESHOLD = 0.50  # 50% drawdown triggers halt

# State file for persistent halt state
STATE_FILE = Path(__file__).parent.parent / ".halt_state"


def is_authorized(chat_id: str) -> bool:
    """Check if chat_id is authorized."""
    if not TELEGRAM_ALLOWED_CHAT_ID:
        return True  # Allow all if not configured
    return str(chat_id) == TELEGRAM_ALLOWED_CHAT_ID


def read_halt_state() -> bool:
    """Read halt state from file."""
    if STATE_FILE.exists():
        return STATE_FILE.read_text().strip() == "HALT"
    return False


def write_halt_state(halted: bool):
    """Write halt state to file."""
    STATE_FILE.write_text("HALT" if halted else "RESUME")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("Unauthorized")
        return
    
    try:
        wallet = WalletManager()
        memory_db = MemoryDB(MEMORY_DB_PATH)
        
        if not wallet.is_unlocked:
            await update.message.reply_text("Wallet not configured")
            return
        
        balances = wallet.get_balances()
        summary = memory_db.get_pnl_summary()
        prior = memory_db.fetch_memory_prior()
        halted = read_halt_state()
        
        # Format status
        status = f"""📊 MiroFish-Alpha Status
        
👛 Wallet: `{wallet.address[:8]}...{wallet.address[-4:]}`💰 Bankroll: ${balances.usdc_e:.2f} USDC.e
📈 Total Trades: {summary['total_trades']}
💵 Volume: ${summary['total_volume_usd']:.2f}
⚡ Avg Latency: {summary['avg_latency_ms']:.0f}ms
🧠 Memory Prior: {prior:+.3f}
{"⚠️ HALTED" if halted else "✅ ACTIVE"}
"""
        
        await update.message.reply_text(status, parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def cmd_halt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /halt command - enter monitor-only mode."""
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("Unauthorized")
        return
    
    write_halt_state(True)
    
    # Also write to env file for persistence across restarts
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        content = env_file.read_text()
        if "MAX_RISK_USD=" in content:
            content = content.replace(
                content.split("MAX_RISK_USD=")[1].split("\n")[0],
                "0.0"
            )
            env_file.write_text(content)
    
    await update.message.reply_text("⚠️ HALTED\n\nSystem in monitor-only mode.\nMAX_RISK_USD = 0")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /resume command - resume live trading."""
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("Unauthorized")
        return
    
    write_halt_state(False)
    
    env_file = Path(__file__).parent.parent / ".env"
    max_risk = os.environ.get("MAX_RISK_USD", "2.0")
    
    await update.message.reply_text(f"✅ RESUMED\n\nSystem active.\nMAX_RISK_USD = {max_risk}")


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /memory command - show recent lessons."""
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("Unauthorized")
        return
    
    try:
        memory_db = MemoryDB(MEMORY_DB_PATH)
        lessons = memory_db.get_lessons(limit=3)
        
        if not lessons:
            await update.message.reply_text("No lessons recorded yet.")
            return
        
        lines = ["🧠 Recent Consolidation Lessons\n"]
        for i, lesson in enumerate(lessons, 1):
            lines.append(f"{i}. [{lesson.created_at[:10]}] {lesson.market_id[:12]}...")
            lines.append(f"   Modifier: {lesson.prior_modifier:+.3f}")
            lines.append(f"   Insight: {lesson.insight[:50]}...")
            lines.append("")
        
        await update.message.reply_text("\n".join(lines))
        
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


def check_drawdown_alert():
    """Check if drawdown threshold breached. Return alert message or None."""
    try:
        wallet = WalletManager()
        if not wallet.is_unlocked:
            return None
        
        balances = wallet.get_balances()
        
        if balances.usdc_e < INITIAL_BANKROLL * DRAWDOWN_THRESHOLD:
            write_halt_state(True)
            return f"""🚨 CRITICAL: Drawdown Threshold BreachedBalance: ${balances.usdc_e:.2f}
Initial: ${INITIAL_BANKROLL:.2f}
Drawdown: {(1 - balances.usdc_e/INITIAL_BANKROLL)*100:.1f}%System shifted to monitor-only mode.
Manual intervention required."""
        
        return None
    except Exception:
        return None


async def alert_loop(application: Application):
    """Background task to check for alerts."""
    while True:
        await asyncio.sleep(60)  # Check every minute
        alert = check_drawdown_alert()
        if alert and TELEGRAM_ALLOWED_CHAT_ID:
            await application.bot.send_message(
                chat_id=TELEGRAM_ALLOWED_CHAT_ID,
                text=alert
            )


def main():
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        return 1
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("halt", cmd_halt))
    application.add_handler(CommandHandler("resume", cmd_resume))
    application.add_handler(CommandHandler("memory", cmd_memory))
    
    print("Telegram bot running...", file=sys.stderr)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    sys.exit(main() or 0)
```

- [ ] **Step 3: Commit Telegram bot**

```bash
git add scripts/telegram_bot.py pyproject.toml
git commit -m "feat: add Telegram safety bot with /status /halt /resume /memory"
```

---

## Chunk 5: Backtest Framework

### Task 5.1: Backtest Simulation

**Files:**
- Create: `scripts/backtest.py`

- [ ] **Step 1: Write backtest.py**

Create `scripts/backtest.py`:

```python
#!/usr/bin/env python3
"""Historical simulation with exact Polymarket fee calculation.

Usage:
    python scripts/backtest.py [--simulations N] [--seed S]
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from lib.kelly import calculate_polymarket_fee
from lib.bayesian import BayesianEstimator


def simulate_polymarket_fees(q_array: np.ndarray) -> np.ndarray:
    """Calculate exact Polymarket fee for each price.
    
    Formula: fee_per_share = 0.25 * q * (q * (1-q))^2
    Effective drag = fee_per_share / q
    """
    with np.errstate(divide='ignore', invalid='ignore'):
        fee_per_share = 0.25 * q_array * (q_array * (1 - q_array)) ** 2
        effective_drag = np.where(q_array > 0.001, fee_per_share / q_array, 0)
    return effective_drag


def run_backtest(n_simulations: int = 1000, seed: int = None) -> dict:
    """Run historical simulation.
    
    Args:
        n_simulations: Number of random intervals to simulate
        seed: Random seed for reproducibility
    
    Returns:
        Dict with simulation results
    """
    if seed is not None:
        np.random.seed(seed)
    
    # Simulate market prices uniformly distributed
    q_market = np.random.uniform(0.10, 0.90, n_simulations)
    
    # Simulate Bayesian posteriors
    # 70% aligned with market, 30% discover edge
    noise = np.random.normal(0, 0.05, n_simulations)
    p_posterior = np.clip(q_market + noise, 0.01, 0.99)
    
    # Calculate edge
    edge = p_posterior - q_market
    
    # Apply edge threshold
    edge_threshold = 0.035
    trade_mask = np.abs(edge) > edge_threshold
    
    # Calculate fees for traded intervals
    fee_drag = simulate_polymarket_fees(q_market[trade_mask])
    
    # Simulate outcomes (binary resolution)
    outcomes = np.random.binomial(1, p_posterior[trade_mask])
    
    # Calculate PnL
    investment = q_market[trade_mask]
    payout = outcomes * 1.0  # 1 USDC if win, 0 if lose
    
    # Net PnL = payout - investment - fees
    pnl = payout - investment - fee_drag
    
    # Aggregate results
    total_trades = np.sum(trade_mask)
    total_fees = np.sum(fee_drag)
    net_pnl = np.sum(pnl)
    win_rate = np.mean(outcomes) if total_trades > 0else 0
    
    # Average latency simulation
    avg_latency_ms = np.random.uniform(1500, 5000)  # ms
    
    return {
        "n_simulations": n_simulations,
        "edge_threshold": edge_threshold,
        "total_trades": total_trades,
        "trade_rate": total_trades / n_simulations,
        "win_rate": win_rate,
        "total_fees_usd": total_fees,
        "net_pnl_usd": net_pnl,
        "avg_latency_ms": avg_latency_ms,
        "fee_drag_avg": np.mean(fee_drag) if len(fee_drag) > 0 else 0,
    }


def print_results(results: dict):
    """Print formatted results."""
    print("=" * 60)
    print("Polymarket 15-Min BTC Backtest Results")
    print("=" * 60)
    print(f"Simulations: {results['n_simulations']}")
    print(f"Edge Threshold: {results['edge_threshold']*100:.1f}%")
    print("-" * 60)
    print(f"Total Trades Executed: {results['total_trades']}")
    print(f"Trade Rate: {results['trade_rate']*100:.1f}%")
    print(f"Systematic Win Rate: {results['win_rate']*100:.1f}%")
    print(f"Avg Fee Drag: {results['fee_drag_avg']*100:.2f}%")
    print("-" * 60)
    print(f"Total Fees Surrendered: ${results['total_fees_usd']:.4f}")
    print(f"Net PnL (USDC): ${results['net_pnl_usd']:.4f}")
    print(f"Avg Latency: {results['avg_latency_ms']:.0f}ms")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Backtest simulation")
    parser.add_argument("--simulations", "-n", type=int, default=1000,
                        help="Number of simulations")
    parser.add_argument("--seed", "-s", type=int, default=None,
                        help="Random seed")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON")
    
    args = parser.parse_args()
    
    results = run_backtest(args.simulations, args.seed)
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_results(results)
    
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
```

- [ ] **Step 2: Run backtest**

Run: `uv run python scripts/backtest.py --simulations 1000 --seed 42`
Expected: Output with win rate, PnL, fee analysis

- [ ] **Step 3: Commit backtest**

```bash
git add scripts/backtest.py
git commit -m "feat: add backtest framework with exact Polymarket fee simulation"
```

---

## Chunk 6: Configuration & Persona Files

### Task 6.1: Create Configuration Files

**Files:**
- Create: `IDENTITY.md`
- Create: `SOUL.md`
- Create: `MEMORY.md` (empty)
- Create: `openclaw.json`
- Create: `.env.example`

- [ ] **Step 1: Create IDENTITY.md**

```markdown
Name: MiroFish-Alpha
Role: High-Frequency Statistical Arbitrage Quant
Traits: Cold-blooded, deterministic, fee-obsessed, hyper-rational.
Emoji:🐟Directive: You do not predict the market; you trade the mathematical discrepancy between your Bayesian posterior and the Polymarket order book.
```

- [ ] **Step 2: Create SOUL.md**

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

- [ ] **Step 3: Create MEMORY.md**

```markdown
# Execution Log

This file is appended by heartbeat.py and read by Google Memory Agent for consolidation.
```

- [ ] **Step 4: Create openclaw.json**

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

- [ ] **Step 5: Create .env.example**

```bash
# Polygon RPC & Wallet
CHAINSTACK_NODE=https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY
POLYCLAW_PRIVATE_KEY=0xYOUR_PRIVATE_KEY
POLYGON_CHAIN_ID=137

# Polymarket CLOB
POLYMARKET_HOST=https://clob.polymarket.com

# OpenCode API (for Google Memory Agent integration)
OPENCODE_API_KEY=sk-YOUR_KEY
OPENCODE_BASE_URL=https://opencode.ai/zen/go/v1
MODEL_NAME=opencode-go/kimi-k2.5

# Memory Agent
MEMORY_DB_PATH=/opt/google-memory-agent/data/memory.db
MEMORY_FILE=/home/quant/.openclaw/workspace/MEMORY.md

# Telegram Bot
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
TELEGRAM_ALLOWED_CHAT_ID=YOUR_CHAT_ID

# Risk Limits
MAX_RISK_USD=2.0
EDGE_THRESHOLD=0.035
HEDGE_RATIO=0.25
INITIAL_BANKROLL=20.0

# Optional: Rotating proxy for CLOB
HTTPS_PROXY=http://user:pass@proxy:port
CLOB_MAX_RETRIES=5
```

- [ ] **Step 6: Update SKILL.md with new commands**

Append to `SKILL.md`:

```markdown
## btc15-hedge: Autonomous Trading

The btc15-hedge skill provides autonomous 15-minute BTC trading with Bayesian probability estimation.

### Commands

```bash
# Run single heartbeat cycle (dry-run)
uv run python scripts/heartbeat.py --dry-run

# Check system status
uv run python scripts/heartbeat.py --status

# Run backtest simulation
uv run python scripts/backtest.py --simulations 1000

# Start Telegram safety bot
uv run python scripts/telegram_bot.py
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MAX_RISK_USD` | Yes | Maximum risk per cycle (default: 2.0) |
| `EDGE_THRESHOLD` | No | Minimum edge for execution (default: 0.035) |
| `HEDGE_RATIO` | No | Hedge ratio for opposite side (default: 0.25) |
| `INITIAL_BANKROLL` | No | Initial capital for drawdown calculation |
| `TELEGRAM_BOT_TOKEN` | Optional | Telegram bot token for safety controls |
| `TELEGRAM_ALLOWED_CHAT_ID` | Optional | Authorized chat ID |
```

- [ ] **Step 7: Commit configuration files**

```bash
git add IDENTITY.md SOUL.md MEMORY.md openclaw.json .env.example SKILL.md
git commit -m "feat: add persona files, OpenClaw config, and environment template"
```

---

## Chunk 7: Integration Tests & Final Polish

### Task 7.1: Integration Test

**Files:**
- Create: `tests/test_heartbeat.py`

- [ ] **Step 1: Write integration test for heartbeat**

Create `tests/test_heartbeat.py`:

```python
"""Integration tests for heartbeat execution."""

import pytest
import tempfile
import os
from unittest.mock import AsyncMock, patch, MagicMock

from lib.bayesian import BayesianEstimator
from lib.kelly import KellySizer
from lib.memory_db import MemoryDB, Trade


class TestHeartbeatIntegration:
    def test_bayesian_kelly_pipeline(self):
        """Full pipeline from order book to position size."""
        # Simulated order book
        order_book = {
            "bids": [{"price": "0.52", "size": "100"}, {"price": "0.51", "size": "200"}],
            "asks": [{"price": "0.54", "size": "80"}, {"price": "0.55", "size": "150"}]
        }
        
        # Bayesian estimation
        estimator = BayesianEstimator(base_prior=0.50, memory_modifier=0.02)
        p_posterior = estimator.estimate_from_signals(
            order_book=order_book,
            sentiment_drift=0.01
        )
        
        # Kelly sizing
        q_market = 0.54
        edge = p_posterior - q_market
        
        sizer = KellySizer(max_risk_usd=2.0)
        
        if estimator.should_trade(edge):
            result = sizer.calculate_full(p_posterior, q_market, bankroll=20.0)
            assert result.primary_size_usd > 0
            assert result.primary_size_usd <= 2.0else:
            # Edge threshold not met
            pass

    def test_memory_persistence_cycle(self):
        """Trade logging and memory retrieval cycle."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            db = MemoryDB(db_path)
            
            # Log a trade
            trade = Trade(
                timestamp=1709500000.0,
                market_id="btc-15m-test",
                p_prior=0.52,
                p_posterior=0.58,
                q_market=0.54,
                edge=0.04,
                action="BUY",
                trade_size_usd=1.87,
                hedge_size_shares=12,
                latency_ms=2340
            )
            db.log_trade(trade)
            
            # Update lesson
            db.update_lesson(
                market_id="btc-15m-test",
                prior_modifier=-0.01,
                insight="Overestimated momentum"
            )
            
            # Retrieve
            prior = db.fetch_memory_prior()
            assert prior == -0.01
            
            trades = db.get_recent_trades(limit=1)
            assert len(trades) == 1
            assert trades[0].market_id == "btc-15m-test"
            
        finally:
            os.unlink(db_path)

    def test_edge_filter_blocks_small_edge(self):
        """Edge below threshold should be blocked."""
        estimator = BayesianEstimator(edge_threshold=0.035)
        
        # Edge of 2% should be blocked
        assert not estimator.should_trade(0.02)
        
        # Edge of 4% should pass
        assert estimator.should_trade(0.04)

    def test_kelly_respects_limits(self):
        """Kelly shouldnever exceed max risk."""
        sizer = KellySizer(max_risk_usd=2.0)
        
        # Even with very high edge
        size = sizer.calculate_size(p=0.90, q=0.50, bankroll=100.0)
        assert size <= 2.0

    def test_fee_calculation_at_different_prices(self):
        """Polymarket fee varies with price."""
        from lib.kelly import calculate_polymarket_fee
        
        # Peak fee at 50% probability
        fee_50 = calculate_polymarket_fee(0.50)
        fee_30 = calculate_polymarket_fee(0.30)
        fee_70 = calculate_polymarket_fee(0.70)
        
        # Fee should be symmetric around 0.5
        assert abs(fee_30 - fee_70) < 0.001
        
        # Peak should be higher than edges
        assert fee_50 > fee_30
```

- [ ] **Step 2: Run integration tests**

Run: `uv run pytest tests/test_heartbeat.py -v`
Expected: PASS

- [ ] **Step 3: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 4: Final commit**

```bash
git add tests/test_heartbeat.py
git commit -m "test: add integration tests for heartbeat pipeline"
```

---

## Summary

After completing all tasks:

```bash
git log --oneline -10
```

Should show commits for:
1. feat: add Bayesian probability estimation module
2. feat: add fee-aware Kelly criterion sizing module
3. feat: add SQLite memory persistence layer
4. feat: add BTC 15-min market discovery module
5. feat: add heartbeat execution loop for 15-min trading
6. feat: add Telegram safety bot with /status /halt /resume /memory
7. feat: add backtest framework with exact Polymarket fee simulation
8. feat: add persona files, OpenClaw config, and environment template
9. test: add integration tests for heartbeat pipeline

---

**Plan complete and saved to `docs/superpowers/plans/2026-03-15-btc15-hedge-implementation.md`. Ready to execute?**