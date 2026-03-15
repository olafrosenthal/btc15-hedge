"""Tests for fee-aware Kelly criterion."""

import pytest
from lib.kelly import KellySizer, calculate_polymarket_fee

class TestKellySizer:
    def test_kelly_returns_zero_when_no_edge(self):
        sizer = KellySizer(max_risk_usd=2.0)
        size = sizer.calculate_size(p=0.48, q=0.50, bankroll=20.0)
        assert size == 0.0

    def test_kelly_sizes_proportionally_to_edge(self):
        sizer = KellySizer(max_risk_usd=2.0, half_kelly=True)
        size_small = sizer.calculate_size(p=0.52, q=0.50, bankroll=20.0)
        size_large = sizer.calculate_size(p=0.60, q=0.50, bankroll=20.0)
        assert size_large > size_small

    def test_kelly_respects_max_risk_cap(self):
        sizer = KellySizer(max_risk_usd=2.0, half_kelly=True)
        size = sizer.calculate_size(p=0.95, q=0.40, bankroll=100.0)
        assert size <= 2.0

    def test_kelly_obfuscates_size(self):
        sizer = KellySizer(max_risk_usd=2.0, half_kelly=True, obfuscate=True)
        sizes = [sizer.calculate_size(p=0.60, q=0.50, bankroll=20.0) for _ in range(10)]
        assert len(set(sizes)) > 1

    def test_kelly_no_obfuscation_when_disabled(self):
        sizer = KellySizer(max_risk_usd=2.0, half_kelly=True, obfuscate=False)
        sizes = [sizer.calculate_size(p=0.60, q=0.50, bankroll=20.0) for _ in range(5)]
        assert len(set(sizes)) == 1

    def test_polymarket_fee_calculation(self):
        fee_50 = calculate_polymarket_fee(0.50)
        fee_10 = calculate_polymarket_fee(0.10)
        fee_90 = calculate_polymarket_fee(0.90)
        assert fee_50 > fee_10
        assert fee_50 > fee_90
        assert abs(fee_50 - 0.03125) < 0.001

    def test_effective_drag_calculation(self):
        sizer = KellySizer(max_risk_usd=2.0)
        drag_50 = sizer.calculate_effective_drag(0.50)
        drag_70 = sizer.calculate_effective_drag(0.70)
        assert drag_50 > drag_70

    def test_hedge_size_calculation(self):
        sizer = KellySizer(max_risk_usd=2.0, hedge_ratio=0.25)
        primary_shares = 100
        hedge_shares = sizer.calculate_hedge_size(primary_shares)
        assert hedge_shares == 25