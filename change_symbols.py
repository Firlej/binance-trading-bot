
import os
import pprint

from dotenv import load_dotenv

import ccxt

############################################

pprint.PrettyPrinter(indent=4)
pp = pprint.pprint

# load the .env file
load_dotenv(".env.max")

symbol_old = 'BTC/TUSD'
symbol_new = 'BTC/FDUSD'

############################################

exchange = ccxt.binance({
    "apiKey": os.getenv("API_KEY"),
    "secret": os.getenv("API_SECRET")
})

open_orders_old = exchange.fetch_open_orders(symbol_old)

for o in open_orders_old:

	id = o["id"]
	amount = o["amount"]
	price = o["price"]

	exchange.cancel_order(
		id=id, symbol=symbol_old
	)

	exchange.create_order(
		symbol=symbol_new, type="limit", side="sell", amount=amount, price=price
	)

	print(f"Replaced {id=} {amount=} at {price=}")
	

open_orders_new = exchange.fetch_open_orders(symbol_new)

def print_orders_stats(orders):
	
	amounts = [o["amount"] for o in orders]
	prices = [o["price"] for o in orders]

	# Min and Max price
	min_price = min(prices)
	max_price = max(prices)

	# Sum of amount
	sum_amount = sum(amounts)

	# Weighted average price
	weighted_average_price = sum(price*amount for price, amount in zip(prices, amounts)) / sum_amount

	print(f"{min_price=}\n{max_price=}\n{sum_amount=}\n{weighted_average_price=}")


print("Old orders: ", symbol_old)
print_orders_stats(open_orders_old)
print("New orders: ", symbol_new)
print_orders_stats(open_orders_new)