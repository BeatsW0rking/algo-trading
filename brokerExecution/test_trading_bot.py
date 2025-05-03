import unittest
from unittest.mock import patch, MagicMock
import math
import datetime
import time

# Import the functions and constants from your trading bot module.
from oanda_h1_m0_strategy_v2_cgpt import (
    get_tick_size,
    get_current_bid_ask,
    adjust_for_spread,
    get_first_minute_high_low,
    get_account_details,
    get_pip_value,
    calculate_position_size,
    place_entry_order,
    place_take_profit_orders,
    cancel_order,
    cancel_orders,
    get_pending_orders,
    get_open_trades,
    poll_for_entry_fill,
    poll_trade_for_stoploss,
    close_all_trades,
    MIN_POSITION_SIZE,
    TAKE_PROFIT_LEVELS,
    client
)

# A helper function to compare floating point numbers.
def almost_equal(a, b, tol=1e-6):
    return abs(a - b) < tol

# ============================================================================
# Tests for Helper Functions
# ============================================================================
class TestHelperFunctions(unittest.TestCase):
    
    @patch('oanda_h1_m0_strategy_v2_cgpt.client.request')
    def test_get_tick_size(self, mock_request):
        # Simulate InstrumentsDetails response with displayPrecision "5"
        mock_response = {"instruments": [{"displayPrecision": "5"}]}
        mock_request.return_value = mock_response
        tick_size = get_tick_size()
        self.assertTrue(almost_equal(tick_size, 1e-5))
    
    @patch('oanda_h1_m0_strategy_v2_cgpt.client.request')
    def test_get_current_bid_ask(self, mock_request):
        # Simulate a pricing response with fixed bid and ask
        mock_response = {"prices": [{
            "bids": [{"price": "1.1000"}],
            "asks": [{"price": "1.1002"}]
        }]}
        mock_request.return_value = mock_response
        bid, ask = get_current_bid_ask()
        self.assertEqual(bid, 1.1000)
        self.assertEqual(ask, 1.1002)
    
    @patch('oanda_h1_m0_strategy_v2_cgpt.get_current_bid_ask', return_value=(1.1000, 1.1002))
    def test_adjust_for_spread_buy(self, mock_get_bid_ask):
        # For a BUY order, price is increased by half the spread.
        adjusted = adjust_for_spread(1.1000, "buy")
        self.assertTrue(almost_equal(adjusted, 1.1000 + 0.0001))
    
    @patch('oanda_h1_m0_strategy_v2_cgpt.get_current_bid_ask', return_value=(1.1000, 1.1002))
    def test_adjust_for_spread_sell(self, mock_get_bid_ask):
        # For a SELL order, price is decreased by half the spread.
        adjusted = adjust_for_spread(1.1000, "sell")
        self.assertTrue(almost_equal(adjusted, 1.1000 - 0.0001))
    
    @patch('oanda_h1_m0_strategy_v2_cgpt.client.request')
    def test_get_first_minute_high_low(self, mock_request):
        # Simulate a candle endpoint response.
        mock_response = {"candles": [{"mid": {"h": "1.1050", "l": "1.0950"}}]}
        mock_request.return_value = mock_response
        high, low = get_first_minute_high_low()
        self.assertAlmostEqual(high, 1.1050)
        self.assertAlmostEqual(low, 1.0950)
    
    @patch('oanda_h1_m0_strategy_v2_cgpt.client.request')
    def test_get_account_details(self, mock_request):
        # Simulate an account details response.
        mock_response = {"account": {"balance": "10000", "marginAvailable": "5000"}}
        mock_request.return_value = mock_response
        balance, margin = get_account_details()
        self.assertEqual(balance, 10000)
        self.assertEqual(margin, 5000)
    
    @patch('oanda_h1_m0_strategy_v2_cgpt.get_tick_size', return_value=0.0001)
    @patch('oanda_h1_m0_strategy_v2_cgpt.client.request')
    def test_get_pip_value(self, mock_request, mock_get_tick_size):
        # Simulate pricing info response.
        mock_response = {"prices": [{
            "bids": [{"price": "1.1000"}],
            "asks": [{"price": "1.1002"}]
        }]}
        mock_request.return_value = mock_response
        pip_value = get_pip_value()
        self.assertTrue(almost_equal(pip_value, 0.0001 / 1.1))
    
    @patch('oanda_h1_m0_strategy_v2_cgpt.get_pip_value')
    @patch('oanda_h1_m0_strategy_v2_cgpt.get_account_details')
    @patch('oanda_h1_m0_strategy_v2_cgpt.get_tick_size', return_value=0.0001)
    def test_calculate_position_size(self, mock_get_tick_size, mock_get_account_details, mock_get_pip_value):
        entry_price = 1.1000
        stop_loss = 1.0990  # distance = 0.0010
        # For this test, assume pip_value ~ 0.0001/1.1 (~9.09e-05)
        mock_get_pip_value.return_value = 0.0001 / 1.1
        mock_get_account_details.return_value = (10000, 10000)
        size = calculate_position_size(entry_price, stop_loss)
        # raw_size = 100 / (0.001 / (0.0001/1.1)) ≈ 9.09; floor to 9 (if MIN_POSITION_SIZE==1)
        self.assertEqual(size, 9090)

