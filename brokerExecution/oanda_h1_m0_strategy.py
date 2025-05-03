import time
import datetime
import math
import oandapyV20
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.accounts as accounts
import oandapyV20.endpoints.instruments as instruments
# from oandapyV20.types import StopLossDetails, TakeProfitDetails
from oandapyV20.contrib.requests import (
    MarketOrderRequest,
    TakeProfitDetails,
    StopLossDetails
)

# OANDA API credentials & settings
API_KEY = "YOUR_OANDA_API_KEY"
ACCOUNT_ID = "YOUR_OANDA_ACCOUNT_ID"
INSTRUMENT = "EUR_USD"         # Change as needed (or e.g., "NAS100_USD")
RISK_PER_TRADE_GBP = 100       # Risk per trade in GBP
ACCOUNT_CURRENCY = "GBP"

# Configure take profit levels (optional, up to 3 levels)
# "pips" are defined in terms of the instrument's tick size.
TAKE_PROFIT_LEVELS = [
    {"pips": 10, "percentage": 0.5},  # Close 50% of the position at 10 pips in profit
    {"pips": 20, "percentage": 0.3},  # Close 30% at 20 pips
    {"pips": 30, "percentage": 0.2},  # Close 20% at 30 pips
]

# Minimum position size allowed (units). Adjust as appropriate for the instrument.
MIN_POSITION_SIZE = 1

# OANDA API client
client = oandapyV20.API(access_token=API_KEY)

def get_tick_size():
    """
    Fetch the instrument details and return the minimum price increment (tick size).
    For many instruments the “displayPrecision” or similar field can be used.
    Adjust this function if necessary to obtain the actual tick size.
    """
    try:
        response = client.request(instruments.InstrumentsDetails(INSTRUMENT))
        # Many instruments provide "displayPrecision" (number of decimals)
        # We then compute the tick size as 10^(-displayPrecision).
        display_precision = int(response["instrument"]["displayPrecision"])
        tick_size = 10 ** (-display_precision)
        return tick_size
    except Exception as e:
        print(f"Error fetching tick size: {e}")
        return None

def get_first_minute_high_low():
    """
    Fetch the high and low of the first minute of the current hour.
    """
    now = datetime.datetime.utcnow()
    start = now.replace(minute=0, second=0, microsecond=0)
    end = start + datetime.timedelta(minutes=1)
    params = {
        "granularity": "M1",
        "from": start.isoformat() + "Z",
        "to": end.isoformat() + "Z",
        "count": 1
    }
    try:
        candle_endpoint = instruments.InstrumentsCandles(instrument=INSTRUMENT, params=params)
        candles = client.request(candle_endpoint)
        if candles.get("candles"):
            candle = candles["candles"][0]
            return float(candle["mid"]["h"]), float(candle["mid"]["l"])
    except Exception as e:
        print(f"Error fetching candle data: {e}")
    return None, None

def get_account_details():
    """Fetch account balance and margin details."""
    try:
        response = client.request(accounts.AccountDetails(ACCOUNT_ID))
        account = response["account"]
        balance = float(account["balance"])
        margin_available = float(account["marginAvailable"])
        return balance, margin_available
    except Exception as e:
        print(f"Error fetching account details: {e}")
        return None, None

def get_pip_value():
    """
    Calculate a pip value based on the tick size.
    For example, for EUR_USD if tick_size = 0.0001 then pip value per unit ~ (tick_size / price).
    This is an approximation – you may need to refine it for your instrument.
    """
    try:
        params = {"instruments": INSTRUMENT}
        response = client.request(pricing.PricingInfo(ACCOUNT_ID, params=params))
        price = float(response["prices"][0]["bids"][0]["price"])
        tick_size = get_tick_size()
        if tick_size:
            return tick_size / price
    except Exception as e:
        print(f"Error fetching pip value: {e}")
    return None

