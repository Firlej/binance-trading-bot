# Modified code to handle KeyboardInterrupt gracefully and close the exchange connection.

import time
import os
import math
import ccxt.pro
from typing import List
from ccxt.base.types import OrderBook, Ticker, Balances, Order
import asyncio
from dotenv import load_dotenv

from helpers import log_order, log_error

# load the .env file
load_dotenv('.env.o')

symbol = os.getenv("SYMBOL")

exchange = ccxt.pro.binance({
    "apiKey": os.getenv("API_KEY"),
    "secret": os.getenv("API_SECRET")
})

def process_orders_update(orders: List[Order]):
    def process_order_update(order: Order):
        print(order)

    for order in orders:
        process_order_update(order)
        break

def common_handler(
        orderbook: OrderBook = None,
        ticker: Ticker = None,
        balances: Balances = None,
        orders: List[Order] = None
    ):

    # https://docs.ccxt.com/#/ccxt.pro.manual

    if orderbook:
        print(f"OrderBook: ask: {orderbook['asks'][0]}, bid: {orderbook['bids'][0]}")
    
    if ticker:
        print(f"Ticker: {ticker['datetime']}, last_price: {ticker['last']}")
    
    if balances:
        print(f"{balances['balance']=}")
    
    if orders:
        process_orders_update(orders)
        for order in orders:
            log_order(order)

async def watch_order_book():
    try:
        while True:
            orderbook = await exchange.watch_order_book(symbol)
            common_handler(orderbook=orderbook)
    except Exception as e:
        print(type(e).__name__, str(e))

async def watch_ticker():
    try:
        while True:
            ticker = await exchange.watch_ticker(symbol)
            common_handler(ticker=ticker)
    except Exception as e:
        print(type(e).__name__, str(e))

async def watch_balance():
    try:
        while True:
            balances = await exchange.watch_balance()
            common_handler(balances=balances)
    except Exception as e:
        print(type(e).__name__, str(e))

async def watch_orders():
    try:
        while True:
            orders = await exchange.watch_orders(symbol=symbol)
            common_handler(orders=orders)
    except Exception as e:
        print(type(e).__name__, str(e))

async def market_buy():
    def min_order_amount(self, price=None):
        """
        Get the minimum amount of the base currency that can be traded in one order.
        """
        price = exchange.fetch_ticker(self.s)['last']
        min_cost = self.min_cost + self.min_price
        return math.ceil(min_cost / price / self.min_amount) * self.min_amount
    
    amount = min_order_amount()

    order = await exchange.create_order(
        symbol=symbol, type="market", side="buy", amount=amount
    )

    return order

async def main():
    await exchange.load_markets()

    try:
        loops = [
            watch_order_book(),
            watch_balance(),
            watch_orders(),
            watch_ticker()
        ]
        await asyncio.gather(*loops)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(type(e).__name__, str(e))
    finally:
        await exchange.close()

asyncio.run(main())
