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
wait_time = 60 * 3  # wait for 2 hours before placing the next trade
sell_percentage = 1.001  # sell the bitcoin bought in the market buy order for this percentage more

def log_trade(order):
    # log completed market trades and open/completed limit orders to a CSV file
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


def buy(budget):
    # place a market buy order for the specified budget
    order = exchange.create_order(symbol, 'market', 'buy', None, None, {'cost': budget})
    # print(f'Placed market buy order for {budget} BUSD')
    return order

def sell(order):
    # sell the bitcoin bought in the market buy order for the specified percentage more
    sell_price = order['price'] * sell_percentage
    sell_amount = order['filled']
    sell_order = exchange.create_order(symbol, 'limit', 'sell', sell_amount, sell_price)
    return sell_order

def check_for_completed_sell_orders(sell_order):
    # check if the limit sell order has been completed every 5 seconds
    timer = 5
    while True:
        order = exchange.fetch_order(sell_order['id'], symbol)  # pass the symbol argument
        if order['status'] == 'closed':
            log_trade(order)  # log completed limit order
            break
        if timer < 60:
            timer += 1
        time.sleep(timer)

while True:
    # check the available balance of BUSD in the account
    balance = exchange.fetch_balance()
    available_busd = balance['BUSD']['free']

    if available_busd < budget:
        print(f'Not enough BUSD in the account. Available balance: {available_busd} BUSD')
    else:
        # buy $11 worth of bitcoin
        initial_buy_order = buy(budget)
        log_trade(initial_buy_order)  # log completed market trade

        # sell the bitcoin bought in the market buy order for 0.01% more
        sell_order = sell(initial_buy_order)
        log_trade(sell_order)  # log open limit order

        # create a separate thread for checking for completed limit sell orders
        thread = threading.Thread(target=check_for_completed_sell_orders, args=(sell_order,))
        thread.start()

    # wait
    time.sleep(wait_time)
