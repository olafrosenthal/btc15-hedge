"""Tests for SQLite memory persistence."""

import os
import tempfile
import pytest
from lib.memory_db import MemoryDB, Trade, Lesson

class TestMemoryDB:
    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        os.unlink(db_path)

    def test_init_creates_tables(self, temp_db):
        db = MemoryDB(temp_db)
        assert db.table_exists("trades")
        assert db.table_exists("lessons")

    def test_log_trade_stores_record(self, temp_db):
        db = MemoryDB(temp_db)
        trade = Trade(
            timestamp=1709500000.0, market_id="btc-15m-test", p_prior=0.52,
            p_posterior=0.58, q_market=0.54, edge=0.04, action="BUY",
            trade_size_usd=1.87, hedge_size_shares=12, latency_ms=2340
        )
        db.log_trade(trade)
        trades = db.get_recent_trades(limit=1)
        assert len(trades) == 1
        assert trades[0].market_id == "btc-15m-test"
        assert trades[0].edge == 0.04

    def test_update_lesson_stores_modifier(self, temp_db):
        db = MemoryDB(temp_db)
        db.update_lesson(market_id="btc-15m-test", prior_modifier=-0.02, insight="test")
        lessons = db.get_lessons(limit=1)
        assert len(lessons) == 1
        assert lessons[0].prior_modifier == -0.02

    def test_fetch_memory_prior_returns_latest(self, temp_db):
        db = MemoryDB(temp_db)
        db.update_lesson("m1", 0.01, "First")
        db.update_lesson("m2", -0.02, "Second")
        db.update_lesson("m3", 0.03, "Third")
        prior = db.fetch_memory_prior()
        assert prior == 0.03

    def test_fetch_memory_prior_returns_zero_when_empty(self, temp_db):
        db = MemoryDB(temp_db)
        prior = db.fetch_memory_prior()
        assert prior == 0.0

    def test_get_pnl_summary(self, temp_db):
        db = MemoryDB(temp_db)
        db.log_trade(Trade(timestamp=1.0, market_id="m1", p_prior=0.5, p_posterior=0.6,
            q_market=0.5, edge=0.1, action="BUY", trade_size_usd=2.0, hedge_size_shares=5, latency_ms=100))
        db.log_trade(Trade(timestamp=2.0, market_id="m2", p_prior=0.5, p_posterior=0.6,
            q_market=0.5, edge=0.1, action="BUY", trade_size_usd=1.5, hedge_size_shares=3, latency_ms=150))
        summary = db.get_pnl_summary()
        assert summary["total_trades"] == 2
        assert summary["total_volume_usd"] == 3.5