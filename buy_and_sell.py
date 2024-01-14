

import time
import os
import threading
import signal
import random

from dotenv import load_dotenv
import ccxt


from helpers import log_order
from exchange import ExtendedSymbolExchange

# load the .env file
load_dotenv('.env.o')

symbol = os.getenv("SYMBOL")

exchange = ExtendedSymbolExchange(symbol=symbol, config={
    "apiKey": os.getenv("API_KEY"),
    "secret": os.getenv("API_SECRET")
})

price = exchange.price()
amount = exchange.min_order_amount(price)

# place a market buy order for the min amount
order = exchange.create_order(
    symbol=symbol, type="market", side="buy", amount=amount
)

log_order(order)

sell_price = order["price"] + exchange.min_price
sell_amount = order["filled"]

sell_order = exchange.create_order(
    symbol=symbol,
    type="limit",
    side="sell",
    amount=sell_amount,
    price=sell_price
)

log_order(sell_order)