import time
import os
import threading
import requests

import ccxt

from dotenv import load_dotenv

from helpers import *


import signal
exit_flag = False

def end():
    global exit_flag
    exit_flag = True
    print("Cancelling all open buy orders...")
    cancel_all_open_buy_orders()
    print("Exiting...")

def exit_flag_trueSIGINT(signal, frame):
    print("SIGINT detected. Ending...")
    end()

def exit_flag_trueSIGTERM(signal, frame):
    print("SIGTERM detected. Ending...")
    end()

signal.signal(signal.SIGINT, exit_flag_trueSIGINT)
signal.signal(signal.SIGTERM, exit_flag_trueSIGTERM)

############################################

# load the .env file
load_dotenv()

symbol = "BTC/BUSD"

SLEEP_MIN = int(os.getenv("SLEEP_MIN"))
SLEEP_MAX = int(os.getenv("SLEEP_MAX"))

PROFIT_MARGIN_MIN = float(os.getenv("PROFIT_MARGIN_MIN"))
PROFIT_MARGIN_MAX = float(os.getenv("PROFIT_MARGIN_MAX"))

print(f"SLEEP_MIN: {SLEEP_MIN} SLEEP_MAX: {SLEEP_MAX}")
print(f"PROFIT_MARGIN_MIN: {PROFIT_MARGIN_MIN} PROFIT_MARGIN_MAX: {PROFIT_MARGIN_MAX}")

############################################

# define the exchange and the markets you want to trade on
exchange = ccxt.binance({
    "apiKey": os.getenv("API_KEY"),
    "secret": os.getenv("API_SECRET")
})

fetcher = Fetcher(exchange, symbol)

############################################

orders = { order["id"]: order for order in fetcher.open_orders() }

def watch_open_orders():
    print(f"watch_open_orders started")
    
    while True:
        
        if exit_flag:
            return
        
        global orders
        
        # filter orders to only keeps sell orders
        sell_orders = { order["id"]: order for order in orders.values() if order["side"] == "sell" }
        if len(sell_orders) > 0:    
            # get open sell order with lowest sell price
            order = min(sell_orders.values(), key=lambda order: order["price"])
            process_order_update(order)
        
        # filter orders to only keeps sell orders
        buy_orders = { order["id"]: order for order in orders.values() if order["side"] == "buy" }
        if len(buy_orders) > 0:        
            # get open sell order with lowest sell price
            order = max(buy_orders.values(), key=lambda order: order["price"])
            process_order_update(order)
        
        time.sleep(1)

def process_order_update(order):
    try:
        order = exchange.fetch_order(order["id"], symbol)
        if order["status"] == "closed":
            log_trade(order)
            del orders[order["id"]]
            if order["side"] == "buy":
                limit_sell(order)
            else:
                limit_buy(order)
        elif order["status"] == "canceled":
            log_trade(order)
            del orders[order["id"]]
    except requests.exceptions.HTTPError as e:
        print(f"process_order_update requests.exceptions.HTTPError for {order['side']} order: {str(e)}")
        # sleep for and additional 10 seconds
        time.sleep(10)
    except ccxt.errors.InvalidNonce as e:
        print(f"process_order_update ccxt.errors.InvalidNonce for {order['side']} order: {str(e)}")
        # sleep for and additional 10 seconds
        time.sleep(10)
    except KeyError as e:
        print(f"process_order_update KeyError for {order['side']} order: {str(e)}")
        pass

############################################

# cancel an order with a timeout
def cancel_order(order, timeout=0):
    
    # split sleep into 1 second intervals to allow for exit_flag to be checked
    for _ in range(int(timeout)):
        if exit_flag:
            return
        time.sleep(1)

    try:
        canceled_order = exchange.cancel_order(order["id"], symbol=symbol)
        log_trade(canceled_order)
        
        global orders
        del orders[canceled_order["id"]]
        
        return canceled_order
    except ccxt.errors.OrderNotFound:
        pass
    except KeyError:
        pass

############################################