def calculate_position_size(entry_price, stop_loss):
    """
    Calculate the number of units such that risk (difference between entry and stop loss)
    multiplied by the pip value equals RISK_PER_TRADE_GBP.
    Then, adjust the size to be a multiple of MIN_POSITION_SIZE.
    """
    stop_loss_distance = abs(entry_price - stop_loss)
    pip_value = get_pip_value()
    if not pip_value or stop_loss_distance == 0:
        print("Error: Invalid pip value or stop loss distance.")
        return 0
    # Calculate raw position size based on risk
    raw_size = RISK_PER_TRADE_GBP / (stop_loss_distance / pip_value)
    # Ensure the size is a multiple of MIN_POSITION_SIZE:
    size = math.floor(raw_size / MIN_POSITION_SIZE) * MIN_POSITION_SIZE
    if size < MIN_POSITION_SIZE:
        print("Calculated position size is below the minimum allowed.")
        return 0
    # Additionally, ensure we do not exceed margin limits
    _, margin_available = get_account_details()
    max_size = margin_available / entry_price  # This is a rough estimate.
    return int(min(size, max_size))

def place_entry_order(entry_price, stop_loss, order_side):
    """
    Place an entry order of type STOP with a stop loss attached.
    order_side: "buy" or "sell"
    Returns a tuple (order_id, units) if successful.
    """
    units = calculate_position_size(entry_price, stop_loss)
    if units <= 0:
        print("Skipping entry order: position size too small.")
        return None, None
    side_multiplier = 1 if order_side == "buy" else -1
    order_data = {
        "order": {
            "instrument": INSTRUMENT,
            "units": str(units * side_multiplier),
            "type": "STOP",
            "price": str(entry_price),
            "timeInForce": "GTC",
            "positionFill": "DEFAULT",
            "stopLossOnFill": StopLossDetails(price=str(stop_loss)).data
        }
    }
    try:
        response = client.request(orders.OrderCreate(ACCOUNT_ID, data=order_data))
        order_id = response["orderFillTransaction"]["id"]
        print(f"Placed {order_side.upper()} entry order at {entry_price} with SL at {stop_loss} for {units} units.")
        return order_id, units
    except Exception as e:
        print(f"Error placing {order_side} entry order: {e}")
        return None, None

def place_take_profit_orders(trade_id, entry_price, order_side, total_units):
    """
    Place up to 3 take profit orders as LIMIT orders with REDUCE_ONLY.
    These orders are not linked natively to the stop loss, so we simulate cancellation later.
    """
    side_multiplier = 1 if order_side == "buy" else -1
    tp_order_ids = []
    for i, tp in enumerate(TAKE_PROFIT_LEVELS):
        # For a BUY order, TP price is entry + (tick_size * pips)
        # For a SELL order, TP price is entry - (tick_size * pips)
        tick_size = get_tick_size()
        tp_offset = tp["pips"] * tick_size
        tp_price = entry_price + (tp_offset if order_side == "buy" else -tp_offset)
        tp_units = int(total_units * tp["percentage"])
        if tp_units < MIN_POSITION_SIZE:
            continue  # Skip if below minimum
        # For reducing the position, the order units are opposite in sign.
        tp_order_data = {
            "order": {
                "instrument": INSTRUMENT,
                "units": str(-tp_units * side_multiplier),
                "type": "LIMIT",
                "price": str(tp_price),
                "timeInForce": "GTC",
                "positionFill": "REDUCE_ONLY"
            }
        }
        try:
            response = client.request(orders.OrderCreate(ACCOUNT_ID, data=tp_order_data))
            tp_order_id = response["orderCreateTransaction"]["id"]
            tp_order_ids.append(tp_order_id)
            print(f"Placed TP {i+1}: {tp_units} units at {tp_price}")
        except Exception as e:
            print(f"Error placing TP order {i+1}: {e}")
    return tp_order_ids

