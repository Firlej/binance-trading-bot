

import time
import os
import threading
import signal
import random

from dotenv import load_dotenv
import ccxt


from utils import log_order

from config import exchange

price = exchange.price()
amount = exchange.min_order_amount(price)

symbol = exchange.s

# place a market buy order for the min amount
order = exchange.create_order(
    symbol=symbol, type="market", side="buy", amount=amount
)

log_order(order)

# sell_price = order["price"] + exchange.min_price
sell_price = order["price"] * 1.003
sell_amount = order["filled"]

sell_order = exchange.create_order(
    symbol=symbol,
    type="limit",
    side="sell",
    amount=sell_amount,
    price=sell_price
)

log_order(sell_order)