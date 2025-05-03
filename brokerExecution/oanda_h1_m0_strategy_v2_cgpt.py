
import time
import datetime
import math
import oandapyV20
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.accounts as accounts
import oandapyV20.endpoints.instruments as instruments
from oandapyV20.contrib.requests import (
    MarketOrderRequest,
    TakeProfitDetails,
    StopLossDetails
)

# ------------------------------
# Configuration & Settings
# ------------------------------
API_KEY = "YOUR_OANDA_API_KEY"
ACCOUNT_ID = "YOUR_OANDA_ACCOUNT_ID"
INSTRUMENT = "EUR_USD"  # Change as needed (or e.g., "NAS100_USD")
RISK_PER_TRADE_GBP = 100       # Risk per trade in GBP
ACCOUNT_CURRENCY = "GBP"

# Configure up to 3 take profit levels (optional)
# The "pips" values are expressed in terms of the instrument's tick size.
TAKE_PROFIT_LEVELS = [
    {"pips": 10, "percentage": 0.5},  # Close 50% at 10 pips in profit
    {"pips": 20, "percentage": 0.3},  # Close 30% at 20 pips
    {"pips": 30, "percentage": 0.2},  # Close 20% at 30 pips
]

# Minimum position size allowed (in units)
MIN_POSITION_SIZE = 1

# Create OANDA API client
client = oandapyV20.API(access_token=API_KEY)

# ------------------------------
# Helper Functions
# ------------------------------

def get_tick_size():
    """
    Fetch the instrument details and return the tick size.
    Many instruments provide a "displayPrecision" field; we then assume:
        tick_size = 10^(-displayPrecision)
    Adjust this function as needed.
    """
    try:
        params = {"instruments": INSTRUMENT}
        response = client.request(accounts.AccountInstruments(ACCOUNT_ID, params=params))
        # print(response)
        resp_instrument = response["instruments"][0]
        display_precision = int(resp_instrument["displayPrecision"])
        tick_size = 10 ** (-display_precision)
        return tick_size
    except Exception as e:
        print(f"Error fetching tick size: {e}")
        return None

def get_current_bid_ask():
    """Fetch the current bid and ask prices for the instrument."""
    try:
        params = {"instruments": INSTRUMENT}
        response = client.request(pricing.PricingInfo(ACCOUNT_ID, params=params))
        # print(response)
        price_data = response["prices"][0]
        bid = float(price_data["bids"][0]["price"])
        ask = float(price_data["asks"][0]["price"])
        return bid, ask
    except Exception as e:
        print(f"Error fetching bid/ask: {e}")
        return None, None

