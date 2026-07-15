"""
Full End-to-End Tests for oanda_execution.py
Flow: DEMO check → empty check → validation → open order → verify → close → confirm empty
# 1) full tests
pytest tests/test_oanda_execution.py -v -s
# 2) Only run DEMO mode check
pytest tests/test_oanda_execution.py::test_1_confirm_demo_mode -v -s
# Only run input validation
pytest tests/test_oanda_execution.py::test_3_input_validation -v -s
# 3) Run Tests 1 + 2 + 3 only
pytest \
  tests/test_oanda_execution.py::test_1_confirm_demo_mode \
  tests/test_oanda_execution.py::test_2_confirm_empty_account \
  tests/test_oanda_execution.py::test_3_input_validation \
  -v -s
"""
import sys
import os
# --------------------------
# 🔧 FIX: Add project root FIRST
# --------------------------
# This points straight to /home/nie/projects/quant_code/ where config.py lives
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
print(f"✅ Added project root to path: {PROJECT_ROOT}")

# --------------------------
# Now imports work perfectly
# --------------------------
import pytest
import oandapyV20.endpoints.trades as trades
from config import DEMO_MODE, OANDA_ENV, OANDA_ACCOUNT_ID
from utils.oanda_execution import open_oanda_order, close_all_trades, api

# ==========================================
# 1. Verify DEMO mode only
# ==========================================
def test_1_confirm_demo_mode():
    print("\n" + "="*60)
    print("🔹 TEST 1: Enforce DEMO / PRACTICE account")
    print("="*60)
    assert DEMO_MODE is True, "❌ ABORT: Set DEMO_MODE=True before running order tests!"
    assert OANDA_ENV.lower() == "practice", "❌ ABORT: OANDA_ENV must be 'practice'!"
    print(f"✅ Safe: Running on demo account {OANDA_ACCOUNT_ID}")

# ==========================================
# 2. Confirm no existing trades first — auto-clean if needed
# ==========================================
def test_2_confirm_empty_account():
    print("\n" + "="*60)
    print("🔹 TEST 2: Auto-clean & confirm empty account")
    print("="*60)
    # Auto-close any leftover trades first
    close_all_trades()
    
    # Now verify empty
    resp = api.request(trades.TradesList(OANDA_ACCOUNT_ID))
    open_trades = resp.get("trades", [])
    assert len(open_trades) == 0, f"❌ Still found open trades after cleanup: {open_trades}"
    print("✅ Account is empty — ready for test")

# ==========================================
# 3. Input validation safety checks
# ==========================================
def test_3_input_validation():
    print("\n" + "="*60)
    print("🔹 TEST 3: Input validation checks")
    print("="*60)
    assert open_oanda_order({"action": "BUY", "stop_loss": 160, "take_profit": 165})["status"] == "ERROR"
    assert open_oanda_order({"pair": "USD_JPY", "action": "HOLD", "stop_loss": 160, "take_profit": 165})["status"] == "ERROR"
    assert open_oanda_order({"pair": "USD_JPY", "action": "BUY"})["status"] == "ERROR"
    assert open_oanda_order({"pair": "USD_JPY", "action": "BUY", "stop_loss": "x", "take_profit": "y"})["status"] == "ERROR"
    print("✅ All invalid inputs correctly rejected")


# ==========================================
# 4. Send test market order
# ==========================================
def test_4_send_test_order():
    print("\n" + "="*60)
    print("🔹 TEST 4: Send small DEMO market order")
    print("="*60)
    signal = {
        "pair": "USD_JPY",
        "action": "BUY",
        "stop_loss": 162.00,
        "take_profit": 163.00
    }
    result = open_oanda_order(signal, units=1000)
    assert result["status"] == "SUCCESS", f"❌ Order failed: {result}"
    print(f"✅ Order filled: ID {result['order_id']} @ {result['filled_price']}")


# ==========================================
# 5. Verify new trade exists
# ==========================================
def test_5_verify_order_open():
    print("\n" + "="*60)
    print("🔹 TEST 5: Verify test trade is open")
    print("="*60)
    resp = api.request(trades.TradesList(OANDA_ACCOUNT_ID))
    open_trades = resp.get("trades", [])
    assert len(open_trades) >= 1, f"❌ No open trades found after sending order"
    print(f"✅ Found {len(open_trades)} open trade(s)")
    # Check our test instrument is there
    instruments = [t["instrument"] for t in open_trades]
    assert "USD_JPY" in instruments, "❌ USD_JPY test trade not found"
    print("✅ USD_JPY trade confirmed open")

# ==========================================
# 6. Close all trades & confirm empty
# ==========================================
def test_6_close_and_confirm_empty():
    print("\n" + "="*60)
    print("🔹 TEST 6: Close all trades & confirm empty")
    print("="*60)
    close_result = close_all_trades()
    assert close_result["status"] in ["SUCCESS", "INFO"], f"❌ Close failed: {close_result}"
    print(f"✅ Cleanup: {close_result.get('message', close_result.get('closed_trades', 'done'))}")

    # Final check
    resp = api.request(trades.TradesList(OANDA_ACCOUNT_ID))
    assert len(resp.get("trades", [])) == 0, "❌ Trades still remain!"
    print("✅ All trades closed — account empty again")