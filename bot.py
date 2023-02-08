import time
import os
import threading

import ccxt

from dotenv import load_dotenv

from helpers import *

# load the .env file
load_dotenv()

############################################

symbol = "BTC/BUSD"

SLEEP_MIN = 60 * 5
SLEEP_MAX = 60 * 20

PROFIT_MARGIN_MIN = 1.0001
PROFIT_MARGIN_MAX = 1.002

############################################

# define the exchange and the markets you want to trade on
exchange = ccxt.binance({
    "apiKey": os.getenv("API_KEY"),
    "secret": os.getenv("API_SECRET")
})

fetcher = Fetcher(exchange, symbol)

# cancel an order with a timeout
def cancel_order(order, timeout=0):

    time.sleep(timeout)

    try:
        canceled_order = exchange.cancel_order(order["id"], symbol=symbol)
        log_trade(canceled_order)
        return canceled_order
    except ccxt.errors.OrderNotFound:
        return

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
    sell_price = order["price"] * fetcher.scale_by_balance(PROFIT_MARGIN_MIN, PROFIT_MARGIN_MAX)
    sell_amount = order["filled"]
    sell_order = exchange.create_order(
        symbol=symbol, type="limit", side="sell", amount=sell_amount, price=sell_price
    )
    
    log_trade(sell_order)

    # create a separate thread for checking for completed limit sell orders
    threading.Thread(target=check_for_completed_order, args=(sell_order,)).start()


# place a limit buy order for the amount of BTC that was sold
def limit_buy(order):

    buy_price = order["price"] / fetcher.scale_by_balance(PROFIT_MARGIN_MIN, PROFIT_MARGIN_MAX)
    buy_amount = order["filled"]

    try:
        buy_order = exchange.create_order(
            symbol=symbol, type="limit", side="buy", amount=buy_amount, price=buy_price
        )

        log_trade(buy_order)

        # create a separate thread for checking for completed limit orders
        threading.Thread(target=check_for_completed_order, args=(buy_order,)).start()
        threading.Thread(target=cancel_order, args=(buy_order, SLEEP_MAX + 1)).start()

    except ccxt.errors.InsufficientFunds:
        print(f'Insufficient funds for limit buy of {buy_amount} at {buy_price} for total: {buy_price * buy_amount}')
        return

# periodically check for completed order
def check_for_completed_order(order, start_time=1):
    # periodically check if the order has been completed
    timer = start_time
    while True:
        # pass the symbol argument
        order = exchange.fetch_order(order["id"], symbol)
        if order["status"] == "closed":
            log_trade(order)
            if order["side"] == "buy":
                limit_sell(order)
            else:
                limit_buy(order)
            return
        elif order["status"] == "canceled":
            log_trade(order)
            return
        if timer < 120:
            timer += 1
        time.sleep(timer)
        
def watch_currently_open_sell_orders():
    open_sell_orders = fetcher.open_sell_orders()
    
    for i, order in enumerate(open_sell_orders):
        threading.Thread(target=check_for_completed_order, args=(order, i+1)).start()
    
    print(f"Watching {len(open_sell_orders)} currently open sell orders...")

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

        print("sleeping for:", sleep_timer - seconds_since_last_trade + 1)
        time.sleep(sleep_timer - seconds_since_last_trade + 1)

if __name__ == "__main__":
    cancel_all_open_buy_orders()
    watch_currently_open_sell_orders()
    main()