import time
import os
import csv
import json
import threading

import ccxt
import ccxt.pro as ccxtpro
import asyncio

from dotenv import load_dotenv


# load the .env file
load_dotenv()

exchange = ccxt.binance(config={
    "apiKey": os.getenv("API_KEY"),
    "secret": os.getenv("API_SECRET")
})

exchangepro = ccxtpro.binance(config={
    "apiKey": os.getenv("API_KEY"),
    "secret": os.getenv("API_SECRET")
})

SYMBOL = "BTC/BUSD"

BUDGET = 10.25

SLEEP_MIN = 60
SLEEP_MAX = 60 * 20

PROFIT_MARGIN_MIN = 1.0000000001
PROFIT_MARGIN_MAX = 1.002

BUY_ORDER_TIMEOUT = 60 * 15

free_busd, total_busd = 0, 0

last_trade_timestamp = 0

open_orders = {}

# map a range of values to another range of values
def map_range(x, a, b, y, z):
    return (x - a) * (z - y) / (b - a) + y

def get_busd_locked_in_open_orders():
    busd_locked_in_open_orders = 0
    for o in open_orders.values():
        if o["side"] == "buy":
            busd_locked_in_open_orders += o["price"] * o["amount"]
    return busd_locked_in_open_orders

def get_sleep():
    busd_locked_in_open_sell_orders = get_busd_locked_in_open_orders()

    print(f"{free_busd=} {total_busd=} {busd_locked_in_open_sell_orders=}")
    sleep = map_range(
        free_busd, 0, total_busd + busd_locked_in_open_sell_orders, SLEEP_MAX, SLEEP_MIN
    )

    assert sleep >= SLEEP_MIN
    assert sleep <= SLEEP_MAX
    return sleep

def get_profit_margin():

    busd_locked_in_open_sell_orders = get_busd_locked_in_open_orders()

    profit_margin = map_range(
        free_busd, 0, total_busd + busd_locked_in_open_sell_orders, PROFIT_MARGIN_MIN, PROFIT_MARGIN_MAX
    )

    assert profit_margin >= PROFIT_MARGIN_MIN
    assert profit_margin <= PROFIT_MARGIN_MAX
    return profit_margin

def update_balances():
    global free_busd, total_busd
    balances = exchange.fetch_balance()
    free_busd = balances["free"]["BUSD"]
    total_busd = balances["total"]["BUSD"]

update_balances()

def update_open_orders():
    global open_orders

    past_open_orders = exchange.fetch_open_orders(symbol=SYMBOL)

    for o in past_open_orders:
        open_orders[o["id"]] = o

    print("open orders len:", len(open_orders))

    for o in open_orders.values():
        print("        ", o["id"], o["status"], o["side"], o["price"], o["amount"])

update_open_orders()

# update last trade timestamp
def update_last_trade_timestamp():
    last_trade = exchange.fetch_my_trades(symbol=SYMBOL, limit=1)[0]
    global last_trade_timestamp
    last_trade_timestamp = last_trade["timestamp"] // 1000

update_last_trade_timestamp()

def log_order(o):

        d = {
            "timestamp": o["timestamp"],
            "type": o["type"],
            "symbol": o["symbol"],
            "side": o["side"],
            "price": o["price"],
            "amount": o["amount"] if o["amount"] else o["filled"],
            "cost": o["price"] * o["amount"],
            "order_id": o["id"],
            "status": o["status"],
        }

        print(
            f'{d["timestamp"]} | {d["side"]} for {d["amount"]} BTC at a price of {d["price"]} for a value of {(d["cost"])}. status: {d["status"]}'
        )

# get the number of seconds since the last trade
def get_seconds_since_last_trade():
    global last_trade_timestamp
    if last_trade_timestamp == 0:
        return 0
    return time.time() - last_trade_timestamp

def cancel_order(order, timeout=0):

    time.sleep(timeout)

    try:
        canceled_order = exchange.cancel_order(order["id"], symbol=SYMBOL)
        log_order(canceled_order)
    except ccxt.errors.OrderNotFound:
        pass

# place a limit sell order for the amount of BTC that was bought
def limit_sell(order):
    assert order["side"] == "buy", json.dumps(order)
    assert order["status"] == "closed", json.dumps(order)
    
    sell_price = order["price"] * get_profit_margin()
    sell_amount = order["filled"]
    sell_order = exchange.create_order(SYMBOL, "limit", "sell", sell_amount, sell_price)

    open_orders[sell_order["id"]] = sell_order

    log_order(sell_order)

