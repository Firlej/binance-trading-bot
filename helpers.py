import time
import csv
import threading
import math

import ccxt
import ccxt.pro as ccxtpro

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

def log_trade(order):
    with open("trades.csv", "a", newline="") as csvfile:
        
        d = {
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
            f'{d["datetime"]} | {d["type"]:<6} | {d["side"]:<4} | {d["amount"]:<7} | {d["price"]:<8} | {d["cost"]:<18} | {d["status"]:<6}'
        )
        
        writer.writerow(d)