# ============================================================================
# Tests for Order Placement Functions
# ============================================================================
class TestOrderPlacement(unittest.TestCase):
    
    @patch('oanda_h1_m0_strategy_v2_cgpt.client.request')
    @patch('oanda_h1_m0_strategy_v2_cgpt.get_current_bid_ask', return_value=(1.1000, 1.1002))
    @patch('oanda_h1_m0_strategy_v2_cgpt.adjust_for_spread', side_effect=lambda price, side: price)
    @patch('oanda_h1_m0_strategy_v2_cgpt.get_account_details')
    @patch('oanda_h1_m0_strategy_v2_cgpt.get_tick_size', return_value=0.0001)
    def test_place_entry_order(self, mock_get_tick_size, mock_get_account_details, mock_adjust_for_spread,  mock_get_current_bid_ask, mock_request):
        # Simulate a successful order creation response.
        response_data = {"orderFillTransaction": {"id": "entry_order_1", "tradeID": "trade_1"}}
        mock_request.return_value = response_data
        mock_get_account_details.return_value = (10000, 5000)  
 
        entry_price = 1.1050
        stop_loss = 1.0950
        order_side = "buy"
        order_id, units = place_entry_order(entry_price, stop_loss, order_side)
        self.assertEqual(order_id, "entry_order_1")
        self.assertTrue(units > 0)
    
    # A helper fake order creation function to record calls.
    class FakeOrderCreate:
        def __init__(self):
            self.calls = []  # Record each call’s data.
        def __call__(self, endpoint):
            self.calls.append(endpoint.data)
            return {"orderCreateTransaction": {"id": f"tp_order_{len(self.calls)}"}}
    
    @patch('oanda_h1_m0_strategy_v2_cgpt.adjust_for_spread', side_effect=lambda price, side: price)
    @patch('oanda_h1_m0_strategy_v2_cgpt.get_tick_size', return_value=0.0001)
    @patch('oanda_h1_m0_strategy_v2_cgpt.MIN_POSITION_SIZE', new=10)
    def test_place_take_profit_orders_rounding_buy(self, mock_get_tick_size, mock_adjust_for_spread):
        """
        For a BUY order with total_units=97 and TP percentages:
          - Level 1: 50% → raw = 48.5, rounded down to 40 (multiple of 10)
          - Level 2: 30% → raw = 29.1, rounded down to 20
          - Level 3: remainder = 97 - (40+20) = 37, rounded down to 30.
        """
        fake_order_create = TestOrderPlacement.FakeOrderCreate()
        with patch('oanda_h1_m0_strategy_v2_cgpt.client.request', side_effect=fake_order_create):
            order_ids = place_take_profit_orders("dummy_trade", 1.1000, "buy", 97)
            self.assertEqual(len(fake_order_create.calls), 3)
            expected_units = ["-40", "-20", "-30"]
            for i, call_data in enumerate(fake_order_create.calls):
                self.assertEqual(call_data["order"]["units"], expected_units[i])
            self.assertEqual(len(order_ids), 3)
    
    @patch('oanda_h1_m0_strategy_v2_cgpt.adjust_for_spread', side_effect=lambda price, side: price)
    @patch('oanda_h1_m0_strategy_v2_cgpt.get_tick_size', return_value=0.0001)
    @patch('oanda_h1_m0_strategy_v2_cgpt.MIN_POSITION_SIZE', new=10)
    def test_place_take_profit_orders_rounding_sell(self, mock_get_tick_size, mock_adjust_for_spread):
        """
        For a SELL order with total_units=97, we expect TP orders with units:
          Level 1: "40", Level 2: "20", Level 3: "30"
        """
        fake_order_create = TestOrderPlacement.FakeOrderCreate()
        with patch('oanda_h1_m0_strategy_v2_cgpt.client.request', side_effect=fake_order_create):
            order_ids = place_take_profit_orders("dummy_trade", 1.1000, "sell", 97)
            self.assertEqual(len(fake_order_create.calls), 3)
            expected_units = ["40", "20", "30"]
            for i, call_data in enumerate(fake_order_create.calls):
                self.assertEqual(call_data["order"]["units"], expected_units[i])
            self.assertEqual(len(order_ids), 3)
    
    @patch('oanda_h1_m0_strategy_v2_cgpt.client.request')
    def test_cancel_order(self, mock_request):
        # Call cancel_order and verify that client.request is invoked with an endpoint that has the correct orderID.
        cancel_order("order_test")
        called_endpoint = mock_request.call_args[0][0]
        # print(called_endpoint)
        self.assertIn("order_test", str(called_endpoint))
    
    @patch('oanda_h1_m0_strategy_v2_cgpt.cancel_order')
    def test_cancel_orders(self, mock_cancel_order):
        order_ids = ["order1", "order2", "order3"]
        cancel_orders(order_ids)
        self.assertEqual(mock_cancel_order.call_count, 3)

