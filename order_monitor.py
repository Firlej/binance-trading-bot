"""
Order monitor: tracks open/closed orders and prints bot status.
"""

import time

import ccxt

from utils import log_error, log_order, map_range


class OrderMonitor():
    """
    Class to keep track of orders.
    """

    # initialize the class
    def __init__(self, exchange):
        assert isinstance(exchange, ccxt.binance)

        self.exchange = exchange

        self.open_orders = {}
        self.closed_orders = {}
        self.init_orders()

        # key: sell order id, value: buy order id
        self.order_pairs = {}

        print("Initialized OrderMonitor")

    def init_orders(self):
        """
        Fetch all open orders and add them to the open_orders dict
        """
        for open_order in self.exchange.open_orders():
            self.open_orders[open_order["id"]] = open_order
        print(f'{self.exchange.current_timestamp()} | Initialized {len(self.open_orders)} open orders')

    def log(self, order, order_prev = None):
        """
        Log an order and update the open_orders dict
        """
        id = order["id"]
        log_order(order, order_prev)

        match order["status"]:

            case "open":

                self.open_orders[id] = order

            case "canceled":

                if id in self.open_orders:
                    del self.open_orders[id]

            case "closed":

                if id in self.open_orders:
                    del self.open_orders[id]
                    self.closed_orders[id] = order

            case _:
                print(f"error. invalid status: {order['status']}")

    def get_lowest_sell_order(self):
        """
        Get the lowest sell order
        """
        sell_orders = [o for o in self.open_orders.values() if o["side"] == "sell"]
        if len(sell_orders) > 0:
            return min(sell_orders, key=lambda o: o["price"])
        return None

    def get_highest_buy_order(self):
        """
        Get the highest buy order
        """
        buy_orders = [o for o in self.open_orders.values() if o["side"] == "buy"]
        if len(buy_orders) > 0:
            return max(buy_orders, key=lambda o: o["price"])
        return None

    def status(self):
        """
        Print the status of the bot. This includes the current balances, open orders, etc.
        """
        try:

            orders = self.exchange.open_orders()
            buy_orders = [o for o in orders if o["side"] == "buy"]
            sell_orders = [o for o in orders if o["side"] == "sell"]

            sell_base_amount = 0
            sell_base_value = 0
            curr_sell_value = 0

            if len(sell_orders) > 0:
                amounts = [o["amount"] for o in sell_orders]
                values = [o["price"] * o["amount"] for o in sell_orders]
                sell_base_amount = sum(amounts)
                sell_base_value = sum(values)
                curr_sell_value = sell_base_amount * self.exchange.price()

            free_quote, total_quote = self.exchange.quote_balance()
            free_balance_percent = map_range(free_quote, 0, total_quote + sell_base_value, 0, 100)

            prices = [o['price'] for o in sell_orders]
            p_max = max(prices) if len(prices) > 0 else 0
            p_min = min(prices) if len(prices) > 0 else 0

            # Calculate price difference percentage (avoid division by zero)
            if p_min > 0:
                price_diff_pct = round((p_max - p_min) / p_min * 100, 2)
                price_info = f"Min: {p_min} | Max: {p_max} | Diff: {round(p_max - p_min, 2)} ({price_diff_pct}%)"
            else:
                price_info = "No sell orders"

            print(f"""
    {self.exchange.current_timestamp()}
    Available balances | {free_quote:.2f} / {total_quote + sell_base_value:.2f} {self.exchange.quote} ({free_balance_percent:.2f}%) | {sell_base_amount:.5f} {self.exchange.base}
    {self.exchange.base} value          | Expected: {sell_base_value:.2f} | Current: {curr_sell_value:.2f} | Curr loss: {curr_sell_value - sell_base_value:.2f}
    Open orders        | {len(buy_orders)} buy | {len(sell_orders)} sell | {len(orders)} total
    Sell prices        | {price_info}
            """)

        except Exception as e:
            log_error(e, "OrderMonitor.status()")
            print("Error in OrderMonitor.status(). Sleeping for 10 seconds and retrying...")
            time.sleep(10)
            self.status()
