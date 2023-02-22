import time
import os
import threading
import requests
import urllib3

import ccxt

from dotenv import load_dotenv

from helpers import *

############################################

import signal
exit_flag = False

def end():
    global exit_flag
    exit_flag = True
    print("Cancelling all open buy orders...")
    cancel_all_open_buy_orders()
    print("Exiting...")

signal.signal(signal.SIGINT, end)
signal.signal(signal.SIGTERM, end)

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

exchange = ccxt.binance({
    "apiKey": os.getenv("API_KEY"),
    "secret": os.getenv("API_SECRET")
})

fetcher = Fetcher(exchange, symbol)
order_monitor = OrderMonitor(exchange, symbol)

############################################

def watch_open_orders():
    print(f"watch_open_orders started")
    
    while True:
        
        if exit_flag:
            return
        
        lowest_sell_order = order_monitor.get_lowest_sell_order()
        if lowest_sell_order:
            if process_order_update(lowest_sell_order):
                continue
            
        highest_buy_order = order_monitor.get_highest_buy_order()
        if highest_buy_order:
            if process_order_update(highest_buy_order):
                continue
        
        time.sleep(1)

def process_order_update(order):
    try:
        order = exchange.fetch_order(order["id"], symbol)
        if order["status"] == "closed":
            order_monitor.log(order)
            if order["side"] == "buy":
                limit_sell(order)
            else:
                limit_buy(order)
            return True
        elif order["status"] == "canceled":
            order_monitor.log(order)
            return True
        return False
    except KeyError:
        pass
    except Exception as e:
        # all kinds of network errors can happen here. log them so they can be examined later
        log_error(e, __name__)
        
        print("Sleeping for 10 seconds...")
        time.sleep(10)

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
        order_monitor.log(canceled_order)
        
        return canceled_order
    except (ccxt.errors.OrderNotFound, KeyError):
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
        order_monitor.log(order)

        # place a limit sell order for the amount of BTC that was bought
        limit_sell(order)

    except ccxt.errors.InsufficientFunds:
        print("Insufficient funds for market buy")
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
        
        order_monitor.log(sell_order, order)
        
        # if status closed then immediately buy back
        if sell_order["status"] == "closed":
            limit_buy(sell_order)
            return
        
    except requests.exceptions.HTTPError as e:
        print(f"limit_sell requests.exceptions.HTTPError: {str(e)}")
        print(f"Sleeping for 10 secodns and trying limit_sell again")
        # sleep for and additional 10 seconds and try again
        time.sleep(10)
        limit_sell(order)
    except ccxt.errors.InsufficientFunds:
        print(f'Insufficient funds for limit sell of {sell_amount} at {sell_price} for total: {sell_price * sell_amount}')
        return


# place a limit buy order for the amount of BTC that was sold
def limit_buy(order):
    try:

        buy_price = order["price"] / fetcher.scale_by_balance(PROFIT_MARGIN_MIN, PROFIT_MARGIN_MAX)
        buy_amount = fetcher.min_order_amount(buy_price)
        
        buy_order = exchange.create_order(
            symbol=symbol, type="limit", side="buy", amount=buy_amount, price=buy_price
        )

        order_monitor.log(buy_order)
        
        # if status closed then immediately buy back
        if buy_order["status"] == "closed":
            limit_sell(buy_order)
            return
        
        threading.Thread(target=cancel_order, args=(buy_order, SLEEP_MAX)).start()

    except ccxt.errors.InsufficientFunds:
        print(f'Insufficient funds for limit buy of {buy_amount} at {buy_price} for total: {buy_price * buy_amount}')
        return
    except ccxt.errors.InvalidOrder as e:
        print(f"Tried to limit buy {buy_amount} at ~{buy_price} for total: ~{buy_price * buy_amount} but got an error: {str(e)}")
        # todo not trying actually lols
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
            
            order_monitor.status()
        
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