"""
Central configuration — edit this file to control all strategy behaviour.
Do not hardcode these values elsewhere in the codebase.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 🚀 LIVE / DEMO SWITCH — AUTO FROM .env
# ==========================================
# Auto-detect from your existing OANDA_ENV in .env
print("="*60 + "\n")
OANDA_ENV = os.getenv("OANDA_ENV", "practice").lower()
# Demo: dedicated vars first, then fallbacks
OANDA_API_TOKEN = os.getenv("OANDA_API_TOKEN")
OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID", "")
print("\n" + "="*60)
print("🔧 RUNNING IN **DEMO / PRACTICE MODE**")
print("ℹ️  Orders will be sent to your OANDA practice account")
print("⚠️  No real funds will be used or risked")

# ==========================================
# Scheduler
# ==========================================
CHECK_INTERVAL_MINUTES = 15   # 15 min matches the fastest signal timeframe (M15)

# ==========================================
# ACTIVE STRATEGY SETTINGS
# Simple MA5 multi-timeframe trend strategy on JPY pairs.
# ==========================================

# Pairs to actually trade (direct orders placed here)
# TRADE_PAIRS = ["USD_JPY", "EUR_JPY", "GBP_JPY", "AUD_JPY", "USD_CHF", "EUR_CHF", "GBP_CHF", "AUD_CHF"]
TRADE_PAIRS = ["USD_JPY", "EUR_JPY", "GBP_JPY", "AUD_JPY"]

# Timeframes that must ALL be above MA5 for an entry signal
SIGNAL_TIMEFRAMES = ["H4", "H1", "M30", "M15"]

# TP / SL in pips (JPY pairs: 1 pip = 0.01)
TP_PIPS = 100   # fixed take profit: entry + 100 pips
SL_BUFFER_PIPS = 20    # pips below today's daily low
SPREAD_PIPS = 3     # conservative spread buffer added to SL

# ==========================================
# RISK LEVEL  (1 = safest, 10 = most aggressive)
# Controls position size per trade.
# ==========================================
RISK_LEVEL = 10

RISK_PROFILE = {
    1: {"units": 1000, "min_confidence": 0.90},
    2: {"units": 2000, "min_confidence": 0.85},
    3: {"units": 3000, "min_confidence": 0.80},
    4: {"units": 4000, "min_confidence": 0.75},
    5: {"units": 5000, "min_confidence": 0.70},
    6: {"units": 6000, "min_confidence": 0.65},
    7: {"units": 7000, "min_confidence": 0.60},
    8: {"units": 8000, "min_confidence": 0.55},
    9: {"units": 9000, "min_confidence": 0.50},
    10: {"units": 10000, "min_confidence": 0.40},
}

# ==========================================
# GEMINI AI / NEWS FILTER SETTINGS
# ==========================================
USE_GEMINI_AI = False                      # Master switch: False = no Gemini calls at all
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_NEWS_MODEL = "gemini-2.5-flash"     # ✅ Correct free model name (3.5 doesn't exist yet)
GEMINI_NEWS_FALLBACK_MODEL = "gemini-2.0-flash-lite"
GEMINI_MODEL = GEMINI_NEWS_MODEL           # Alias for backward compatibility
GEMINI_NEWS_LOOKBACK_HOURS = 24            # Check last 24h news only
GEMINI_QUOTA_SAVE_MODE = True              # Skip LLM if no high-impact news = save quota

# ==========================================
# ADVANCED STRATEGY SETTINGS
# Used by the full scheduled_runner.py (not the simple runner).
# Safe to ignore when running scheduled_runner_simple.py.
# ==========================================

# Meta selector
META_MODE = "MANUAL"
MANUAL_STRATEGY = 1     # 1=TREND_COMBINED, 2=RANGE_REVERSION,
# 3=BREAKOUT_CONFIRM, 4=TREND_PULLBACK
STRATEGY_PULLBACK = 4

# ADX regime thresholds
ADX_TREND_THRESHOLD = 25
ADX_BREAKOUT_THRESHOLD = 20

# ATR-based SL/TP (used by full runner, not simple runner)
ATR_GRANULARITY = "D"
ATR_CANDLE_COUNT = 20
ATR_MULTIPLIER_SL = 0.75
ATR_MULTIPLIER_TP = 2.0

# Range strategy
RANGE_LOOKBACK = 20
RANGE_TP_RATIO = 0.6
RANGE_SL_RATIO = 0.25

# Breaking / coiling entry
BREAKOUT_DURATION_HOURS = 4
BREAKOUT_WIDTH_PCT = 2.0

# Test mode — forces a specific pair regardless of signal
FORCE_TEST_PAIR = False
TEST_PAIR = None    # e.g. "USD_JPY"

# Order expiry for pending limit/stop orders
EXPIRE_AFTER = 1440       # minutes (1 day)

# ==========================================
# JPY TREND STRATEGY
# ==========================================
MIN_QUALIFYING_PAIRS = 2

STRENGTH_CANDLE_COUNT = 10
STRENGTH_TIMEFRAMES = {
    "H1": 1,
    "H4": 3,
    "H8": 6,
}
STRENGTH_PAIRS = [
    "EUR_USD", "GBP_USD", "AUD_USD", "NZD_USD",
    "USD_CAD", "USD_CHF", "USD_JPY",
    "EUR_GBP", "EUR_JPY", "EUR_AUD", "EUR_CAD", "EUR_CHF",
    "GBP_JPY", "GBP_AUD", "GBP_CAD",
    "AUD_JPY", "AUD_CAD", "AUD_CHF",
    "NZD_JPY", "CAD_JPY", "CHF_JPY",
]
CURRENCIES = ["USD", "EUR", "GBP", "AUD", "NZD", "CAD", "CHF", "JPY"]

STRENGTH_FAST_LOOKBACK = 5
STRENGTH_SLOW_LOOKBACK = 20
STRENGTH_FAST_WEIGHT = 0.7
STRENGTH_SLOW_WEIGHT = 0.3
MIN_STRENGTH_GAP = 0.6133

ENABLE_STRENGTH_ACCELERATION = False
STRENGTH_ACCELERATION_WEIGHT = 0.5
STRENGTH_ATR_PERIOD = 14

ENABLE_EMA_TREND = False
ENABLE_ATR_NORMALIZED_STRENGTH = False
ENABLE_BREAKOUT_CONFIRMATION = False
BREAKOUT_CONFIRMATION_CLOSES = 2
ENABLE_ATR_SLTP = False

ENABLE_NEWS_FILTER = False
NEWS_LOG_PATH = "news_events.log"
NEWS_CURRENCIES = ["USD", "JPY", "EUR", "GBP"]

MIN_DOMINANCE_RATIO = 1.5
ENABLE_VOLATILITY_NORMALIZED_DOMINANCE = False
DOMINANCE_ATR_PERIOD = 14

JPY_PIP = 0.01
MIN_MARKET_STRENGTH = 0.05
FRONT_RUN_PIPS = 15
MACRO_PROTECTION_PIPS = 20
MIN_RR = 1.2

JPY_ATR_PERIOD = 14
JPY_ATR_HISTORY_LOOKBACK = 50
JPY_ATR_SL_MULTIPLIER_NORMAL = 2.2
JPY_ATR_SL_MULTIPLIER_HIGH_VOL = 2.8
JPY_ATR_SL_MULTIPLIER_LOW_VOL = 1.8
JPY_ATR_RR_MULTIPLE = 2.0

# ==========================================
# DATA PROVIDER SETTINGS
# ==========================================
DATA_SOURCE = "OANDA_WITH_YAHOO_FALLBACK"
DRY_RUN = False  # True = simulate only / False = send real orders to OANDA
ENABLE_GEMINI_NEWS_FILTER = False


# ==========================================
# 🧪 TEST MAIN FUNCTION — VIEW ALL VARIABLES
# ==========================================
def main():
    print("="*70)
    print("📋 FULL CONFIGURATION VARIABLES OVERVIEW")
    print("="*70)

    # Core Mode & OANDA Settings
    print("\n🔹 MODE & OANDA CONNECTION")
    print(f"  OANDA_ENV          : {OANDA_ENV}")
    print(f"  OANDA_API_TOKEN    : {'✅ SET' if OANDA_API_TOKEN else '❌ MISSING'}")
    print(f"  OANDA_ACCOUNT_ID   : {OANDA_ACCOUNT_ID if OANDA_ACCOUNT_ID else '❌ MISSING'}")

    # Scheduler & Trading Pairs
    print("\n🔹 SCHEDULER & TRADE SETTINGS")
    print(f"  CHECK_INTERVAL_MIN : {CHECK_INTERVAL_MINUTES} min")
    print(f"  TRADE_PAIRS        : {', '.join(TRADE_PAIRS)}")
    print(f"  SIGNAL_TIMEFRAMES  : {', '.join(SIGNAL_TIMEFRAMES)}")
    print(f"  TP_PIPS            : {TP_PIPS}")
    print(f"  SL_BUFFER_PIPS     : {SL_BUFFER_PIPS}")
    print(f"  SPREAD_PIPS        : {SPREAD_PIPS}")
    print(f"  RISK_LEVEL         : {RISK_LEVEL}")
    print(f"  RISK_PROFILE_UNITS : {RISK_PROFILE[RISK_LEVEL]['units']}")

    # Feature Switches
    print("\n🔹 FEATURE SWITCHES")
    print(f"  DRY_RUN            : {DRY_RUN}")
    print(f"  USE_GEMINI_AI      : {USE_GEMINI_AI}")
    print(f"  ENABLE_NEWS_FILTER : {ENABLE_NEWS_FILTER}")
    print(f"  ENABLE_EMA_TREND   : {ENABLE_EMA_TREND}")
    print(f"  ENABLE_ATR_SLTP    : {ENABLE_ATR_SLTP}")
    print(f"  DATA_SOURCE        : {DATA_SOURCE}")

    print("\n" + "="*70)
    print("✅ Config test complete — all variables loaded correctly!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()