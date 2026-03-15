#!/usr/bin/env python3
"""Telegram bot for btc15-hedge safety orchestration."""
import os
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from lib.memory_db import MemoryDB
from lib.wallet_manager import WalletManager

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALLOWED_CHAT_ID = os.environ.get("TELEGRAM_ALLOWED_CHAT_ID", "")
MEMORY_DB_PATH = os.environ.get("MEMORY_DB_PATH", "/opt/google-memory-agent/data/memory.db")
INITIAL_BANKROLL = float(os.environ.get("INITIAL_BANKROLL", "20.0"))
DRAWDOWN_THRESHOLD = 0.50
STATE_FILE = Path(__file__).parent.parent / ".halt_state"


def is_authorized(chat_id: int) -> bool:
    """Check if chat ID is authorized."""
    if not TELEGRAM_ALLOWED_CHAT_ID:
        return False
    allowed_ids = [x.strip() for x in TELEGRAM_ALLOWED_CHAT_ID.split(",")]
    return str(chat_id) in allowed_ids


def read_halt_state() -> bool:
    """Read halt state from file."""
    if STATE_FILE.exists():
        return STATE_FILE.read_text().strip().lower() == "true"
    return False


def write_halt_state(halted: bool) -> None:
    """Write halt state to file."""
    STATE_FILE.write_text("true" if halted else "false")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show wallet, bankroll, trades, memory prior."""
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("Unauthorized")
        return

    lines = []

    try:
        wallet = WalletManager()
        if wallet.is_unlocked:
            balances = wallet.get_balances()
            lines.append(f"Wallet: {wallet.address}")
            lines.append(f"POL: {balances.pol:.4f}")
            lines.append(f"USDC.e: {balances.usdc_e:.2f}")
        else:
            lines.append("Wallet: Not configured")
    except Exception as e:
        lines.append(f"Wallet error: {e}")

    halted = read_halt_state()
    lines.append(f"Status: {'HALTED' if halted else 'Running'}")

    try:
        db = MemoryDB(MEMORY_DB_PATH)
        summary = db.get_pnl_summary()
        prior = db.fetch_memory_prior()
        lines.append(f"Total trades: {summary['total_trades']}")
        lines.append(f"Total volume: ${summary['total_volume_usd']:.2f}")
        lines.append(f"Avg latency: {summary['avg_latency_ms']:.0f}ms")
        lines.append(f"Memory prior: {prior:.3f}")
        db.close()
    except Exception as e:
        lines.append(f"DB error: {e}")

    await update.message.reply_text("\n".join(lines))


async def cmd_halt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set halt state and disable MAX_RISK_USD in .env."""
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("Unauthorized")
        return

    write_halt_state(True)

    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        lines = []
        found = False
        with open(env_path) as f:
            for line in f:
                if line.startswith("MAX_RISK_USD="):
                    lines.append("MAX_RISK_USD=0\n")
                    found = True
                else:
                    lines.append(line)
        if found:
            with open(env_path, "w") as f:
                f.writelines(lines)

    await update.message.reply_text("Bot HALTED. Trading disabled.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear halt state."""
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("Unauthorized")
        return

    write_halt_state(False)
    await update.message.reply_text("Bot RESUMED. Trading enabled.")


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show last 3 lessons."""
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("Unauthorized")
        return

    try:
        db = MemoryDB(MEMORY_DB_PATH)
        lessons = db.get_lessons(limit=3)
        db.close()

        if not lessons:
            await update.message.reply_text("No lessons recorded")
            return

        lines = []
        for lesson in lessons:
            lines.append(f"[{lesson.created_at}] {lesson.market_id}")
            lines.append(f"  Modifier: {lesson.prior_modifier:.3f}")
            lines.append(f"  {lesson.insight[:100]}...")
            lines.append(f"  W/L: {lesson.win_count}/{lesson.loss_count}")

        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"DB error: {e}")


def check_drawdown_alert() -> str | None:
    """Return alert message if drawdown exceeds threshold."""
    try:
        db = MemoryDB(MEMORY_DB_PATH)
        summary = db.get_pnl_summary()
        db.close()

        if summary["total_trades"] == 0:
            return None

        current_balance = INITIAL_BANKROLL - summary["total_volume_usd"]
        drawdown = (INITIAL_BANKROLL - current_balance) / INITIAL_BANKROLL

        if drawdown >= DRAWDOWN_THRESHOLD:
            return f"WARNING: Drawdown {drawdown:.1%} exceeds {DRAWDOWN_THRESHOLD:.0%} threshold"
        return None
    except Exception:
        return None


def main() -> None:
    """Start bot polling."""
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    if not TELEGRAM_ALLOWED_CHAT_ID:
        print("WARNING: TELEGRAM_ALLOWED_CHAT_ID not set, bot will reject all commands")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("halt", cmd_halt))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("memory", cmd_memory))

    print("Starting Telegram bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()