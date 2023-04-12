import os
import pprint

from dotenv import load_dotenv

from exchange import ExtendedSymbolExchange

############################################

pprint.PrettyPrinter(indent=4)
pp = pprint.pprint

# load the .env file
load_dotenv(".env.o")

symbol = os.getenv("SYMBOL")

############################################

exchange = ExtendedSymbolExchange(symbol=symbol, config={
    "apiKey": os.getenv("API_KEY"),
    "secret": os.getenv("API_SECRET")
})

min_cost = exchange.min_cost
min_amount = exchange.min_amount
min_price = exchange.min_price
free_busd, total_busd = exchange.quote_balance()
free_balance_ratio = exchange.scale_by_balance(1, 0)

############################################


def can_n_orders_fit_in_range(n, amount, min_price, max_price):
    spread = max_price - min_price
    spread_per_order = spread / (n - 1)

    price = min_price
    for _ in range(n):
        amount -= exchange.min_order_amount(price)
        price += spread_per_order

    if amount >= 0:
        return True
    return False


def how_many_orders_can_fit_in_spread_given_amount(amount, min_price, max_price):
    n = 2
    while can_n_orders_fit_in_range(n, amount, min_price, max_price):
        n += 1
    return n - 1


def print_orders(orders):

    len_orders = len(orders)
    
    sum_amount = sum([order["amount"] for order in orders])
    sum_amount = exchange.round(sum_amount, "amount")
    
    sum_total = sum([order["price"] * order["amount"] for order in orders])
    sum_total = exchange.round(sum_total, "quote")

    prices = [order['price'] for order in orders]

    min_price = exchange.round(min(prices), "price")
    max_price = exchange.round(max(prices), "price")

    print(
        f"Number of sell orders: {len_orders} | Sum amount: {sum_amount} | Sum total: {sum_total} | Min price: {min_price} | Max price: {max_price}"
    )
    
    return sum_amount, sum_total, min_price, max_price

############################################


def get_new_orders(n, sum_amount, min_price, max_price, set_amount=None):
    spread = max_price - min_price
    spread_per_order = spread / (n - 1)

    new_orders = []

    price = max_price
    for _ in range(n):

        amount = exchange.min_order_amount(price) if set_amount is None else set_amount

        new_orders.append({
            "price": exchange.round(price + exchange.min_price, "price"),
            "amount": exchange.round(amount, "amount")
        })

        price -= spread_per_order
        price = exchange.round(price, "price")
        sum_amount -= amount
        sum_amount = exchange.round(sum_amount, "amount")

    # add the remaining amount to the first order
    new_orders[0]["amount"] += sum_amount

    return new_orders


def replace_orders(orders, orders_new):
    sum_amount = exchange.round(sum([order["amount"] for order in orders]), "amount")
    # sum_amount = exchange.round(sum_amount, "amount")
    
    sum_amount_new = exchange.round(sum([order["amount"] for order in orders_new]), "amount")
    # sum_amount_new = exchange.round(sum_amount_new, "amount")

    print(f"Are sum_amount and sum_amount_new equal? {sum_amount} {sum_amount_new}")
    assert sum_amount == sum_amount_new, f"Sum amount must be equal | {sum_amount} != {sum_amount_new}"

    sum_value = sum([order["price"] * order["amount"] for order in orders])
    sum_value_new = sum([order["price"] * order["amount"] for order in orders_new])

    assert sum_value_new >= sum_value, f"Sum value must be greater or equal | {sum_value_new} < {sum_value}"

    # cancel current orders
    for order in orders:
        exchange.cancel_order(order["id"], symbol=symbol)

    # create new orders
    for order in orders_new:

        exchange.create_order(
            symbol=symbol, type="limit", side="sell", amount=order["amount"], price=order["price"]
        )

############################################


print("CURRENT SELL ORDERS")
orders = exchange.open_sell_orders()
sum_amount, sum_total, min_price, max_price = print_orders(orders)
n = how_many_orders_can_fit_in_spread_given_amount(sum_amount, min_price, max_price)

max_num_orders = exchange.get_max_num_orders()

if n > max_num_orders:

    print(f"Number of orders {n} is greater than max number of orders {max_num_orders} \n")

    n = int(max_num_orders * 0.8)
    set_amount = exchange.round(sum_amount / n, "amount")

    print("POTENTIAL NEW SELL ORDERS")
    new_orders = get_new_orders(n, sum_amount, min_price, max_price, set_amount=set_amount)
    _, new_sum_total, _, _ = print_orders(new_orders)

else:

    print("Number of orders is less than max number of orders \n")

    print("POTENTIAL NEW SELL ORDERS")
    new_orders = get_new_orders(n, sum_amount, min_price, max_price)
    _, new_sum_total, _, _ = print_orders(new_orders)

if sum_total > new_sum_total:
    multiplier = sum_total / new_sum_total
    for order in new_orders:
        order["price"] = exchange.round(order["price"] * multiplier + exchange.min_price, "price")

    print("POTENTIAL NEW MULTIPLIED SELL ORDERS")
    _, _, _, _ = print_orders(new_orders)

replace_orders(orders, new_orders)

print("NEW SELL ORDERS")
orders = exchange.open_sell_orders()
_, _, _, _ = print_orders(orders)
