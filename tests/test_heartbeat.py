"""Integration tests for heartbeat execution."""

import pytest
import tempfile
import os
from lib.bayesian import BayesianEstimator
from lib.kelly import KellySizer, calculate_polymarket_fee
from lib.memory_db import MemoryDB, Trade


class TestHeartbeatIntegration:
    def test_bayesian_kelly_pipeline(self):
        """Full pipeline from order book to position size."""
        order_book = {
            "bids": [{"price": "0.52", "size": "100"}, {"price": "0.51", "size": "200"}],
            "asks": [{"price": "0.54", "size": "80"}, {"price": "0.55", "size": "150"}]
        }
        estimator = BayesianEstimator(base_prior=0.50, memory_modifier=0.02)
        p_posterior = estimator.estimate_from_signals(order_book=order_book, sentiment_drift=0.01)
        q_market = 0.54
        edge = p_posterior - q_market
        sizer = KellySizer(max_risk_usd=2.0, edge_threshold=0.001)
        if estimator.should_trade(edge):
            result = sizer.calculate_full(p_posterior, q_market, bankroll=20.0)
            assert result.primary_size_usd > 0
            assert result.primary_size_usd <= 2.0

    def test_memory_persistence_cycle(self):
        """Trade logging and memory retrieval cycle."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            db = MemoryDB(db_path)
            trade = Trade(
                timestamp=1709500000.0, market_id="btc-15m-test", p_prior=0.52,
                p_posterior=0.58, q_market=0.54, edge=0.04, action="BUY",
                trade_size_usd=1.87, hedge_size_shares=12, latency_ms=2340
            )
            db.log_trade(trade)
            db.update_lesson("btc-15m-test", -0.01, "Overestimated momentum")
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
        assert not estimator.should_trade(0.02)
        assert estimator.should_trade(0.04)

    def test_kelly_respects_limits(self):
        """Kelly should never exceed max risk."""
        sizer = KellySizer(max_risk_usd=2.0)
        size = sizer.calculate_size(p=0.90, q=0.50, bankroll=100.0)
        assert size <= 2.0

    def test_fee_calculation_at_different_prices(self):
        """Polymarket fee varies with price."""
        fee_50 = calculate_polymarket_fee(0.50)
        fee_30 = calculate_polymarket_fee(0.30)
        fee_70 = calculate_polymarket_fee(0.70)
        assert abs(fee_30 - fee_70) < 0.001
        assert fee_50 > fee_30