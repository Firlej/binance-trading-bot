import time
import ccxt
import os
import csv
import threading
from dotenv import load_dotenv
import json

# load the .env file
load_dotenv()

# define the exchange and the markets you want to trade on
exchange = ccxt.binance(
    {"apiKey": os.getenv("API_KEY"), "secret": os.getenv("API_SECRET")}
)

symbol = "BTC/BUSD"

budget = 10.25

SLEEP_MIN = 60
SLEEP_MAX = 60 * 20

PROFIT_MARGIN_MIN = 1.00001
PROFIT_MARGIN_MAX = 1.002

last_trade_timestamp = 0

# free_busd, total_busd = 0, 0

# get the number of seconds since the last trade
def get_seconds_since_last_trade():
    global last_trade_timestamp
    if last_trade_timestamp == 0:
        return 0
    return time.time() - last_trade_timestamp


# update last trade timestamp
def update_last_trade_timestamp():
    last_trade = exchange.fetch_my_trades(symbol, limit=1)[0]
    global last_trade_timestamp
    last_trade_timestamp = last_trade["timestamp"] // 1000


# periodically update the last trade timestamp
def update_last_trade_timestamp_thread():
	while True:
		update_last_trade_timestamp()
		time.sleep(5)

# start the thread to update the last trade timestamp
threading.Thread(target=update_last_trade_timestamp_thread).start()

# map a range of values to another range of values
def map_range(x, a, b, y, z):
    return (x - a) * (z - y) / (b - a) + y

# get current free and total BUSD balance
def get_busd_balances():
    # retrieve all open orders
    open_orders = exchange.fetch_open_orders(symbol=symbol)
    # calculate the total BUSD in open orders
    total_open_order_busd = sum([order["amount"] * order["price"] for order in open_orders])

    balance = exchange.fetch_balance()
    free_busd = balance['BUSD']['free']
    total_busd = free_busd + total_open_order_busd
    return free_busd, total_busd

# get the sell percentage based on the current BUSD balance
def get_sell_percentage():
    free_busd, total_busd = get_busd_balances()
    sell_percentage = map_range(
        free_busd, 0, total_busd, PROFIT_MARGIN_MIN, PROFIT_MARGIN_MAX
    )
    assert sell_percentage >= 1
    return sell_percentage

# get the sleep time based on the current BUSD balance
def get_sleep_scaled():
    free_busd, total_busd = get_busd_balances()
    sleep_scaled = map_range(free_busd, 0, total_busd, SLEEP_MAX, SLEEP_MIN)
    assert sleep_scaled >= SLEEP_MIN
    return sleep_scaled

# log completed market trades and open/completed limit orders to a CSV file
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
            f'{order["side"]} order for {order["amount"]} BTC at a price of {order["price"]} for a value of {(order["price"] * order["amount"])}. status: {order["status"]}'
        )
        writer.writerow(d)


# place a market buy order for the specified budget
def market_buy(budget):

    try:
        # place a market buy order for the specified budget
        order = exchange.create_order(
            symbol, "market", "buy", None, None, {"cost": budget}
        )

        # update last trade timestamp
        global last_trade_timestamp
        last_trade_timestamp = time.time()

        # log the market buy order
        log_trade(order)

        # place a limit sell order for the amount of BTC that was bought
        limit_sell(order)

    except ccxt.errors.InsufficientFunds:
        print("Insufficient funds")
        return


# place a limit sell order for the amount of BTC that was bought
def limit_sell(order):
    sell_price = order["price"] * get_sell_percentage()
    sell_amount = order["filled"]
    sell_order = exchange.create_order(symbol, "limit", "sell", sell_amount, sell_price)
    log_trade(sell_order)  # log limit sell opened

    # create a separate thread for checking for completed limit sell orders
    threading.Thread(target=check_for_completed_order, args=(sell_order,)).start()


# place a limit buy order for the amount of BTC that was sold
def limit_buy(order):

    # exectute cancel_buy_orders() in a seperate thread
    thread = threading.Thread(target=cancel_buy_orders)
    thread.start()

    buy_price = order["price"] / get_sell_percentage()
    buy_amount = order["filled"]

    try:
        buy_order = exchange.create_order(symbol, "limit", "buy", buy_amount, buy_price)

        # create a separate thread for checking for completed orders
        log_trade(buy_order)  # log limit opened opened

        # create a separate thread for checking for completed limit orders
        threading.Thread(target=check_for_completed_order, args=(buy_order,)).start()

    except ccxt.errors.InsufficientFunds:
        print("Insufficient funds")
        return


# periodically check for completed order
def check_for_completed_order(order):
    # check if the limit sell order has been completed every 5 seconds
    timer = 1
    while True:
        order = exchange.fetch_order(order["id"], symbol)  # pass the symbol argument
        # print(order["id"], order['status'])
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


# cancel all open buy orders except the one with the highest buy price
def cancel_buy_orders():

    # get all open orders
    open_orders = exchange.fetch_open_orders(symbol=symbol)

    # filter all open buy orders
    open_buy_orders = [order for order in open_orders if order["side"] == "buy"]

    if len(open_buy_orders) == 0:
        return

    # find the order with highest buy price
    order_max = max(open_buy_orders, key=lambda x: x["price"])

    # cancel all open buy orders except the one with the highest buy price
    for order in open_buy_orders:

        if order["id"] == order_max["id"]:
            continue

        try:
            exchange.cancel_order(order["id"], symbol=symbol)
        except ccxt.errors.OrderNotFound:
            pass

update_last_trade_timestamp()


# main loop
while True:

    seconds_since_last_trade = get_seconds_since_last_trade()
    sleep_timer = get_sleep_scaled()
    if seconds_since_last_trade > sleep_timer:

        # check the available balance of BUSD in the account
        balance = exchange.fetch_balance()
        available_busd = balance["BUSD"]["free"]

        if available_busd < budget:
            print(f"Not enough BUSD in the account. Available balance: {available_busd} BUSD")
        else:
            # buy `budget` worth of bitcoin
            initial_buy_order = market_buy(budget)

        seconds_since_last_trade = 0

    print("sleeping for: ", sleep_timer - seconds_since_last_trade + 1)
    time.sleep(sleep_timer - seconds_since_last_trade + 1)
