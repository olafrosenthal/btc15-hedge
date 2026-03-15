"""Fee-aware Kelly criterion for position sizing."""

from dataclasses import dataclass
import random

FEE_RATE_CONSTANT = 0.25
FEE_RATE_EXPONENT = 2
DEFAULT_MAX_RISK_USD = 2.0
DEFAULT_HEDGE_RATIO = 0.25
DEFAULT_EDGE_THRESHOLD = 0.035


def calculate_polymarket_fee(q: float) -> float:
    return FEE_RATE_CONSTANT * 2 * (q * (1 - q)) ** FEE_RATE_EXPONENT


@dataclass
class KellyResult:
    primary_size_usd: float
    primary_shares: int
    hedge_shares: int
    effective_fee: float
    edge_after_fees: float


class KellySizer:
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
        return calculate_polymarket_fee(q)

    def calculate_size(self, p: float, q: float, bankroll: float) -> float:
        fee = self.calculate_effective_drag(q)
        edge = p - q - fee
        
        if edge <= self.edge_threshold:
            return 0.0
        
        b = (1 - q) / q if q > 0 else float('inf')
        
        if b <= 0:
            return 0.0
            
        f_star = p - (1 - p) / b
        
        if f_star <= 0:
            return 0.0
            
        if self.half_kelly:
            f_star = f_star / 2
        
        size = f_star * bankroll
        
        if self.obfuscate:
            size = size * (1 + random.uniform(-0.05, 0.05))
        
        return min(size, self.max_risk_usd)

    def calculate_shares(self, size_usd: float, price: float) -> int:
        if price <= 0:
            return 0
        return int(size_usd / price)

    def calculate_hedge_size(self, primary_shares: int) -> int:
        return int(primary_shares * self.hedge_ratio)

    def calculate_full(self, p: float, q: float, bankroll: float) -> KellyResult:
        size_usd = self.calculate_size(p, q, bankroll)
        shares = self.calculate_shares(size_usd, q)
        hedge_shares = self.calculate_hedge_size(shares)
        fee = self.calculate_effective_drag(q)
        edge = p - q - fee
        
        return KellyResult(
            primary_size_usd=size_usd,
            primary_shares=shares,
            hedge_shares=hedge_shares,
            effective_fee=fee,
            edge_after_fees=edge,
        )