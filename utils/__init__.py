"""
Central import hub — all utilities available from here
"""

# Data & Schemas
from .data_provider import get_candles, get_latest_price
from .schemas import TradeSignal
from .oanda_execution import open_oanda_order, close_all_trades
# Core Trading & AI
from .trading_core import (
    oanda_client,
    gemini_client,
    format_price_for_instrument,
    get_open_position,
    attach_sl_tp_to_open_trade,
    verify_sl_tp_on_trade,
    get_recent_range,
    execute_market_trade,
    get_latest_news_sentiment,
    validate_signal_with_fundamentals,
    get_news_risk_bias,
    get_ensemble_consensus,
    run_trading_cycle,
    get_candles,
    get_latest_price
)

# ✅ Fixed: Both functions are in oanda_execution.py now
# from .oanda_execution import open_oanda_order, close_all_trades

# Strategy Helpers & Tools
from .strategy_helpers import *
from .find_support_resistence import get_support_resistance
from .sl_tp_helper import *
from .indicator_provider import *
from .regime_detector import *
from .breaking_entry import *
from .currency_strength import *
from .quota_guard import *
from .retry import with_retry
from .gemini_news_filter import gemini_checker

# Public API — keep all exports here
__all__ = [
    # Core
    "TradeSignal",
    "oanda_client",
    "gemini_client",
    "format_price_for_instrument",
    "get_open_position",
    "attach_sl_tp_to_open_trade",
    "verify_sl_tp_on_trade",
    "get_recent_range",
    "execute_market_trade",
    "get_latest_news_sentiment",
    "validate_signal_with_fundamentals",
    "get_news_risk_bias",
    "get_ensemble_consensus",
    "run_trading_cycle",
    "get_candles",
    "get_latest_price",
    # ✅ Fixed exports
    "open_oanda_order",
    "close_all_trades",
    # Helpers
    "get_support_resistance",
    "with_retry",
    "gemini_checker"
]