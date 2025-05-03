# stub_oanda.py

class FakeOandaClient:
    def __init__(self):
        # List of open trades (each trade is a dict, e.g., {"id": "trade_1", "initialUnits": "100"})
        self.fake_open_trades = []
        # List of pending orders (each order is a dict, e.g., {"id": "order_1", "data": {...}})
        self.pending_orders = []
        self.order_counter = 0
        self.trade_counter = 0

    def _new_order_id(self):
        self.order_counter += 1
        return f"order_{self.order_counter}"

    def _new_trade_id(self):
        self.trade_counter += 1
        return f"trade_{self.trade_counter}"

    def request(self, endpoint):
        cls_name = endpoint.__class__.__name__

        if cls_name == "AccountInstruments":
            # Return instrument details with a display precision of 5.
            return {"instruments": [{"displayPrecision": "5"}]}

        elif cls_name == "PricingInfo":
            # Simulate pricing information.
            return {
                "prices": [{
                    "bids": [{"price": "1.1000"}],
                    "asks": [{"price": "1.1002"}]
                }]
            }

        elif cls_name == "InstrumentsCandles":
            # Return a single candle with high and low.
            return {"candles": [{"mid": {"h": "1.1050", "l": "1.0950"}}]}

        elif cls_name == "AccountDetails":
            # Simulate an account details response.
            return {"account": {"balance": "10000", "marginAvailable": "5000"}}

        elif cls_name == "OrderCreate":
            # Retrieve the order data.
            order_data = endpoint.data["order"]
            # Distinguish between an entry order (with stopLossOnFill) and a take profit (LIMIT) order.
            if "stopLossOnFill" in order_data:
                # Simulate immediate fill for the entry order.
                order_id = self._new_order_id()
                trade_id = self._new_trade_id()
                trade = {
                    "id": trade_id,
                    "initialUnits": order_data["units"]
                }
                self.fake_open_trades.append(trade)
                self.pending_orders.append({"id": order_id, "data": order_data})
                return {"orderFillTransaction": {"id": order_id, "tradeID": trade_id}}
            else:
                # For take profit or other orders.
                order_id = self._new_order_id()
                self.pending_orders.append({"id": order_id, "data": order_data})
                return {"orderCreateTransaction": {"id": order_id}}

        elif cls_name == "OrderCancel":
            # Cancel a pending order.
            order_id = endpoint.orderID
            self.pending_orders = [o for o in self.pending_orders if o["id"] != order_id]
            return {}

        elif cls_name == "OrdersPending":
            # Return the current list of pending orders.
            return {"orders": self.pending_orders}

        elif cls_name == "TradesList":
            # Return the list of open trades.
            return {"trades": self.fake_open_trades}

        elif cls_name == "TradeClose":
            # Simulate closing a trade.
            # print(endpoint)
            # trade_id = endpoint.tradeID
            self.fake_open_trades = [] #[t for t in self.fake_open_trades if t["id"] != trade_id]
            return {}

        else:
            # Default stub response.
            return {}
