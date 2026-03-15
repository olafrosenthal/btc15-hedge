#!/usr/bin/env python3
"""Heartbeat execution loop for 15-minute BTC trading."""

import os
import sys
import time
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from lib.bayesian import BayesianEstimator
from lib.kelly import KellySizer
from lib.memory_db import MemoryDB, Trade
from lib.market_discovery import find_btc_15min_market, get_market_order_book
from lib.gamma_client import GammaClient
from lib.clob_client import ClobClientWrapper
from lib.wallet_manager import WalletManager

MAX_RISK_USD = float(os.environ.get("MAX_RISK_USD", "2.0"))
EDGE_THRESHOLD = float(os.environ.get("EDGE_THRESHOLD", "0.035"))
HEDGE_RATIO = float(os.environ.get("HEDGE_RATIO", "0.25"))
INITIAL_BANKROLL = float(os.environ.get("INITIAL_BANKROLL", "20.0"))
MEMORY_FILE = os.environ.get("MEMORY_FILE", "MEMORY.md")
MEMORY_DB_PATH = os.environ.get("MEMORY_DB_PATH", "/opt/google-memory-agent/data/memory.db")


async def execute_heartbeat(dry_run: bool = False) -> dict:
    """Execute one heartbeat cycle.
    
    Args:
        dry_run: If True, log but don't execute trades
        
    Returns:
        dict with execution log payload
    """
    start_time = time.time()
    
    gamma = GammaClient()
    wallet = WalletManager()
    
    if not wallet.is_unlocked:
        return {
            "status": "error",
            "error": "Wallet not configured",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    clob = ClobClientWrapper(wallet.get_unlocked_key(), wallet.address)
    
    balances = wallet.get_balances()
    bankroll = balances.usdc_e
    if bankroll <= 0:
        bankroll = INITIAL_BANKROLL
    
    try:
        market = await find_btc_15min_market(gamma)
    except ValueError as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    order_book = await get_market_order_book(clob, market.yes_token_id)
    
    if not order_book.get("bids") or not order_book.get("asks"):
        return {
            "status": "error",
            "error": "Empty order book",
            "market_id": market.id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    best_ask = min(ask["price"] for ask in order_book["asks"]) if order_book["asks"] else 0.5
    best_bid = max(bid["price"] for bid in order_book["bids"]) if order_book["bids"] else 0.5
    q_market = best_ask
    
    memory_db = MemoryDB(MEMORY_DB_PATH)
    memory_prior = memory_db.fetch_memory_prior()
    
    bayesian = BayesianEstimator(
        base_prior=0.5,
        memory_modifier=memory_prior,
        edge_threshold=EDGE_THRESHOLD,
    )
    
    p_posterior = bayesian.estimate_from_signals(order_book)
    edge = bayesian.calculate_edge(p_posterior, q_market)
    
    kelly = KellySizer(
        max_risk_usd=MAX_RISK_USD,
        hedge_ratio=HEDGE_RATIO,
        edge_threshold=EDGE_THRESHOLD,
    )
    
    kelly_result = kelly.calculate_full(p_posterior, q_market, bankroll)
    
    latency_ms = int((time.time() - start_time) * 1000)
    
    action = "HOLD"
    trade_size_usd = 0.0
    hedge_shares = 0
    error = None
    
    if bayesian.should_trade(edge):
        if edge > 0:
            action = "BUY_YES"
        else:
            action = "BUY_NO"
        
        trade_size_usd = kelly_result.primary_size_usd
        hedge_shares = kelly_result.hedge_shares
        
        if dry_run:
            print(f"[DRY_RUN] Would {action}: ${trade_size_usd:.4f}")
        else:
            print(f"[EXECUTE] {action}: ${trade_size_usd:.4f}")
    else:
        print(f"[SKIP] Edge {edge:.4f} below threshold {EDGE_THRESHOLD}")
    
    trade = Trade(
        timestamp=time.time(),
        market_id=market.id,
        p_prior=bayesian.base_prior,
        p_posterior=p_posterior,
        q_market=q_market,
        edge=edge,
        action=action,
        trade_size_usd=trade_size_usd,
        hedge_size_shares=hedge_shares,
        latency_ms=latency_ms,
        error=error,
    )
    
    memory_db.log_trade(trade)
    memory_db.append_to_memory_file(trade, MEMORY_FILE)
    
    return {
        "status": "success",
        "market_id": market.id,
        "market_question": market.question,
        "p_prior": bayesian.base_prior,
        "p_posterior": p_posterior,
        "q_market": q_market,
        "edge": edge,
        "action": action,
        "trade_size_usd": trade_size_usd,
        "hedge_shares": hedge_shares,
        "bankroll": bankroll,
        "latency_ms": latency_ms,
        "dry_run": dry_run,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def cmd_status() -> dict:
    """Get current status.
    
    Returns:
        dict with wallet address, balances, trade count, volume, avg latency, memory prior
    """
    wallet = WalletManager()
    
    if not wallet.is_unlocked:
        return {
            "status": "error",
            "error": "Wallet not configured",
        }
    
    balances = wallet.get_balances()
    
    memory_db = MemoryDB(MEMORY_DB_PATH)
    pnl = memory_db.get_pnl_summary()
    memory_prior = memory_db.fetch_memory_prior()
    
    return {
        "status": "success",
        "wallet_address": wallet.address,
        "balances": {
            "pol": balances.pol,
            "usdc_e": balances.usdc_e,
        },
        "trade_count": pnl["total_trades"],
        "total_volume_usd": pnl["total_volume_usd"],
        "avg_latency_ms": pnl["avg_latency_ms"],
        "memory_prior": memory_prior,
    }


def main():
    parser = argparse.ArgumentParser(description="Heartbeat execution for 15-min BTC trading")
    parser.add_argument("--dry-run", action="store_true", help="Log trades without executing")
    parser.add_argument("--status", action="store_true", help="Show current status")
    
    args = parser.parse_args()
    
    if args.status:
        result = asyncio.run(cmd_status())
    else:
        result = asyncio.run(execute_heartbeat(dry_run=args.dry_run))
    
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)