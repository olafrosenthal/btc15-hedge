"""SQLite memory persistence for trading history and lessons."""

import sqlite3
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

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
    id: int
    created_at: str
    market_id: str
    prior_modifier: float
    insight: str
    win_count: int
    loss_count: int


class MemoryDB:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._conn = None
        self._ensure_tables()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _ensure_tables(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                market_id TEXT NOT NULL,
                p_prior REAL NOT NULL,
                p_posterior REAL NOT NULL,
                q_market REAL NOT NULL,
                edge REAL NOT NULL,
                action TEXT NOT NULL,
                trade_size_usd REAL NOT NULL,
                hedge_size_shares INTEGER NOT NULL,
                latency_ms INTEGER NOT NULL,
                error TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                market_id TEXT NOT NULL,
                prior_modifier REAL NOT NULL,
                insight TEXT NOT NULL,
                win_count INTEGER DEFAULT 0,
                loss_count INTEGER DEFAULT 0
            )
        """)
        conn.commit()

    def table_exists(self, table_name: str) -> bool:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return cursor.fetchone() is not None

    def log_trade(self, trade: Trade):
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO trades (timestamp, market_id, p_prior, p_posterior, q_market,
                edge, action, trade_size_usd, hedge_size_shares, latency_ms, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade.timestamp, trade.market_id, trade.p_prior, trade.p_posterior,
            trade.q_market, trade.edge, trade.action, trade.trade_size_usd,
            trade.hedge_size_shares, trade.latency_ms, trade.error
        ))
        conn.commit()

    def update_lesson(self, market_id: str, prior_modifier: float, insight: str,
                      win_count: int = 0, loss_count: int = 0):
        conn = self._get_conn()
        created_at = datetime.now(timezone.utc).isoformat()
        conn.execute("""
            INSERT INTO lessons (created_at, market_id, prior_modifier, insight,
                win_count, loss_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (created_at, market_id, prior_modifier, insight, win_count, loss_count))
        conn.commit()

    def fetch_memory_prior(self) -> float:
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT prior_modifier FROM lessons
            ORDER BY id DESC LIMIT 1
        """)
        row = cursor.fetchone()
        return row["prior_modifier"] if row else 0.0

    def get_lessons(self, limit: int = 10) -> list[Lesson]:
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT id, created_at, market_id, prior_modifier, insight,
                   win_count, loss_count
            FROM lessons
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        return [
            Lesson(
                id=row["id"],
                created_at=row["created_at"],
                market_id=row["market_id"],
                prior_modifier=row["prior_modifier"],
                insight=row["insight"],
                win_count=row["win_count"],
                loss_count=row["loss_count"]
            )
            for row in cursor.fetchall()
        ]

    def get_recent_trades(self, limit: int = 100) -> list[Trade]:
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT timestamp, market_id, p_prior, p_posterior, q_market, edge,
                   action, trade_size_usd, hedge_size_shares, latency_ms, error
            FROM trades
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        return [
            Trade(
                timestamp=row["timestamp"],
                market_id=row["market_id"],
                p_prior=row["p_prior"],
                p_posterior=row["p_posterior"],
                q_market=row["q_market"],
                edge=row["edge"],
                action=row["action"],
                trade_size_usd=row["trade_size_usd"],
                hedge_size_shares=row["hedge_size_shares"],
                latency_ms=row["latency_ms"],
                error=row["error"]
            )
            for row in cursor.fetchall()
        ]

    def get_pnl_summary(self) -> dict:
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total_trades,
                COALESCE(SUM(trade_size_usd), 0) as total_volume_usd,
                COALESCE(AVG(latency_ms), 0) as avg_latency_ms
            FROM trades
        """)
        row = cursor.fetchone()
        return {
            "total_trades": row["total_trades"],
            "total_volume_usd": row["total_volume_usd"],
            "avg_latency_ms": row["avg_latency_ms"]
        }

    def append_to_memory_file(self, trade: Trade, memory_file: str = "MEMORY.md"):
        log_entry = {
            "timestamp": trade.timestamp,
            "market_id": trade.market_id,
            "action": trade.action,
            "edge": trade.edge,
            "p_prior": trade.p_prior,
            "p_posterior": trade.p_posterior,
            "q_market": trade.q_market,
            "trade_size_usd": trade.trade_size_usd,
            "hedge_size_shares": trade.hedge_size_shares,
            "latency_ms": trade.latency_ms,
            "error": trade.error
        }
        with open(memory_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")