"""Bayesian probability estimation for BTC trading signals."""

EDGE_THRESHOLD = 0.035


def parse_order_book_from_clob(response: dict) -> dict:
    """Parse CLOB API response into standardized order book format."""
    if not response:
        return {"bids": [], "asks": []}
    
    bids = []
    asks = []
    
    if "bids" in response:
        for bid in response["bids"]:
            bids.append({"size": str(bid.get("size", "0"))})
    
    if "asks" in response:
        for ask in response["asks"]:
            asks.append({"size": str(ask.get("size", "0"))})
    
    return {"bids": bids, "asks": asks}


class BayesianEstimator:
    """Bayesian probability estimator for trading signals."""
    
    def __init__(
        self,
        base_prior: float = 0.50,
        memory_modifier: float = 0.0,
        edge_threshold: float = EDGE_THRESHOLD
    ):
        self.base_prior = base_prior
        self.memory_modifier = memory_modifier
        self.edge_threshold = edge_threshold
    
    def adjust_prior_with_memory(self) -> float:
        """Adjust base_prior by memory_modifier, clamped to [0.01, 0.99]."""
        adjusted = self.base_prior + self.memory_modifier
        return max(0.01, min(0.99, adjusted))
    
    def calculate_order_book_skew(self, order_book: dict) -> float:
        """Calculate bid_volume / (bid_volume + ask_volume)."""
        bid_volume = sum(float(bid["size"]) for bid in order_book.get("bids", []))
        ask_volume = sum(float(ask["size"]) for ask in order_book.get("asks", []))
        
        total = bid_volume + ask_volume
        if total == 0:
            return 0.5
        
        return bid_volume / total
    
    def likelihood_from_order_book(self, order_book: dict) -> tuple[float, float]:
        """Return (skew, 1-skew) as likelihood pair."""
        skew = self.calculate_order_book_skew(order_book)
        return (skew, 1 - skew)
    
    def calculate_posterior(
        self,
        p_prior: float,
        likelihood_up: float,
        likelihood_down: float
    ) -> float:
        """Apply Bayes theorem, clamped to [0.01, 0.99]."""
        numerator = p_prior * likelihood_up
        denominator = (p_prior * likelihood_up) + ((1 - p_prior) * likelihood_down)
        
        if denominator == 0:
            return 0.5
        
        posterior = numerator / denominator
        return max(0.01, min(0.99, posterior))
    
    def calculate_edge(self, p_posterior: float, q_market: float) -> float:
        """Return p_posterior - q_market."""
        return p_posterior - q_market
    
    def should_trade(self, edge: float) -> bool:
        """Return True if abs(edge) > edge_threshold."""
        return abs(edge) > self.edge_threshold
    
    def estimate_from_signals(
        self,
        order_book: dict,
        sentiment_drift: float = 0.0,
        memory_modifier: float = 0.0
    ) -> float:
        """Full pipeline returning posterior from order book signals."""
        self.memory_modifier = memory_modifier + sentiment_drift
        p_prior = self.adjust_prior_with_memory()
        likelihood_up, likelihood_down = self.likelihood_from_order_book(order_book)
        return self.calculate_posterior(p_prior, likelihood_up, likelihood_down)