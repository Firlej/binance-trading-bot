"""
This is a simple bot that periodically markets buys and sells on the Binance exchange.
"""

import time
import os
import threading
import signal
import random

from dotenv import load_dotenv
import ccxt


from helpers import OrderMonitor, log_error
from exchange import ExtendedSymbolExchange

############################################

exit_flag = False


def end(_a, _b):
    global exit_flag
    exit_flag = True
    print("Cancelling all open buy orders...")
    exchange.cancel_all_buy_orders()
    print("Exiting...")


signal.signal(signal.SIGINT, end)
signal.signal(signal.SIGTERM, end)

############################################

# load the .env file
load_dotenv()

symbol = os.getenv("SYMBOL")

SLEEP_MIN = int(os.getenv("SLEEP_MIN"))
SLEEP_MAX = int(os.getenv("SLEEP_MAX"))

PROFIT_MARGIN_MIN = float(os.getenv("PROFIT_MARGIN_MIN"))
PROFIT_MARGIN_MAX = float(os.getenv("PROFIT_MARGIN_MAX"))

BUY_CANCEL_TIMEOUT = float(os.getenv("BUY_CANCEL_TIMEOUT"))

print(f"SLEEP_MIN: {SLEEP_MIN} SLEEP_MAX: {SLEEP_MAX}")
print(f"PROFIT_MARGIN_MIN: {PROFIT_MARGIN_MIN} PROFIT_MARGIN_MAX: {PROFIT_MARGIN_MAX}")

############################################

exchange = ExtendedSymbolExchange(symbol=symbol, config={
    "apiKey": os.getenv("API_KEY"),
    "secret": os.getenv("API_SECRET")
})

order_monitor = OrderMonitor(exchange)

############################################


def watch_open_orders():
    """
    This function is run in a separate thread and checks open orders to be filled.
    """
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

        time.sleep(2)


def process_order_update(order):
    """
    Process order updates. Returns True if the order has been filled.
    """
    try:
        order = exchange.fetch_order(order["id"], symbol)

        if order["status"] == "open":
            return False

        if order["status"] == "closed":

            order_monitor.log(order)
            if order["side"] == "buy":
                limit_sell(order)
            else:
                limit_buy(order)
            return True

        if order["status"] == "canceled":

            order_monitor.log(order)
            return True

    except KeyError:
        pass
    except ccxt.errors.NetworkError as e:
        # all kinds of network errors can happen here. log them so they can be
        # examined later
        log_error(e, "process_order_update")

        print("Sleeping for 10 seconds...")
        time.sleep(10)

    return False

############################################


def cancel_order(order, timeout=0):
    """
    Cancel an order. If timeout is specified then the order will be canceled with a delay.
    """

    # split sleep into 1 second intervals to allow for exit_flag to be checked
    for _ in range(int(timeout)):
        # todo check if order is still open, if not then return
        if exit_flag:
            return
        time.sleep(1)

    try:
        canceled_order = exchange.cancel_order(order["id"], symbol=symbol)
        order_monitor.log(canceled_order)

    except (ccxt.errors.OrderNotFound, KeyError):
        pass

############################################


def market_buy():
    """
    Market buy the minimum amount of the symbol.
    """

    try:

        # get min_order_amount based on the current price, min_cost, and
        # min_amount
        price = exchange.price()
        amount = exchange.min_order_amount(price)

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

    except ccxt.errors.ExchangeError as e:

        # todo how to catch a error specific to MAX_NUM_ORDERS? instead of this
        # ugly if statement
        if str(e) == 'binance {"code":-2010,"msg":"Filter failure: MAX_NUM_ORDERS"}':

            print("MAX_NUM_ORDERS reached. Merging orders...")
            # todo - check if there are open buy orders and cancel them
            order_updates = exchange.merge_sell_orders()
            for order_update in order_updates:
                order_monitor.log(order_update)

            market_buy()

        else:

            log_error(e, "market_buy")


# place a limit sell order for the amount of BTC that was bought
def limit_sell(order):
    """
    Limit sell the amount of BTC that was bought.
    """

    try:
        scale = random.uniform(PROFIT_MARGIN_MIN, exchange.scale_by_balance(PROFIT_MARGIN_MIN, PROFIT_MARGIN_MAX))
        sell_price = order["price"] * scale
        sell_amount = order["filled"]

        sell_order = exchange.create_order(
            symbol=symbol,
            type="limit",
            side="sell",
            amount=sell_amount,
            price=sell_price)

        order_monitor.log(sell_order, order)

        # if status closed then immediately buy back
        if sell_order["status"] == "closed":
            limit_buy(sell_order)
            return

    except ccxt.errors.InsufficientFunds:
        print(f'Insufficient funds for limit sell of {sell_amount} at {sell_price} for total: {sell_price * sell_amount}')
        return


# place a limit buy order for the amount of BTC that was sold
def limit_buy(order):
    """
    Limit buy the amount of BTC that was sold. Cancel the order if it is not filled within BUY_CANCEL_TIMEOUT.
    """
    try:
        scale = random.uniform(PROFIT_MARGIN_MIN, exchange.scale_by_balance(PROFIT_MARGIN_MIN, PROFIT_MARGIN_MAX))
        buy_price = order["price"] / scale
        buy_amount = exchange.min_order_amount(buy_price)

        buy_order = exchange.create_order(
            symbol=symbol,
            type="limit",
            side="buy",
            amount=buy_amount,
            price=buy_price)

        order_monitor.log(buy_order)

        # if status closed then immediately buy back
        if buy_order["status"] == "closed":
            limit_sell(buy_order)
            return

        threading.Thread(target=cancel_order, args=(buy_order, BUY_CANCEL_TIMEOUT)).start()

    except ccxt.errors.InsufficientFunds:
        print(f'Insufficient funds for limit buy of {buy_amount} at {buy_price} for total: {buy_price * buy_amount}')
        return


def main():
    """
    Begin the main loop.
    """

    print("Starting main loop...")

    while True:

        seconds_since_last_trade = exchange.seconds_since_last_trade()
        sleep_timer = exchange.scale_by_balance(SLEEP_MAX, SLEEP_MIN)
        if seconds_since_last_trade > sleep_timer:

            market_buy()
            seconds_since_last_trade = 0

            order_monitor.status()

        sleeping_for = int(sleep_timer - seconds_since_last_trade + 1)
        ts = exchange.iso8601(exchange.milliseconds())
        ts_unitl = exchange.iso8601(exchange.milliseconds() + sleeping_for * 1000)
        print(f"{ts} | Sleeping until {ts_unitl}... ({sleeping_for} seconds)")

        # split sleep into 1 second intervals to allow for exit_flag to be
        # checked
        for _ in range(int(sleeping_for)):
            if exit_flag:
                return
            time.sleep(1)


if __name__ == "__main__":
    exchange.cancel_all_buy_orders()

    threading.Thread(target=watch_open_orders).start()

    main()
