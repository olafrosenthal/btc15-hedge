"""Tests for BTC 15-minute market discovery."""

import pytest
from lib.market_discovery import MarketFilter

class TestMarketDiscovery:
    def test_market_filter_criteria(self):
        """MarketFilter correctly identifies BTC 15-min markets."""
        filter = MarketFilter(keywords=["bitcoin", "btc"], duration_min=15)
        
        # Should match
        assert filter.matches("Will Bitcoin rise in next 15 minutes?")
        assert filter.matches("BTC above $50k in 15 min?")
        assert filter.matches("Will Bitcoin be higher in 15 minutes")
        
        # Should not match
        assert not filter.matches("Will Ethereum rise?")
        assert not filter.matches("Bitcoin price tomorrow?")
        assert not filter.matches("BTC weekly outlook")