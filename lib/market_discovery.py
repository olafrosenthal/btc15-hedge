"""Market discovery for BTC 15-minute prediction markets."""

import re
from dataclasses import dataclass

from lib.gamma_client import GammaClient, Market


@dataclass
class MarketFilter:
    """Filter criteria for BTC 15-minute markets."""
    
    keywords: list[str]
    duration_min: int = 15
    
    def matches(self, question: str) -> bool:
        """Check if a market question matches the filter criteria."""
        question_lower = question.lower()
        
        has_keyword = any(kw.lower() in question_lower for kw in self.keywords)
        
        duration_patterns = [
            rf"\b{self.duration_min}\s*min(?:ute)?s?\b",
            rf"\b{self.duration_min}m\b",
        ]
        has_duration = any(re.search(pattern, question_lower) for pattern in duration_patterns)
        
        return has_keyword and has_duration


async def find_btc_15min_market(gamma: GammaClient, filter: MarketFilter = None) -> Market:
    """Find active BTC 15-minute prediction market.
    
    Args:
        gamma: GammaClient instance for Polymarket API
        filter: Optional MarketFilter (defaults to BTC 15-min)
        
    Returns:
        Matching active Market
        
    Raises:
        ValueError: If no matching market found
    """
    if filter is None:
        filter = MarketFilter(keywords=["bitcoin", "btc"], duration_min=15)
    
    for keyword in filter.keywords:
        markets = await gamma.search_markets(query=keyword, limit=100)
        
        for market in markets:
            if not market.active or market.closed:
                continue
            if not filter.matches(market.question):
                continue
            return market
    
    raise ValueError("No active BTC 15-minute market found")


async def get_market_order_book(clob_client, token_id: str) -> dict:
    """Get order book for a market token.
    
    Args:
        clob_client: Polymarket CLOB client
        token_id: Token ID to get order book for
        
    Returns:
        dict with 'bids' and 'asks' lists sorted by price
    """
    order_book = await clob_client.get_order_book(token_id)
    
    bids = []
    asks = []
    
    if order_book:
        for bid in order_book.get("bids", []):
            price = float(bid.get("price", 0))
            size = float(bid.get("size", 0))
            bids.append({"price": price, "size": size})
        
        for ask in order_book.get("asks", []):
            price = float(ask.get("price", 0))
            size = float(ask.get("size", 0))
            asks.append({"price": price, "size": size})
    
    bids.sort(key=lambda x: x["price"], reverse=True)
    asks.sort(key=lambda x: x["price"])
    
    return {"bids": bids, "asks": asks}