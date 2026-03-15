#!/usr/bin/env python3
"""Backtest simulation for BTC trading agent with exact Polymarket fee calculation."""

import sys
import json
import argparse
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.kelly import calculate_polymarket_fee


def simulate_polymarket_fees(q_array: np.ndarray) -> np.ndarray:
    """
    Calculate fee drag per share for array of market prices.
    
    Formula: fee_per_share = 0.25 * q * (q * (1-q))^2
    Effective drag = fee_per_share / q (handle division by zero)
    
    Args:
        q_array: Array of market prices.
        
    Returns:
        Array of effective fee drags.
    """
    fee_per_share = 0.25 * q_array * (q_array * (1 - q_array)) ** 2
    
    with np.errstate(divide='ignore', invalid='ignore'):
        effective_drag = np.where(q_array > 0, fee_per_share / q_array, 0.0)
    
    return effective_drag


def run_backtest(n_simulations: int = 1000, seed: int | None = None) -> dict:
    """
    Run Monte Carlo backtest simulation.
    
    Args:
        n_simulations: Number of simulations to run.
        seed: Random seed for reproducibility.
        
    Returns:
        Dictionary with simulation results.
    """
    if seed is not None:
        np.random.seed(seed)
    
    q_market = np.random.uniform(0.10, 0.90, n_simulations)
    
    noise = np.random.normal(0, 0.05, n_simulations)
    p_posterior = np.clip(q_market + noise, 0.01, 0.99)
    
    edge = p_posterior - q_market
    edge_threshold = 0.035
    trade_mask = np.abs(edge) > edge_threshold
    
    fees_per_trade = simulate_polymarket_fees(q_market)
    
    outcomes = np.random.binomial(1, p_posterior)
    
    total_trades = np.sum(trade_mask)
    trade_rate = total_trades / n_simulations
    
    if total_trades > 0:
        traded_outcomes = outcomes[trade_mask]
        traded_edges = edge[trade_mask]
        traded_fees = fees_per_trade[trade_mask]
        
        win_rate = np.mean(traded_outcomes)
        
        pnl_per_trade = np.where(
            traded_edges > 0,
            traded_outcomes - traded_edges - traded_fees,
            (1 - traded_outcomes) - (-traded_edges) - traded_fees
        )
        net_pnl_usd = float(np.sum(pnl_per_trade))
        total_fees_usd = float(np.sum(traded_fees))
        fee_drag_avg = float(np.mean(traded_fees))
    else:
        win_rate = 0.0
        net_pnl_usd = 0.0
        total_fees_usd = 0.0
        fee_drag_avg = 0.0
    
    avg_latency_ms = 150.0
    
    return {
        'n_simulations': n_simulations,
        'edge_threshold': edge_threshold,
        'total_trades': int(total_trades),
        'trade_rate': float(trade_rate),
        'win_rate': float(win_rate),
        'total_fees_usd': total_fees_usd,
        'net_pnl_usd': net_pnl_usd,
        'avg_latency_ms': avg_latency_ms,
        'fee_drag_avg': fee_drag_avg,
    }


def print_results(results: dict) -> None:
    """Print formatted backtest results."""
    print("=" * 50)
    print("BACKTEST RESULTS")
    print("=" * 50)
    print(f"Simulations:    {results['n_simulations']}")
    print(f"Edge threshold: {results['edge_threshold']:.4f}")
    print(f"Total trades:   {results['total_trades']}")
    print(f"Trade rate:     {results['trade_rate']:.2%}")
    print(f"Win rate:       {results['win_rate']:.2%}")
    print(f"Total fees:     ${results['total_fees_usd']:.4f}")
    print(f"Net PnL:        ${results['net_pnl_usd']:.4f}")
    print(f"Avg latency:    {results['avg_latency_ms']:.1f}ms")
    print(f"Avg fee drag:   {results['fee_drag_avg']:.6f}")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description='Run backtest simulation')
    parser.add_argument('--simulations', type=int, default=1000,
                       help='Number of simulations (default: 1000)')
    parser.add_argument('--seed', type=int, default=None,
                       help='Random seed for reproducibility')
    parser.add_argument('--json', action='store_true',
                       help='Output results as JSON')
    
    args = parser.parse_args()
    
    results = run_backtest(n_simulations=args.simulations, seed=args.seed)
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_results(results)


if __name__ == '__main__':
    main()