# place a market buy order for the min amount
def market_buy():

    try:

        # get min_order_amount based on the current price, min_cost, and min_amount
        price = fetcher.price()
        amount = fetcher.min_order_amount(price)

        # place a market buy order for the min amount
        order = exchange.create_order(
            symbol=symbol, type="market", side="buy", amount=amount
        )

        # log the market buy order
        log_trade(order)

        # place a limit sell order for the amount of BTC that was bought
        limit_sell(order)

    except ccxt.errors.InsufficientFunds:
        print("Insufficient funds for market buy")
        return
    except ccxt.errors.InvalidOrder as e:
        print(f"Tried to market buy {amount} at ~{price} for total: ~{price * amount} but got an error: {str(e)}")
        print("Trying again in 1 second...")
        time.sleep(1)
        market_buy()


# place a limit sell order for the amount of BTC that was bought
def limit_sell(order):
    try:
        
        sell_price = order["price"] * fetcher.scale_by_balance(PROFIT_MARGIN_MIN, PROFIT_MARGIN_MAX)
        sell_amount = order["filled"]
        
        sell_order = exchange.create_order(
            symbol=symbol, type="limit", side="sell", amount=sell_amount, price=sell_price
        )
        
        log_trade(sell_order)
        
        # if status closed then immediately buy back
        if sell_order["status"] == "closed":
            limit_buy(sell_order)
            return

        global orders
        orders[sell_order["id"]] = sell_order

    except ccxt.errors.InsufficientFunds:
        print(f'Insufficient funds for limit sell of {sell_amount} at {sell_price} for total: {sell_price * sell_amount}')
        return


# place a limit buy order for the amount of BTC that was sold
def limit_buy(order):
    try:

        buy_price = order["price"] / fetcher.scale_by_balance(PROFIT_MARGIN_MIN, PROFIT_MARGIN_MAX)
        buy_amount = order["filled"]
        
        buy_order = exchange.create_order(
            symbol=symbol, type="limit", side="buy", amount=buy_amount, price=buy_price
        )

        log_trade(buy_order)
        
        # if status closed then immediately buy back
        if buy_order["status"] == "closed":
            limit_sell(buy_order)
            return

        global orders
        orders[buy_order["id"]] = buy_order
        
        threading.Thread(target=cancel_order, args=(buy_order, SLEEP_MAX + 1)).start()

    except ccxt.errors.InsufficientFunds:
        print(f'Insufficient funds for limit buy of {buy_amount} at {buy_price} for total: {buy_price * buy_amount}')
        return
    except ccxt.errors.InvalidOrder as e:
        print(f"Tried to limit buy {buy_amount} at ~{buy_price} for total: ~{buy_price * buy_amount} but got an error: {str(e)}")
        print("Trying again in 1 second...")
        time.sleep(1)

def cancel_all_open_buy_orders():
    open_buy_orders = fetcher.open_buy_orders()
    
    for order in open_buy_orders:
        cancel_order(order)

    print(f"Canceled {len(open_buy_orders)} currently open buy orders...")

def main():

    print("Starting main loop...")

    while True:

        seconds_since_last_trade = fetcher.seconds_since_last_trade()
        sleep_timer = fetcher.scale_by_balance(SLEEP_MAX, SLEEP_MIN)
        if seconds_since_last_trade > sleep_timer:

            market_buy()
            seconds_since_last_trade = 0
            
            fetcher.status()
        
        sleeping_for = int(sleep_timer - seconds_since_last_trade + 1)
        ts = exchange.iso8601(exchange.milliseconds())
        ts_unitl = exchange.iso8601(exchange.milliseconds() + sleeping_for * 1000)
        print(f"{ts} | Sleeping until {ts_unitl}... ({sleeping_for} seconds)")
        
        # split sleep into 1 second intervals to allow for exit_flag to be checked
        for _ in range(int(sleeping_for)):
            if exit_flag:
                return
            time.sleep(1)

if __name__ == "__main__":
    cancel_all_open_buy_orders()

    threading.Thread(target=watch_open_orders).start()
    
    main()