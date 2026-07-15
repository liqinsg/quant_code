#scheduled_runner.py
"""
HYBRID JPY TREND RUNNER: Clear Skip Reasons + Minimal Telegram
"""
import sys
import os
import time
import schedule
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CHECK_INTERVAL_MINUTES, RISK_LEVEL, RISK_PROFILE, USE_GEMINI_AI
from custom_strategy import analyze_custom_strategy, get_last_signal
from utils import get_open_position, with_retry, gemini_checker
from utils import open_oanda_order, close_all_trades
from telegram_message import send_telegram_message

# ------------------------------
# 🎛️ TOGGLES
# ------------------------------
from config import DRY_RUN as dry_run
DRY_RUN = dry_run if dry_run is not None else True  # Default to True if not set
ENABLE_ML_CONFIRM = True
ENABLE_GEMINI_FILTER = USE_GEMINI_AI
SEND_TELEGRAM_ALERTS = True

# ------------------------------
# ML Import
# ------------------------------
try:
    from forex_strategy import get_ml_trade_signal
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    if SEND_TELEGRAM_ALERTS:
        send_telegram_message("⚠️ ML module missing — running rule-based only")


def run_cycle():
    profile = RISK_PROFILE[RISK_LEVEL]
    print(f"\n[{datetime.now().isoformat()}] === HYBRID JPY SCAN ===")

    try:
        # LAYER 1: Strongest-Weakest Scan
        with_retry(analyze_custom_strategy, max_attempts=3, delay=5, label="strategy_scan")
        signal_data = get_last_signal()

        if not signal_data:
            print("[REASON] No valid pairs passed screening:")
            print("  → Either multi-timeframe alignment failed, strength gap too small, or no consensus")
            return

        pair = signal_data["pair"]
        action = signal_data["action"]
        print(f"[LAYER 1] ✅ Candidate: {action} {pair} | Gap: {signal_data['strength_score']:+.4f}")

        # LAYER 2: ML Confirmation
        ml_conf = 0
        if ENABLE_ML_CONFIRM and ML_AVAILABLE:
            print("[LAYER 2] Checking ML confirmation...")
            ml_raw = get_ml_trade_signal(pair.replace("_", ""))
            ml_dir = ml_raw.get("direction", "NONE")
            ml_conf = ml_raw.get("confidence", 0)

            if ml_dir != action:
                print(f"[REASON] Skipped: ML direction conflict")
                print(f"  → Rules say {action}, ML says {ml_dir}")
                return
            if ml_conf < 55:
                print(f"[REASON] Skipped: ML confidence too low")
                print(f"  → {ml_conf:.1f}% required ≥ 55%")
                return
            print(f"  ✅ ML confirmed: {ml_dir} @ {ml_conf:.1f}%")

        # LAYER 3: Gemini News Filter
        print("[LAYER 3] Checking news filter...")
        allow, reason = gemini_checker.check_pair(pair, action)
        if not allow:
            print(f"[REASON] Skipped: News conflict/risk")
            print(f"  → {reason}")
            return
        print(f"  ✅ News check passed")

        # Position Guard
        existing = get_open_position(pair)
        if existing and (float(existing.get("long",{}).get("units",0)) !=0 or float(existing.get("short",{}).get("units",0)) !=0):
            print(f"[REASON] Skipped: Already holding position")
            print(f"  → Open position exists for {pair.replace('_', '/')}")
            return

        # ==========================================
        # ✅ FINAL SIGNAL — SEND TELEGRAM
        # ==========================================
        alert = f"""
🚀 **NEW TRADE SIGNAL**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**Pair**: {pair.replace('_', '/')}
**Action**: {action}
**Entry**: `{signal_data['entry']}`
**SL**: `{signal_data['stop_loss']}`
**TP**: `{signal_data['take_profit']}`
**Units**: {profile['units']:,}
**Mode**: {'🧪 DRY RUN' if DRY_RUN else '🔴 LIVE'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**ML Confidence**: {ml_conf:.1f}%
**Strength Gap**: {signal_data['strength_score']:+.4f}
        """.strip()
        print(f"\n{alert}")
        if SEND_TELEGRAM_ALERTS:
            send_telegram_message(alert)

        # ==========================================
        # EXECUTION — SEND TELEGRAM
        # ==========================================
        if DRY_RUN:
            exec_msg = "🧪 DRY RUN: No order sent to OANDA"
        else:
            res = open_oanda_order(signal_data, units=profile['units'])
            if res['status'] == "SUCCESS":
                exec_msg = f"✅ **ORDER EXECUTED**\n{action} {pair.replace('_', '/')}\nID: `{res['order_id']}`\nFilled @ `{res['filled_price']}`"
            else:
                exec_msg = f"❌ **ORDER FAILED**\n{action} {pair.replace('_', '/')}\nError: {res['message']}"
        print(f"\n{exec_msg}")
        if SEND_TELEGRAM_ALERTS:
            send_telegram_message(exec_msg)

    except Exception as e:
        err = f"❌ CYCLE ERROR: {str(e)[:100]}"
        print(err)
        if SEND_TELEGRAM_ALERTS:
            send_telegram_message(err)


if __name__ == "__main__":
    print("="*60)
    print("🚀 HYBRID TRADER — CLEAR SKIP REASONS")
    print("="*60)
    print(f"  Mode: {'DRY RUN' if DRY_RUN else 'LIVE'} | ML: {ENABLE_ML_CONFIRM} | Gemini: {ENABLE_GEMINI_FILTER}")
    print(f"  Next scan in {CHECK_INTERVAL_MINUTES} minutes...")
    print("="*60 + "\n")

    if SEND_TELEGRAM_ALERTS:
        send_telegram_message("🤖 Hybrid JPY Trader started — scanning every 15 mins")

    # Run first scan immediately
    run_cycle()

    # Scheduler loop with heartbeat
    while True:
        schedule.run_pending()
        next_run = schedule.next_run()
        if next_run:
            print(f"\n⏳ Next scan scheduled at: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        time.sleep(30)  # Check every 30s instead of 5s — lighter, clearer