# ============================================================================
# Tests for Polling and Trade Closure Functions
# ============================================================================
class TestPollingFunctions(unittest.TestCase):
    
    @patch('oanda_h1_m0_strategy_v2_cgpt.get_open_trades')
    @patch('oanda_h1_m0_strategy_v2_cgpt.get_pending_orders')
    @patch('oanda_h1_m0_strategy_v2_cgpt.cancel_order')
    def test_poll_for_entry_fill(self, mock_cancel_order, mock_get_pending_orders, mock_get_open_trades):
        # Simulate an open trade that indicates the entry order has been filled.
        open_trade = {"id": "trade_entry", "initialUnits": "100"}
        mock_get_open_trades.return_value = [open_trade]
        # Simulate pending orders that include both the buy and sell orders.
        mock_get_pending_orders.return_value = [{"id": "order_buy"}, {"id": "order_sell"}]
        filled_side, trade_id, trade_units = poll_for_entry_fill("order_buy", "order_sell", poll_interval=0.1, timeout=2)
        self.assertEqual(filled_side, "buy")
        self.assertEqual(trade_id, "trade_entry")
        self.assertEqual(trade_units, 100)
        # Ensure that cancel_order was called to cancel the opposite order.
        mock_cancel_order.assert_called()
    
    @patch('oanda_h1_m0_strategy_v2_cgpt.get_open_trades')
    @patch('oanda_h1_m0_strategy_v2_cgpt.cancel_orders')
    def test_poll_trade_for_stoploss(self, mock_cancel_orders, mock_get_open_trades):
        # Simulate that the trade is initially open then closes.
        mock_get_open_trades.side_effect = [
            [{"id": "trade_entry", "initialUnits": "100"}],
            []  # trade closed
        ]
        poll_trade_for_stoploss("trade_entry", ["tp_order_1", "tp_order_2"], poll_interval=0.1)
        mock_cancel_orders.assert_called_with(["tp_order_1", "tp_order_2"])
    
    @patch('oanda_h1_m0_strategy_v2_cgpt.get_open_trades')
    @patch('oanda_h1_m0_strategy_v2_cgpt.client.request')
    def test_close_all_trades(self, mock_request, mock_get_open_trades):
        # Simulate two open trades.
        open_trades = [{"id": "trade1"}, {"id": "trade2"}]
        mock_get_open_trades.return_value = open_trades
        # For each trade, simulate a successful close.
        mock_request.return_value = {}
        close_all_trades()
        self.assertEqual(mock_request.call_count, len(open_trades))

# ============================================================================
# Integration Test Using a Stub OANDA API
# ============================================================================
# Assume we have a file named stub_oanda.py defining FakeOandaClient.
# (See the separate stub_oanda.py file for details.)
class TestIntegrationWithStubOandaAPI(unittest.TestCase):
    from stub_oanda import FakeOandaClient  # Import the stub client
    def setUp(self):
        self.fake_client = self.FakeOandaClient()
        patcher = patch('oanda_h1_m0_strategy_v2_cgpt.client', self.fake_client)
        self.addCleanup(patcher.stop)
        patcher.start()
    
    def test_integration_flow(self):
        # Simulate placing entry orders, filling one, and then closing the trade.
        entry_price = 1.1050
        stop_loss = 1.0950
        order_side = "sell"
        order_id, units = place_entry_order(entry_price, stop_loss, order_side)
        self.assertIsNotNone(order_id)
        # poll_for_entry_fill will see our FakeOandaClient’s open trade.
        filled_side, trade_id, trade_units = poll_for_entry_fill("order_entry", "order_entry", poll_interval=0.5, timeout=5)
        self.assertEqual(filled_side, "sell")
        self.assertEqual(trade_id, "trade_1")
        self.assertEqual(trade_units, abs(units))
        # Simulate closing the trade.
        from oandapyV20.endpoints.trades import TradeClose, TradesList
        close_endpoint = TradeClose("dummy_account", tradeID=trade_id)
        self.fake_client.request(close_endpoint)
        trades_list = self.fake_client.request(TradesList("dummy_account"))
        self.assertEqual(trades_list["trades"], [])

# ============================================================================
# Main Block to Run All Tests
# ============================================================================
if __name__ == '__main__':
    unittest.main()