# place a limit buy order for the amount of BTC that was bought
def limit_buy(order):
    assert order["side"] == "sell", json.dumps(order)
    assert order["status"] == "closed", json.dumps(order)

    buy_price = order["price"] / get_profit_margin()
    buy_amount = order["filled"]
    buy_order = exchange.create_order(SYMBOL, "limit", "buy", buy_amount, buy_price)

    open_orders[buy_order["id"]] = buy_order

    log_order(buy_order)
    
    threading.Thread(target=cancel_order, args=(buy_order, BUY_ORDER_TIMEOUT)).start()

# place a market buy order
def market_buy():

    try:
        order = exchange.create_order(
            SYMBOL, "market", "buy", None, None, {"cost": BUDGET}
        )

        # update last trade timestamp
        global last_trade_timestamp
        last_trade_timestamp = time.time()

        log_order(order)

        limit_sell(order)

    except ccxt.errors.InsufficientFunds:
        print("Insufficient funds")
        return

# MAIN LOOP
def market_buy_loop():

    update_last_trade_timestamp()
    update_open_orders()
    time.sleep(10)
    update_last_trade_timestamp()
    update_open_orders()

    print("Starting market_buy_loop...")

    while True:
        
        if get_seconds_since_last_trade() > get_sleep():
        
            market_buy()

        sleep = get_sleep() - get_seconds_since_last_trade()
        print("sleeping for", sleep, "seconds")
        time.sleep(sleep)

threading.Thread(target=market_buy_loop).start()



# WEBSOCKET WATCHERS

def ts():
    return exchange.iso8601(exchange.milliseconds())

# BALANCE

async def watch_balance_loop():

    print("Starting watch_balance_loop...")
    
    while True:
        balance = await exchangepro.watch_balance()
        global free_busd
        global total_busd
        
        # check if BUSD, free, and total are in the balance, and free and total are not None
        if "BUSD" in balance and "free" in balance["BUSD"] and "total" in balance["BUSD"] and balance["BUSD"]["free"] and balance["BUSD"]["total"]:
            free_busd, total_busd = balance['BUSD']['free'], balance['BUSD']['total']
            print("BALANCE", ts(), "PROFIT_MARGIN:", get_profit_margin(), f"{free_busd=}", f"{total_busd=}", f"{balance['info']['e']=}")
        else:
            print("BALANCE", ts(), "ERROR:", json.dumps(balance, indent=4))
        pass

# TRADES

async def watch_my_trades_loop():

    print("Starting watch_my_trades_loop...")
    
    while True:
        trades = await exchangepro.watch_my_trades(symbol=SYMBOL)

        global last_trade_timestamp
        last_trade_timestamp = trades[-1]["timestamp"] // 1000

        # for t in trades:
        #     print("TRADE  ", ts(), t['order'], t['type'], t['side'], t['price'], t['amount'])
        #     print(t)
        #     pass

# ORDERS

async def watch_orders_loop():
    
    print("Starting watch_orders_loop...")

    while True:
        orders = await exchangepro.watch_orders(symbol=SYMBOL)
        for o in orders:

            # continue if order was not in open orders
            if o['id'] not in open_orders:
                continue
            
            if o['type'] == 'limit':
                # if order is closed and in open_orders
                if o['status'] == 'closed':
                    if o['side'] == 'buy':
                        limit_sell(o)
                    elif o['side'] == 'sell':
                        limit_buy(o)

                    del open_orders[o['id']]
                    
                elif o["status"] == "canceled":
                    del open_orders[o['id']]
                    # market_buy()
                elif o["status"] == "open":
                    continue

                print("open orders len:", len(open_orders))

                for o in open_orders.values():
                    print("        ", o["id"], o["status"], o["side"], o["price"], o["amount"])

            elif o['type'] == 'market':
                continue


            # o = {key: order[key] for key in keys_to_keep}
            print("ORDER  ", ts(), o['id'], o['type'], o['side'], o['status'])
            # print(o['status'], type(o['timestamp']), type(o['datetime']))

async def main():
        asyncio.ensure_future(watch_balance_loop())
        asyncio.ensure_future(watch_my_trades_loop())
        asyncio.ensure_future(watch_orders_loop())

        # sleep forever
        await asyncio.sleep(float('inf'))

asyncio.run(main())