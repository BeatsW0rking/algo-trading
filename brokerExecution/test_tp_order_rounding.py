import unittest
from unittest.mock import patch
from trading_bot import (
    place_take_profit_orders,
    MIN_POSITION_SIZE,
    TAKE_PROFIT_LEVELS,
    client
)

# A helper class to record order creation calls.
class FakeOrderCreate:
    def __init__(self):
        self.calls = []  # to store each call's data

    def __call__(self, endpoint):
        # We assume endpoint is an instance of orders.OrderCreate.
        # Save the order data so we can later inspect it.
        self.calls.append(endpoint.data)
        # Return a fake response containing an order id.
        return {"orderCreateTransaction": {"id": f"tp_order_{len(self.calls)}"}}


class TestTPOrderRounding(unittest.TestCase):

    @patch('trading_bot.adjust_for_spread', side_effect=lambda price, side: price)
    @patch('trading_bot.get_tick_size', return_value=0.0001)
    @patch('trading_bot.MIN_POSITION_SIZE', new=10)
    def test_place_take_profit_orders_rounding_buy(self, mock_get_tick_size, mock_adjust_for_spread):
        """
        Test that for a BUY order, the TP orders are sized in multiples of the MIN_POSITION_SIZE
        and any leftover that is too small is not allocated.
        For example, with total_units=97 and configured TP percentages of:
          - Level 1: 50%
          - Level 2: 30%
          - Level 3: 20%
        we expect:
          Level 1: floor(97*0.5)=48 → rounded down to 40 units,
          Level 2: floor(97*0.3)=29 → rounded down to 20 units,
          Level 3: remainder = 97 - (40+20)=37 → rounded down to 30 units.
        """
        fake_order_create = FakeOrderCreate()
        with patch('trading_bot.client.request', side_effect=fake_order_create):
            # Call the function under test.
            # For testing, we use:
            #  - trade_id as a dummy string,
            #  - entry_price = 1.1000,
            #  - order_side = "buy",
            #  - total_units = 97.
            order_ids = place_take_profit_orders("dummy_trade", 1.1000, "buy", 97)

            # We expect three TP orders.
            self.assertEqual(len(fake_order_create.calls), 3)

            # For a BUY order, side_multiplier is 1 and the code sets units as str(-tp_units).
            # Expected units:
            #  Level 1: 40 units  → order data "units" should be "-40"
            #  Level 2: 20 units  → order data "units" should be "-20"
            #  Level 3: 30 units  → order data "units" should be "-30"
            expected_units = ["-40", "-20", "-30"]
            for i, call_data in enumerate(fake_order_create.calls):
                self.assertEqual(call_data["order"]["units"], expected_units[i])
            # Also, verify that the function returns three order ids.
            self.assertEqual(len(order_ids), 3)

    @patch('trading_bot.adjust_for_spread', side_effect=lambda price, side: price)
    @patch('trading_bot.get_tick_size', return_value=0.0001)
    @patch('trading_bot.MIN_POSITION_SIZE', new=10)
    def test_place_take_profit_orders_rounding_sell(self, mock_get_tick_size, mock_adjust_for_spread):
        """
        Test that for a SELL order, the TP orders are sized in multiples of the MIN_POSITION_SIZE.
        For SELL orders, the code uses a side_multiplier of -1 so that the order 'units' become positive.
        Using the same percentages and total_units as above:
          Level 1: 40 units → "40"
          Level 2: 20 units → "20"
          Level 3: 30 units → "30"
        """
        fake_order_create = FakeOrderCreate()
        with patch('trading_bot.client.request', side_effect=fake_order_create):
            order_ids = place_take_profit_orders("dummy_trade", 1.1000, "sell", 97)
            self.assertEqual(len(fake_order_create.calls), 3)
            # For a SELL order, expected units are positive.
            expected_units = ["40", "20", "30"]
            for i, call_data in enumerate(fake_order_create.calls):
                self.assertEqual(call_data["order"]["units"], expected_units[i])
            self.assertEqual(len(order_ids), 3)


if __name__ == '__main__':
    unittest.main()
