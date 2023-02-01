import time
import csv
import threading

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
        scaled_value =  map_range(free_busd, 0, total_busd + sell_btc_value, x, y)
        assert min(x, y) <= scaled_value <= max(x, y)
        return scaled_value
    
    # get the number of seconds since the last trade
    def seconds_since_last_trade(self):
        trades = self.exchange.fetch_my_trades(self.symbol, limit=1)
        if len(trades) == 0:
            print("No trades found in seconds_since_last_trade. Returning 0.")
            return 0
        else:
            return time.time() - trades[0]["timestamp"] // 1000


# cancel an order with a timeout
def cancel_order(exchange, symbol, order, timeout=0):
    assert isinstance(exchange, ccxt.binance)

    time.sleep(timeout)

    try:
        canceled_order = exchange.cancel_order(order["id"], symbol=symbol)
        return canceled_order
    except ccxt.errors.OrderNotFound:
        pass

# cancel all open buy orders except the one with the highest buy price
def cancel_buy_orders(fetcher):
    assert isinstance(fetcher, Fetcher)

    open_buy_orders = fetcher.open_buy_orders()

    if len(open_buy_orders) == 0:
        return

    for order in open_buy_orders:
        cancel_order(order)

def log_trade(order):
    with open("trades.csv", "a", newline="") as csvfile:
        fieldnames = [
            "timestamp",
            "type",
            "symbol",
            "side",
            "price",
            "amount",
            "cost",
            "order_id",
            "status",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        d = {
            "timestamp": order["timestamp"],
            "type": order["type"],
            "symbol": order["symbol"],
            "side": order["side"],
            "price": order["price"],
            "amount": order["amount"] if order["amount"] else order["filled"],
            "cost": order["price"] * order["amount"],
            "order_id": order["id"],
            "status": order["status"],
        }

        print(
            f'{d["timestamp"]} | {d["side"]} for {d["amount"]} BTC at a price of {d["price"]} for a value of {(d["cost"])}. status: {d["status"]}'
        )
        writer.writerow(d)