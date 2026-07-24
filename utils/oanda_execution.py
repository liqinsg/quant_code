# utils/oanda_execution.py
import sys
import os
import time

# Add project root to import path so config.py is found
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import oandapyV20
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.positions as positions
from oandapyV20.exceptions import V20Error
from typing import Dict, Optional
from config import OANDA_ACCOUNT_ID, OANDA_ENV, OANDA_API_TOKEN

api = oandapyV20.API(
    access_token=OANDA_API_TOKEN,
    environment=OANDA_ENV
)

# FIX: never print the raw token — only confirm it loaded.
print(f"[OANDA CONFIG] account={OANDA_ACCOUNT_ID} env={OANDA_ENV} token_set={bool(OANDA_API_TOKEN)}")


def open_oanda_order(signal: Dict, units: Optional[float] = None) -> Dict:
    """
    Open a market order on OANDA from your strategy signal dict.
    Expected keys: pair, action, stop_loss, take_profit
    """
    if not OANDA_ACCOUNT_ID or not OANDA_API_TOKEN:
        return {"status": "ERROR", "message": "Missing OANDA credentials"}

    pair_raw = signal.get("pair")
    if not pair_raw:
        return {"status": "ERROR", "message": "Signal missing 'pair'"}

    # Convert format: USD_JPY → USD/JPY
    pair = pair_raw.replace("_", "/")

    action = signal.get("action")

    # FIX: validate action BEFORE checking for duplicates, so an invalid
    # action doesn't waste a duplicate-check API call.
    if action not in {"BUY", "SELL"}:
        return {"status": "ERROR", "message": "Signal 'action' must be BUY or SELL"}

    if has_duplicate_trade(pair_raw, action):
        return {
            "status": "SKIPPED",
            "message": f"Existing {action} position already open"
        }

    sl_raw = signal.get("stop_loss")
    tp_raw = signal.get("take_profit")
    if sl_raw is None or tp_raw is None:
        return {"status": "ERROR", "message": "Signal missing stop_loss or take_profit"}

    try:
        sl = float(sl_raw)
        tp = float(tp_raw)
    except (TypeError, ValueError):
        return {"status": "ERROR", "message": "stop_loss/take_profit must be numeric"}

    default_units = 10000
    position_units = default_units if units is None else units
    position_units = float(position_units)

    if action == "SELL":
        position_units = -abs(position_units)

    order_payload = {
        "order": {
            "type": "MARKET",
            "instrument": pair,
            "units": str(int(position_units)),
            "timeInForce": "FOK",
            "positionFill": "DEFAULT",
            "stopLossOnFill": {
                "price": str(round(sl, 3)),
                "timeInForce": "GTC",
            },
            "takeProfitOnFill": {
                "price": str(round(tp, 3)),
                "timeInForce": "GTC",
            },
        }
    }

    try:
        print(f"\n[OANDA EXEC] Sending {action} order for {pair}...")
        print(f"  Units: {abs(int(position_units))} | SL: {sl:.3f} | TP: {tp:.3f}")

        request = orders.OrderCreate(OANDA_ACCOUNT_ID, data=order_payload)
        response = api.request(request)

        # Wait briefly for fill
        time.sleep(1.2)

        # ✅ Get confirmed trade details
        trades_resp = api.request(trades.TradesList(OANDA_ACCOUNT_ID))
        recent_trades = [t for t in trades_resp.get("trades", [])
                         if t["instrument"] == pair.replace("/", "_") and t["state"] == "OPEN"]

        if recent_trades:
            t = recent_trades[-1]  # most recent
            result = {
                "status": "SUCCESS",
                "order_id": t["id"],
                "filled_price": t["price"],
                "instrument": t["instrument"],
                "units": t["currentUnits"],
                "sl_set": t.get("stopLossOrder", {}).get("price", "NOT_SET"),
                "tp_set": t.get("takeProfitOrder", {}).get("price", "NOT_SET"),
                "time": t["openTime"],
            }
        else:
            return {"status": "ERROR", "message": "Order sent but no open trade found"}

        print(f"[OANDA EXEC] ✅ Order filled: {result['order_id']} @ {result['filled_price']}")
        return result

    except V20Error as e:
        error_msg = f"OANDA API Error: {e}"
        print(f"[OANDA EXEC] ❌ {error_msg}")
        return {"status": "ERROR", "message": error_msg}
    except Exception as e:
        error_msg = f"Unexpected Error: {str(e)}"
        print(f"[OANDA EXEC] ❌ {error_msg}")
        return {"status": "ERROR", "message": error_msg}


def get_open_positions() -> Dict:
    """
    Fetch only ACTIVE open positions (filter out closed/cached)
    Returns: {instrument: {"side": "BUY"/"SELL", "units": float, "entry": float, "sl": float, "tp": float}}
    """
    try:
        request = trades.TradesList(OANDA_ACCOUNT_ID)
        response = api.request(request)
        trades_list = response.get("trades", [])
        positions = {}

        for t in trades_list:
            # Only keep OPEN trades
            if t.get("state") != "OPEN":
                continue
            instrument = t["instrument"]
            units = float(t["currentUnits"])
            entry_price = float(t["price"])
            sl = float(t.get("stopLossOrder", {}).get("price", 0.0))
            tp = float(t.get("takeProfitOrder", {}).get("price", 0.0))

            if units > 0:
                side = "BUY"
            elif units < 0:
                side = "SELL"
                units = abs(units)
            else:
                continue

            positions[instrument] = {
                "side": side,
                "units": units,
                "entry": entry_price,
                "sl": sl,
                "tp": tp,
                "trade_id": t["id"]
            }

        return positions

    except V20Error as e:
        print(f"[OANDA POSITIONS] ❌ API Error: {e}")
        return {}
    except Exception as e:
        print(f"[OANDA POSITIONS] ❌ Unexpected Error: {e}")
        return {}