def adjust_for_spread(price, order_side):
    """
    Adjust a price to account for the spread.
    For a BUY order, shift the price up by half the spread (since you pay the ask);
    for a SELL order, shift it down by half the spread (since you receive the bid).
    """
    bid, ask = get_current_bid_ask()
    if bid is None or ask is None:
        return price  # fallback if pricing data is unavailable
    half_spread = (ask - bid) / 2.0
    if order_side.lower() == "buy":
        return price + half_spread
    else:
        return price - half_spread

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
    """Fetch account balance and available margin."""
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
    This is a rough approximation: pip_value ~ tick_size / price.
    """
    try:
        price, _ = get_current_bid_ask()
        tick_size = get_tick_size()
        if tick_size:
            return tick_size / price
    except Exception as e:
        print(f"Error fetching pip value: {e}")
    return None

def calculate_position_size(entry_price, stop_loss):
    """
    Calculate the number of units such that the risk (the distance between the entry and the stop loss)
    times the pip value equals RISK_PER_TRADE_GBP.
    Then, adjust the size to be a multiple of MIN_POSITION_SIZE.
    """
    stop_loss_distance = abs(entry_price - stop_loss)
    stop_loss_distance_pips =  stop_loss_distance / get_tick_size()
    pip_value = get_pip_value()
    if not pip_value or stop_loss_distance == 0:
        print("Error: Invalid pip value or stop loss distance.")
        return 0
    # Calculate raw position size based on fixed risk.
    raw_size = RISK_PER_TRADE_GBP / (stop_loss_distance_pips * pip_value)
    # Adjust size to be a multiple of MIN_POSITION_SIZE.
    size = math.floor(raw_size / MIN_POSITION_SIZE) * MIN_POSITION_SIZE
    # print(f'Raw size: {raw_size}, Adjusted size: {size}, MinPositionSize: {MIN_POSITION_SIZE}, stop_loss_distance: {stop_loss_distance}, pip_value: {pip_value}, stop_loss_distance_pips: {stop_loss_distance_pips}')
    if size < MIN_POSITION_SIZE:
        print("Calculated position size is below the minimum allowed.")
        return 0
    # Also ensure we do not exceed margin limits.
    _, margin_available = get_account_details()
    print(f'Margin: {margin_available}')
    max_size = margin_available / entry_price  # Rough estimate.
    return int(min(size, max_size))

# ------------------------------
# Order Placement Functions
# ------------------------------

def place_entry_order(entry_price, stop_loss, order_side):
    """
    Place an entry STOP order with an attached stop loss.
    Adjust the entry and SL prices to account for the spread.
    order_side: "buy" or "sell"
    Returns (order_id, units) if successful.
    """
    # Adjust entry price and stop loss for the spread.
    adjusted_entry = adjust_for_spread(entry_price, order_side)
    # For the stop loss, use the opposing pricing adjustment.
    adjusted_sl = adjust_for_spread(stop_loss, "sell" if order_side.lower() == "buy" else "buy")
    
    # Calculate the total position size.
    units = calculate_position_size(entry_price, stop_loss)
    if units < MIN_POSITION_SIZE:
        print("Skipping entry order: position size below minimum allowed.")
        return None, None
    side_multiplier = 1 if order_side.lower() == "buy" else -1
    order_data = {
        "order": {
            "instrument": INSTRUMENT,
            "units": str(units * side_multiplier),
            "type": "STOP",
            "price": str(adjusted_entry),
            "timeInForce": "GTC",
            "positionFill": "DEFAULT",
            "stopLossOnFill": StopLossDetails(price=str(adjusted_sl)).data
        }
    }
    try:
        response = client.request(orders.OrderCreate(ACCOUNT_ID, data=order_data))
        order_id = response["orderFillTransaction"]["id"]
        print(f"Placed {order_side.upper()} entry order at {adjusted_entry} with SL at {adjusted_sl} for {units} units.")
        return order_id, units
    except Exception as e:
        print(f"Error placing {order_side} entry order: {e}")
        return None, None


def place_take_profit_orders(trade_id, entry_price, order_side, total_units):
    """
    Place up to 3 take profit LIMIT orders (with REDUCE_ONLY) for partial exits.
    Adjusts each TP order's units to be a multiple of MIN_POSITION_SIZE.
    If there is a remainder, it is allocated to the final TP order (if possible).
    Prices are adjusted to account for the spread.
    """
    side_multiplier = 1 if order_side.lower() == "buy" else -1
    tp_order_ids = []
    tick_size = get_tick_size()
    if tick_size is None:
        print("Cannot place TP orders without tick size.")
        return tp_order_ids

    # We'll allocate units to each TP level based on the configured percentages.
    ordered_units = 0
    num_levels = len(TAKE_PROFIT_LEVELS)

    for i, tp in enumerate(TAKE_PROFIT_LEVELS):
        if i < num_levels - 1:
            # For all but the final level, round down to a multiple of MIN_POSITION_SIZE.
            raw_units = total_units * tp["percentage"]
            tp_units = (int(raw_units) // MIN_POSITION_SIZE) * MIN_POSITION_SIZE
        else:
            # For the final level, allocate the remaining units (rounded down).
            remainder = total_units - ordered_units
            tp_units = (remainder // MIN_POSITION_SIZE) * MIN_POSITION_SIZE

        if tp_units < MIN_POSITION_SIZE:
            print(f"Skipping TP {i+1}: Calculated TP units ({tp_units}) below MIN_POSITION_SIZE ({MIN_POSITION_SIZE}).")
            continue

        ordered_units += tp_units

        # Calculate TP price
        tp_offset = tp["pips"] * tick_size
        base_tp_price = entry_price + (tp_offset if order_side.lower() == "buy" else -tp_offset)
        adjusted_tp = adjust_for_spread(base_tp_price, order_side)
        tp_order_data = {
            "order": {
                "instrument": INSTRUMENT,
                "units": str(-tp_units * side_multiplier),  # REDUCE_ONLY order
                "type": "LIMIT",
                "price": str(adjusted_tp),
                "timeInForce": "GTC",
                "positionFill": "REDUCE_ONLY"
            }
        }
        try:
            response = client.request(orders.OrderCreate(ACCOUNT_ID, data=tp_order_data))
            tp_order_id = response["orderCreateTransaction"]["id"]
            tp_order_ids.append(tp_order_id)
            print(f"Placed TP {i+1}: Close {tp_units} units at {adjusted_tp}")
        except Exception as e:
            print(f"Error placing TP order {i+1}: {e}")
    return tp_order_ids

# ------------------------------
# Order Cancellation Functions
# ------------------------------

def cancel_order(order_id):
    """Cancel a pending order by ID."""
    try:
        cancel_endpoint = orders.OrderCancel(accountID=ACCOUNT_ID, orderID=order_id)
        client.request(cancel_endpoint)
        print(f"Canceled order {order_id}")
    except Exception as e:
        print(f"Error canceling order {order_id}: {e}")

def cancel_orders(order_ids):
    """Cancel all orders in the provided list."""
    for oid in order_ids:
        cancel_order(oid)

# ------------------------------
# Polling Helpers for OCO Simulation
# ------------------------------

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
    Poll for one of the entry orders to fill.
    Once one is filled, cancel the other order.
    Returns a tuple: (filled_side, trade_id, units)
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        open_trades = get_open_trades()
        for trade in open_trades:
            trade_units = float(trade["initialUnits"])
            filled_side = "buy" if trade_units > 0 else "sell"
            trade_id = trade["id"]
            pending_orders = get_pending_orders()
            for order in pending_orders:
                if order["id"] in [buy_order_id, sell_order_id]:
                    if (filled_side == "buy" and order["id"] == sell_order_id) or \
                       (filled_side == "sell" and order["id"] == buy_order_id):
                        cancel_order(order["id"])
            return filled_side, trade_id, abs(int(trade_units))
        time.sleep(poll_interval)
    print("Timeout waiting for entry fill.")
    return None, None, None

def poll_trade_for_stoploss(trade_id, tp_order_ids, poll_interval=2):
    """
    Poll the trade until it is closed.
    If the trade closes (assumed to be due to stop loss), cancel any remaining TP orders.
    """
    while True:
        open_trades = get_open_trades()
        still_open = any(trade["id"] == trade_id for trade in open_trades)
        if not still_open:
            print(f"Trade {trade_id} is closed. Canceling any pending TP orders.")
            cancel_orders(tp_order_ids)
            break
        time.sleep(poll_interval)

def close_all_trades():
    """Close all open trades."""
    try:
        open_trades = get_open_trades()
        for trade in open_trades:
            close_endpoint = trades.TradeClose(ACCOUNT_ID, tradeID=trade["id"])
            client.request(close_endpoint)
            print(f"Closed trade {trade['id']}")
    except Exception as e:
        print(f"Error closing trades: {e}")

# ------------------------------
# Main Routine
# ------------------------------

def main():
    while True:
        now = datetime.datetime.utcnow()
        # At the start of the hour, place the entry orders.
        if now.minute == 0 and now.second < 5:  # 5-second window at the top of the hour
            high, low = get_first_minute_high_low()
            if high and low:
                print(f"First minute high: {high}, low: {low}")
                # For a BUY entry order, use the high as the base trigger and SL at the low.
                buy_order_id, _ = place_entry_order(high, low, "buy")
                # For a SELL entry order, use the low as the base trigger and SL at the high.
                sell_order_id, _ = place_entry_order(low, high, "sell")
                
                if not buy_order_id or not sell_order_id:
                    print("Failed to place one or both entry orders.")
                    continue

                # Poll until one entry order fills (simulate OCO behavior).
                filled_side, trade_id, units = poll_for_entry_fill(buy_order_id, sell_order_id)
                if filled_side and trade_id:
                    # Use the unadjusted base price for TP calculation.
                    base_entry_price = high if filled_side == "buy" else low
                    tp_order_ids = place_take_profit_orders(trade_id, base_entry_price, filled_side, units)
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
