"""
Implementation of the ExtendedSymbolExchange class.
"""

import math
import time
import requests

import numpy as np
import ccxt

from helpers import log_error, map_range

class ExtendedSymbolExchange(ccxt.binance):
    """
    Wrapper class for ccxt.binance that adds some extra functionality.
    """
    def __init__(self, symbol, config):

        super().__init__(config)

        # print ts
        print(f"{self.iso8601(self.milliseconds())}")

        print(f"Initializing {self.__class__.__name__}...")
        self.s = symbol
        self.m = self.load_markets()[self.s]

        self.precision = self.m['precision']

        self.min_amount = self.m['limits']['amount']['min']
        self.min_price = self.m['limits']['price']['min']
        self.min_cost = self.m['limits']['cost']['min']

        self.max_num_orders = self.get_max_num_orders()

        self.base = self.m['base']
        self.quote = self.m['quote']

        print(f"min_cost: {self.min_cost} {self.quote}")
        print(f"min_amount: {self.min_amount} {self.base}")
        print(f"min_price: {self.min_price} {self.quote}")
        print(f"min_order_amount: {self.min_order_amount()} {self.base} at {self.price()} {self.quote}")

    def round(self, x, precision):
        """
        Round x to the specified decimal precision. Used to round amounts and prices.
        """
        # {'amount': 5, 'base': 8, 'price': 2, 'quote': 8}
        assert precision in self.precision.keys(), f"precision must be one of {self.precision.keys()}"

        return round(x, self.precision[precision])

    def get_max_num_orders(self):
        """
        Get the maximum number of orders allowed on the exchange for this symbol.
        """
        max_num_orders = next((f['maxNumOrders'] for f in self.m["info"]["filters"] if f['filterType'] == 'MAX_NUM_ORDERS'), None)
        return int(max_num_orders)

    # wrapper for create_order() that retries on network errors
    def create_order(self, symbol, type, side, amount, price=None, params={}):
        """
        Wrapper for create_order() that retries on transient network errors.
        """

        try:

            return super().create_order(
                symbol=symbol,
                type=type,
                side=side,
                amount=amount,
                price=price,
                params=params)

        except (ccxt.errors.NetworkError, ccxt.errors.InvalidOrder, ccxt.errors.DDoSProtection, requests.exceptions.HTTPError) as e:

            print(f"Error: Tried to {type} {side} {amount} {self.base} at {price} {self.quote} but got error.")
            log_error(e, "ExtendedSymbolExchange.create_order()")
            print("Retrying in 10 seconds...")
            time.sleep(10)

            return self.create_order(
                symbol=symbol,
                type=type,
                side=side,
                amount=amount,
                price=price,
                params=params)

    def price(self):
        """
        Get the current price of the symbol.
        """
        return self.fetch_ticker(self.s)['last']

    def min_order_amount(self, price=None):
        """
        Get the minimum amoount of the base currency that can be traded in one order.
        """
        if price is None:
            price = self.price()
        min_cost = self.min_cost + self.min_price
        return math.ceil(min_cost / price / self.min_amount) * self.min_amount

    def open_orders(self):
        """
        Get all open orders for the symbol.
        """
        return self.fetch_open_orders(self.s)

    def open_buy_orders(self):
        """
        Get all open buy orders for the symbol.
        """
        return [order for order in self.open_orders() if order["side"] == "buy"]

    def open_sell_orders(self):
        """
        Get all open sell orders for the symbol.
        """
        return [order for order in self.open_orders() if order["side"] == "sell"]

    def sell_base_value(self):
        """
        Calculate the total quote currency value of all open sell orders.
        """
        orders = self.open_sell_orders()
        if len(orders) == 0:
            return 0
        values = [order["price"] * order["amount"] for order in orders]
        return sum(values)

    def base_balance(self):
        """
        Get free and total base currency balance.
        """
        balances = self.fetch_balance()
        return balances["free"][self.base], balances["total"][self.base]

    def quote_balance(self):
        """
        Get free and total quote currency balance.
        """
        balances = self.fetch_balance()
        return balances["free"][self.quote], balances["total"][self.quote]

    def scale_by_balance(self, x, y):
        """
        Get a value between x and y scaled linearly by the balance of the quote currency.
        """

        try:

            free_quote, total_quote = self.quote_balance()

            sell_base_value = self.sell_base_value()

            # todo sometimes this throws an error `TypeError: can only
            # concatenate str (not "float") to str``
            scaled_value = map_range(free_quote, 0, total_quote + sell_base_value, x, y)

            assert min(x, y) <= scaled_value <= max(x, y)
            return scaled_value

        except ccxt.errors.DDoSProtection as e:
            
            log_error(e, "scale_by_balance()")
            print("Retrying in 10 seconds...")
            time.sleep(30)
            
            return self.scale_by_balance(x, y)

        except Exception as e:

            log_error(e, "scale_by_balance()")

            # still raise the error
            raise e

    def seconds_since_last_trade(self):
        """
        Get seconds since last trade.
        """

        try:

            trades = self.fetch_my_trades(self.s, limit=1)
            if len(trades) == 0:
                print("No trades found in seconds_since_last_trade. Returning float(\"inf\")")
                return float("inf")

            return time.time() - trades[0]["timestamp"] // 1000

        except ccxt.errors.DDoSProtection as e:
            
            log_error(e, "seconds_since_last_trade()")
            print("Retrying in 10 seconds...")
            time.sleep(10)
            
            return self.seconds_since_last_trade()

    def get_lowest_sell_order(self):
        """
        Get lowest sell order.
        """
        orders = self.open_sell_orders()
        if len(orders) == 0:
            return None

        return min(orders, key=lambda order: order["price"])

    def get_highest_buy_order(self):
        """
        Get highest buy order.
        """
        orders = self.open_buy_orders()
        if len(orders) == 0:
            return None
        return max(orders, key=lambda order: order["price"])

    def merge_sell_orders(self):
        """
        Merge sell orders into pairs of orders with summed amounts and average weighted prices.
        """

        orders = self.open_sell_orders()

        if len(orders) < 10:
            raise Exception("Not enough orders to merge")

        orders.sort(key=lambda order: -order["price"])

        # skip first order
        orders = orders[1:]

        # use only top half of orders
        # orders = orders[:len(orders) // 2]

        # keep only even number of orders
        if len(orders) % 2 != 0:
            orders = orders[:-1]

        prev_value = self.sell_base_value()

        order_updates = []

        # Iterate over sell orders in pairs
        for i in range(0, len(orders) - 1, 2):
            # Get the two orders in the current pair
            order1 = orders[i]
            order2 = orders[i + 1]

            prices = [order1['price'], order2['price']]
            amounts = [order1['amount'], order2['amount']]

            new_amount = np.sum(amounts)
            new_price = np.average(prices, weights=amounts) + self.min_price + self.min_price

            # Cancel the old orders
            order_updates.append(self.cancel_order(order1['id'], symbol=self.s))
            order_updates.append(self.cancel_order(order2['id'], symbol=self.s))

            # Place the new order
            new_order = self.create_order(
                symbol=self.s,
                type='limit',
                side='sell',
                amount=new_amount,
                price=new_price,
            )

            order_updates.append(new_order)

        new_value = self.sell_base_value()
        print(f"Sell {self.base} value | {prev_value=} | {new_value=}")

        return order_updates

    def current_timestamp(self):
        """
        Get current timestamp as ISO 8601 string.
        """
        return self.iso8601(self.milliseconds())

    def cancel_all_buy_orders(self):
        """
        Cancel all buy orders for the current symbol.
        """
        for order in self.open_buy_orders():
            self.cancel_order(order["id"], symbol=self.s)

    def sell_remaining_base_for_max_price(self):
        """
        If there are any base currency left, sell it for the maximum price of the current sell orders.
        """

        free, _ = self.base_balance()

        sell_orders = self.open_sell_orders()

        assert len(sell_orders) > 0, "No sell orders found"

        prices = [o["price"] for o in sell_orders]
        max_sell_price = max(prices) - self.min_price

        assert free >= self.min_order_amount(max_sell_price), f"free {free} < min_order_amount {self.min_order_amount(max_sell_price)}"

        if free > self.min_order_amount():

            self.create_order(
                symbol=self.s,
                type="limit",
                side="sell",
                amount=free,
                price=max_sell_price)
