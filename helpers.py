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

# Use for catching `Exception` and printing debug into where all kinds of different errors can happen
def log_error(e, name):
    module = e.__module__ if hasattr(e, "__module__") else ""
    print(f'''
    Error in {name}:
    {e.__class__=}
    {module=}
    {e.args=}
    {e.__context__=}
    Error occured in {e.__traceback__.tb_frame.f_code.co_filename} at line {e.__traceback__.tb_lineno}
    ''')
 
def log_order(order):
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
    print(
        f'{d["datetime"]} | {d["id"]} | {d["type"].upper():<6} | {d["side"].upper():<4} | {d["amount"]:<7} | {d["price"]:<8} | {d["cost"]:<18} | {d["status"]:<6}'
    )
        


# class to keep track of orders. open orders are stored in a dictionary and closed orders are stored in a list
class OrderMonitor():
    
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
        for open_order in self.exchange.open_orders():
            self.open_orders[open_order["id"]] = open_order
        print(f'{self.exchange.ts()} | Initialized {len(self.open_orders)} open orders')
    
    def log(self, order):
        
        id = order["id"]
        log_order(order)
            
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
        sell_orders = [o for o in self.open_orders.values() if o["side"] == "sell"]
        if len(sell_orders) > 0:
            return min(sell_orders, key=lambda o: o["price"])
        return None
    
    def get_highest_buy_order(self):
        buy_orders = [o for o in self.open_orders.values() if o["side"] == "buy"]
        if len(buy_orders) > 0:
            return max(buy_orders, key=lambda o: o["price"])
        return None
    
    def status(self):
        
        try:
        
            orders = self.exchange.open_orders()
            buy_orders = [o for o in orders if o["side"] == "buy"]
            sell_orders = [o for o in orders if o["side"] == "sell"]
            
            sell_btc_amount = 0 if len(sell_orders) == 0 else sum([o["amount"] for o in sell_orders])
            sell_btc_value = 0 if len(sell_orders) == 0 else sum([o["price"] * o["amount"] for o in sell_orders])
            curr_sell_value = 0 if len(sell_orders) == 0 else sell_btc_amount * self.exchange.price()
            
            free_busd, total_busd = self.exchange.quote_balance()
            free_balance_percent = map_range(free_busd, 0, total_busd + sell_btc_value, 0, 100)
            
            prices = [o['price'] for o in sell_orders]
            p_max = max(prices) if len(prices) > 0 else 0
            p_min = min(prices) if len(prices) > 0 else 0
            
            print(f'''
    {self.exchange.ts()}
    Available balances | {"{:.2f}".format(free_busd)} / {"{:.2f}".format(total_busd + sell_btc_value)} BUSD ({"{:.2f}".format(free_balance_percent)}%) | {"{:.5f}".format(sell_btc_amount)} BTC
    BTC value          | Expected: {"{:.2f}".format(sell_btc_value)} | Current: {"{:.2f}".format(curr_sell_value)} | Curr loss: {"{:.2f}".format(curr_sell_value - sell_btc_value)}
    Open orders        | {len(buy_orders)} buy | {len(sell_orders)} sell | {len(orders)} total
    Sell prices        | Min: {p_min} | Max: {p_max} | Diff: {round(p_max - p_min, 2)} ({round((p_max - p_min) / p_min * 100, 2)}%)
            ''')
            
        except Exception as e:
            log_error(e, "OrderMonitor.status()")
            
            print("Error in OrderMonitor.status(). Sleeping for 10 seconds and retrying...")
            time.sleep(10)
            
            self.status()
