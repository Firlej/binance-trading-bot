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
exchange = ccxt.binance({
    'apiKey': os.getenv('API_KEY'),
    'secret': os.getenv('API_SECRET')
})

symbol = 'BTC/BUSD'

budget = 10.25

SLEEP_MIN = 60
SLEEP_MAX = 60 * 10

PROFIT_MARGIN_MIN = 1.00001
PROFIT_MARGIN_MAX = 1.001

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
	sell_percentage = map_range(free_busd, 0, total_busd, PROFIT_MARGIN_MIN, PROFIT_MARGIN_MAX)
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
    with open('trades.csv', 'a', newline='') as csvfile:
        fieldnames = ['timestamp', 'type', 'symbol', 'side', 'price', 'amount', 'cost', 'order_id', 'status']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        d = {
            'timestamp': order['timestamp'],
            'type': order['type'],
            'symbol': order['symbol'],
            'side': order['side'],
            'price': order['price'],
            'amount': order['amount'] if order['amount'] else order['filled'],
            'cost': order['price'] * order['amount'],  # calculate cost as price * amount
            'order_id': order['id'],  # add order id to log
            'status': order['status']
        }

        print(f'{order["side"]} order for {order["amount"]} BTC at a price of {order["price"]} for a value of {(order["price"] * order["amount"])}. status: {order["status"]}')
        writer.writerow(d)

# place a market buy order for the specified budget
def market_buy(budget):
    # place a market buy order for the specified budget
    order = exchange.create_order(symbol, 'market', 'buy', None, None, {'cost': budget})
    log_trade(order)  # log completed market buy
    limit_sell(order)

# place a limit sell order for the amount of BTC that was bought
def limit_sell(order):
    sell_price = order['price'] * get_sell_percentage()
    sell_amount = order['filled']
    sell_order = exchange.create_order(symbol, 'limit', 'sell', sell_amount, sell_price)
    log_trade(sell_order)  # log limit sell opened

    # create a separate thread for checking for completed limit sell orders
    thread = threading.Thread(target=check_for_completed_order, args=(sell_order,))
    thread.start()

# place a limit buy order for the amount of BTC that was sold
def limit_buy(order):

    cancel_buy_orders()

    buy_price = order['price'] / get_sell_percentage()
    buy_amount = order['filled']
    
    # check the available balance of BUSD in the account
    balance = exchange.fetch_balance()
    available_busd = balance['BUSD']['free']

    if available_busd < buy_price * buy_amount:
        return
    
    buy_order = exchange.create_order(symbol, 'limit', 'buy', buy_amount, buy_price)
    # create a separate thread for checking for completed orders
    log_trade(buy_order)  # log limit opened opened
    thread = threading.Thread(target=check_for_completed_order, args=(buy_order,))
    thread.start()

# periodically check for completed order
def check_for_completed_order(order):
    # check if the limit sell order has been completed every 5 seconds
    timer = 5
    while True:
        order = exchange.fetch_order(order['id'], symbol)  # pass the symbol argument
        # print(order["id"], order['status'])
        if order['status'] == 'closed':
            log_trade(order)
            if (order['side'] == "buy"):
                limit_sell(order)
            else:
                limit_buy(order)
            return
        elif order['status'] == "canceled":
            return
        if timer < 60:
            timer += 1
        time.sleep(timer)

def cancel_buy_orders():
    # Get a list of open orders
    open_orders = exchange.fetch_open_orders(symbol=symbol)

    # Iterate through the open orders and cancel only buy orders
    for order in open_orders:
        if order['side'] == 'buy':
            exchange.cancel_order(order['id'], symbol=symbol)

# get the number of seconds since the last trade
def get_seconds_since_last_trade() -> float:
    trades = exchange.fetch_my_trades(symbol, limit=1)
    last_trade_timestamp = trades[0]['timestamp'] // 1000
    current_time = time.time()
    elapsed_time = current_time - last_trade_timestamp
    return elapsed_time

# main loop
while True:

	seconds_since_last_trade = get_seconds_since_last_trade()
	sleep_timer = get_sleep_scaled()
	if seconds_since_last_trade > sleep_timer:

		# check the available balance of BUSD in the account
		balance = exchange.fetch_balance()
		available_busd = balance['BUSD']['free']

		if available_busd < budget:
			print(f'Not enough BUSD in the account. Available balance: {available_busd} BUSD')
		else:
			# buy `budget` worth of bitcoin
			initial_buy_order = market_buy(budget)
		
		seconds_since_last_trade = 0

	print("sleeping for: ", sleep_timer - seconds_since_last_trade + 1)
	time.sleep(sleep_timer - seconds_since_last_trade + 1)
