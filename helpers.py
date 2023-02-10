import time
import csv
import threading
import math
from decimal import Decimal

import ccxt
import ccxt.pro as ccxtpro

def decimal_precision(f):
    return abs(Decimal(str(f)).as_tuple().exponent)

def round_up_to_n_decimal_places(f, n):
    return math.ceil(f * 10**n) / 10**n

# map a range of values to another range of values
def map_range(x, a, b, y, z):
    return (x - a) * (z - y) / (b - a) + y

class Fetcher():

    def __init__(self, exchange, symbol):
        assert isinstance(exchange, ccxt.binance)

        self.exchange = exchange
        self.symbol = symbol

        self.market = self.exchange.load_markets()[self.symbol]
    
    def price(self):
        return self.exchange.fetch_ticker(self.symbol)['last']

    def min_cost(self):
        return self.market['limits']['cost']['min']
    
    def min_amount(self):
        return self.market['limits']['amount']['min']
    
    def min_price(self):
        return self.market['limits']['price']['min']

    def min_order_amount(self, price=None):
        if price is None:
            price = self.price()
        return math.ceil(self.min_cost() / price / self.min_amount()) * self.min_amount()
    
    def open_orders(self):
        return self.exchange.fetch_open_orders(self.symbol)

    def open_buy_orders(self):
        return [order for order in self.open_orders() if order["side"] == "buy"]
    
    def open_sell_orders(self):
        return [order for order in self.open_orders() if order["side"] == "sell"]
    
    def sell_btc_value(self):
        orders = self.open_sell_orders()
        if len(orders) == 0:
            return 0
        return sum([order["price"] * order["amount"] for order in orders])

    # get the balances
    def balances(self):
        return self.exchange.fetch_balance()

    # get the free and total BUSD balance
    def busd_balance(self):
        balances = self.balances()
        return balances["free"]["BUSD"], balances["total"]["BUSD"]

    # scale a value based on the balance of BUSD
    def scale_by_balance(self, x, y):
        free_busd, total_busd = self.busd_balance()
        sell_btc_value = self.sell_btc_value()
        scaled_value = map_range(free_busd, 0, total_busd + sell_btc_value, x, y)
        assert min(x, y) <= scaled_value <= max(x, y)
        return scaled_value
    
    # get the number of seconds since the last trade
    def seconds_since_last_trade(self):
        trades = self.exchange.fetch_my_trades(self.symbol, limit=1)
        if len(trades) == 0:
            print("No trades found in seconds_since_last_trade. Returning float(\"inf\")")
            return float("inf")
        else:
            return time.time() - trades[0]["timestamp"] // 1000
        
    def order(self, order):
        return self.exchange.fetch_order(order["id"], self.symbol)
    
    def status(self):
        orders = self.open_orders()
        buy_orders = [o for o in orders if o["side"] == "buy"]
        sell_orders = [o for o in orders if o["side"] == "sell"]
        
        sell_btc_amount = 0 if len(sell_orders) == 0 else sum([o["amount"] for o in sell_orders])
        sell_btc_value = 0 if len(sell_orders) == 0 else sum([o["price"] * o["amount"] for o in sell_orders])
        curr_sell_value = 0 if len(sell_orders) == 0 else sell_btc_amount * self.price()
        
        free_busd, total_busd = self.busd_balance()
        free_balance_percent = map_range(free_busd, 0, total_busd + sell_btc_value, 0, 100)
        
        prices = [o['price'] for o in sell_orders]
        p_max = max(prices) if len(prices) > 0 else 0
        p_min = min(prices) if len(prices) > 0 else 0
        
        print(f'''
    {self.exchange.iso8601(self.exchange.milliseconds())}
    Available balances | {"{:.2f}".format(free_busd)} / {"{:.2f}".format(total_busd + sell_btc_value)} BUSD ({"{:.2f}".format(free_balance_percent)}%) | {"{:.5f}".format(sell_btc_amount)} BTC
    BTC value          | Expected: {"{:.2f}".format(sell_btc_value)} | Current: {"{:.2f}".format(curr_sell_value)} | Curr loss: {"{:.2f}".format(curr_sell_value - sell_btc_value)}
    Open orders        | {len(buy_orders)} buy | {len(sell_orders)} sell | {len(orders)} total
    Sell prices        | Min: {p_min} | Max: {p_max} | Diff: {round(p_max - p_min, 2)} ({round((p_max - p_min) / p_min * 100, 2)}%)
        ''')


def log_trade(order):
    with open("trades.csv", "a", newline="") as csvfile:
        
        d = {
            "id": order["id"],
            "timestamp": order["timestamp"],
            "datetime": order["datetime"],
            "type": order["type"],
            "symbol": order["symbol"],
            "side": order["side"],
            "price": order["price"],
            "amount": order["amount"] if order["amount"] else order["filled"],
            "cost": order["price"] * order["amount"],
            "order_id": order["id"],
            "status": order["status"],
        }      
        
        writer = csv.DictWriter(csvfile, fieldnames=d.keys())  
        
        print(
            f'{d["datetime"]} | {d["id"]} | {d["type"].upper():<6} | {d["side"].upper():<4} | {d["amount"]:<7} | {d["price"]:<8} | {d["cost"]:<18} | {d["status"]:<6}'
        )
        
        writer.writerow(d)