def close_all_trades() -> Dict:
    """
    Close ALL open positions using POSITION endpoint (more reliable),
    wait and confirm fully closed.
    """
    try:
        # Get only OPEN trades
        open_positions = get_open_positions()
        if not open_positions:
            return {"status": "INFO", "message": "No open trades found"}

        results = []
        for instrument, pos in open_positions.items():
            # ✅ Use position close instead of per-trade close — more reliable
            close_data = {}
            if pos["side"] == "BUY":
                close_data = {"longUnits": "ALL"}
            else:
                close_data = {"shortUnits": "ALL"}

            req = positions.PositionClose(OANDA_ACCOUNT_ID,
                                          instrument=instrument,
                                          data=close_data)
            api.request(req)
            results.append({"instrument": instrument, "closed": True})
            print(f"[CLEANUP] Closed position: {instrument}")

        # Delete all pending SL/TP orders
        order_req = orders.OrderList(OANDA_ACCOUNT_ID)
        pending_orders = api.request(order_req).get("orders", [])
        for o in pending_orders:
            if o["type"] in ["STOP_LOSS", "TAKE_PROFIT"]:
                del_req = orders.OrderCancel(OANDA_ACCOUNT_ID, orderID=o["id"])
                api.request(del_req)
                print(f"[CLEANUP] Deleted pending order ID: {o['id']} ({o['type']})")

        # ✅ Poll up to 10 seconds until empty
        print("[CLEANUP] Waiting for account to update...")
        for _ in range(10):
            time.sleep(1)
            if not get_open_positions():
                print("[CLEANUP] ✅ All positions confirmed closed")
                break
        else:
            print("[CLEANUP] ⚠️ Timeout — some still show open")

        return {"status": "SUCCESS", "closed_positions": results}

    except Exception as e:
        return {"status": "ERROR", "message": str(e)}


def close_position(instrument: str) -> Dict:
    """
    Close a single open position (by instrument) and cancel its pending
    SL/TP orders. Used for signal reversals — close the opposite-side
    position before opening the new one, instead of close_all_trades()
    which would touch every open pair.
    """
    try:
        current = get_open_positions()
        if instrument not in current:
            return {"status": "INFO", "message": f"No open position on {instrument}"}

        pos = current[instrument]
        close_data = {"longUnits": "ALL"} if pos["side"] == "BUY" else {"shortUnits": "ALL"}

        req = positions.PositionClose(OANDA_ACCOUNT_ID, instrument=instrument, data=close_data)
        api.request(req)
        print(f"[CLOSE] Closed {pos['side']} position on {instrument}")

        # Cancel any pending SL/TP orders tied to this instrument
        order_req = orders.OrderList(OANDA_ACCOUNT_ID)
        pending_orders = api.request(order_req).get("orders", [])
        for o in pending_orders:
            if o.get("instrument") == instrument and o["type"] in ["STOP_LOSS", "TAKE_PROFIT"]:
                del_req = orders.OrderCancel(OANDA_ACCOUNT_ID, orderID=o["id"])
                api.request(del_req)
                print(f"[CLOSE] Cancelled pending order {o['id']} ({o['type']})")

        # Poll up to 10s to confirm the position is actually gone
        for _ in range(10):
            time.sleep(1)
            if instrument not in get_open_positions():
                print(f"[CLOSE] ✅ {instrument} confirmed closed")
                break
        else:
            print(f"[CLOSE] ⚠️ Timeout waiting for {instrument} to close")

        return {"status": "SUCCESS", "closed_side": pos["side"], "instrument": instrument}

    except V20Error as e:
        error_msg = f"OANDA API Error: {e}"
        print(f"[CLOSE] ❌ {error_msg}")
        return {"status": "ERROR", "message": error_msg}
    except Exception as e:
        error_msg = f"Unexpected Error: {str(e)}"
        print(f"[CLOSE] ❌ {error_msg}")
        return {"status": "ERROR", "message": error_msg}


# ----------------------
# 🧪 TEST MAIN FUNCTION
# ----------------------
def main():
    print("=" * 50)

    test_signal = {
        "pair": "USD_JPY",
        "action": "BUY",
        "stop_loss": 162.10,
        "take_profit": 162.70
    }

    test_units = 1000

    print("\n📤 Sending test order...")
    open_result = open_oanda_order(test_signal, units=test_units)

    print("\n📋 Open Order Result:")
    for k, v in open_result.items():
        print(f"  {k}: {v}")

    print("\n✅ Test run complete!")


def get_position_side(pair):
    positions = get_open_positions()

    if pair in positions:
        return positions[pair]["side"]

    return None

def has_duplicate_trade(pair: str, action: str) -> bool:
    positions = get_open_positions()

    # convert USD_JPY -> USD/JPY if necessary
    pair1 = pair
    pair2 = pair.replace("_", "/")
    pair3 = pair.replace("/", "_")

    for instrument, pos in positions.items():
        if instrument in (pair1, pair2, pair3):
            if pos["side"] == action:
                print(
                    f"[DUPLICATE] Existing {action} position "
                    f"already open on {instrument}"
                )
                return True

    return False

if __name__ == "__main__":
    main()