def cancel_order(order_id):
    """Cancel a pending order by ID."""
    try:
        cancel_endpoint = orders.OrderCancel(accountID=ACCOUNT_ID, orderID=order_id)
        client.request(cancel_endpoint)
        print(f"Canceled order {order_id}")
    except Exception as e:
        print(f"Error canceling order {order_id}: {e}")

def cancel_orders(order_ids):
    """Cancel a list of order IDs."""
    for oid in order_ids:
        cancel_order(oid)

def get_pending_orders():
    """Retrieve the list of pending orders for the account."""
    try:
        response = client.request(orders.OrdersPending(accountID=ACCOUNT_ID))
        return response.get("orders", [])
    except Exception as e:
        print(f"Error fetching pending orders: {e}")
        return []

def get_open_trades():
    """Retrieve the list of open trades."""
    try:
        response = client.request(trades.TradesList(ACCOUNT_ID))
        return response.get("trades", [])
    except Exception as e:
        print(f"Error fetching open trades: {e}")
        return []

def poll_for_entry_fill(buy_order_id, sell_order_id, poll_interval=2, timeout=300):
    """
    Poll for an entry order fill.
    Once one entry order is filled, cancel the other.
    Returns a tuple: (filled_side, trade_id, units)
    filled_side is "buy" or "sell"
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        open_trades = get_open_trades()
        for trade in open_trades:
            # We assume the trade's "id" corresponds to the filled order
            # In practice, you may need to correlate via client extensions or other metadata.
            # Here we simply assume that if a trade is open, one of our entry orders was filled.
            # And we assume that the trade's side is determined by the sign of the "initialUnits".
            trade_units = float(trade["initialUnits"])
            filled_side = "buy" if trade_units > 0 else "sell"
            trade_id = trade["id"]

            # Cancel the pending entry order for the opposite side
            pending_orders = get_pending_orders()
            for order in pending_orders:
                if order["id"] in [buy_order_id, sell_order_id]:
                    # If this order is not the one that resulted in the open trade, cancel it.
                    if (filled_side == "buy" and order["id"] == sell_order_id) or \
                       (filled_side == "sell" and order["id"] == buy_order_id):
                        cancel_order(order["id"])
            return filled_side, trade_id, abs(int(trade_units))
        time.sleep(poll_interval)
    print("Timeout waiting for entry fill.")
    return None, None, None


def main():
    while True:
        now = datetime.datetime.utcnow()
        # At the start of the hour, place entry orders.
        if now.minute == 0 and now.second < 5:  # allow a 5-second window
            high, low = get_first_minute_high_low()
            if high and low:
                print(f"First minute high: {high}, low: {low}")
                # For a BUY entry order, use the high as the trigger with SL at low.
                buy_order_id, _ = place_entry_order(high, low, "buy")
                # For a SELL entry order, use the low as the trigger with SL at high.
                sell_order_id, _ = place_entry_order(low, high, "sell")
                
                if not buy_order_id or not sell_order_id:
                    print("Failed to place one or both entry orders.")
                    continue

                # Poll until one entry order fills (simulate OCO)
                filled_side, trade_id, units = poll_for_entry_fill(buy_order_id, sell_order_id)
                if filled_side and trade_id:
                    # Once an entry is filled, place take profit orders for that trade.
                    entry_price = high if filled_side == "buy" else low
                    tp_order_ids = place_take_profit_orders(trade_id, entry_price, filled_side, units)
                    # Start polling for stop loss execution on this trade.
                    # (In a production system, you might run this in a separate thread)
                    poll_trade_for_stoploss(trade_id, tp_order_ids)
                else:
                    print("No entry order was filled. Cancelling any pending orders.")
                    cancel_orders([buy_order_id, sell_order_id])
                    
        # At the 58th minute, close any open trades.
        if now.minute == 58:
            print("58th minute reached. Closing all open trades.")
            close_all_trades()
            
        time.sleep(1)

if __name__ == "__main__":
    main()
