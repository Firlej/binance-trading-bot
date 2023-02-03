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

# place a market buy order for the min amount
def market_buy():

    try:

        # get min_order_amount based on the current price, min_cost, and min_amount
        amount = fetcher.min_order_amount()

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


# place a limit sell order for the amount of BTC that was bought
def limit_sell(order):
    sell_price = order["price"] * fetcher.scale_by_balance(PROFIT_MARGIN_MIN, PROFIT_MARGIN_MAX)
    sell_amount = order["filled"]
    sell_order = exchange.create_order(symbol, "limit", "sell", sell_amount, sell_price)
    log_trade(sell_order)  # log limit sell opened

    # create a separate thread for checking for completed limit sell orders
    threading.Thread(target=check_for_completed_order, args=(sell_order,)).start()


# place a limit buy order for the amount of BTC that was sold
def limit_buy(order):

    buy_price = order["price"] / fetcher.scale_by_balance(PROFIT_MARGIN_MIN, PROFIT_MARGIN_MAX)
    buy_amount = order["filled"]

    try:
        buy_order = exchange.create_order(symbol, "limit", "buy", buy_amount, buy_price)

        # create a separate thread for checking for completed orders
        log_trade(buy_order)  # log limit opened opened

        # create a separate thread for checking for completed limit orders
        threading.Thread(target=check_for_completed_order, args=(buy_order,)).start()
        threading.Thread(target=cancel_order, args=(exchange, symbol, buy_order, fetcher.scale_by_balance(SLEEP_MAX, SLEEP_MIN) + 1,)).start()

    except ccxt.errors.InsufficientFunds:
        print("Insufficient funds")
        return

# periodically check for completed order
def check_for_completed_order(order):
    # periodically check if the order has been completed
    timer = 1
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
            return
        if timer < 60:
            timer += 1
        time.sleep(timer)


print("Starting main loop...")

# main loop
while True:

    seconds_since_last_trade = fetcher.seconds_since_last_trade()
    sleep_timer = fetcher.scale_by_balance(SLEEP_MAX, SLEEP_MIN)
    if seconds_since_last_trade > sleep_timer:

        market_buy()
        seconds_since_last_trade = 0

    print("sleeping for: ", sleep_timer - seconds_since_last_trade + 1)
    time.sleep(sleep_timer - seconds_since_last_trade + 1)
