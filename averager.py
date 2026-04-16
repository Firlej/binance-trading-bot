import os
import pprint
from decimal import ROUND_FLOOR, ROUND_CEILING

import numpy as np

from exchange import ExtendedSymbolExchange
from utils import (
    amount_to_units,
    calculate_min_order_amount,
    how_many_orders_can_fit_in_spread_given_amount,
    round_units,
    units_to_amount,
)

############################################

pprint.PrettyPrinter(indent=4)
pp = pprint.pprint

############################################


def print_orders(exchange: ExtendedSymbolExchange, orders):

    len_orders = len(orders)
    
    sum_amount = sum([order["amount"] for order in orders])
    sum_amount = exchange.round(sum_amount, "amount")
    
    sum_total = sum([order["price"] * order["amount"] for order in orders])
    sum_total = exchange.round(sum_total, "quote")

    prices = [order['price'] for order in orders]
    if len(prices) == 0:
        prices = [0]
    
    min_price = exchange.round(min(prices), "price")
    max_price = exchange.round(max(prices), "price")

    print(
        f"Number of sell orders: {len_orders} | Sum amount: {sum_amount} | Sum total: {sum_total} | Min price: {min_price} | Max price: {max_price}"
    )
    
    return sum_amount, sum_total, min_price, max_price

############################################


def get_new_orders(exchange: ExtendedSymbolExchange, n, sum_amount, min_price, max_price, set_amount=None):
    
    prices = np.linspace(min_price, max_price, num=n)
    prices = [exchange.round(p, "price") for p in prices]
    
    min_amount_step = exchange.min_amount
    total_units = amount_to_units(min_amount_step, exchange.round(sum_amount, "amount"))

    min_units_per_order = []
    for p in prices:
        min_amt = calculate_min_order_amount(p, exchange.min_cost, exchange.min_price, exchange.min_amount)
        min_units = round_units(min_amount_step, min_amt, ROUND_CEILING)
        min_units_per_order.append(min_units)

    sum_min_units = sum(min_units_per_order)
    if sum_min_units > total_units:
        raise AssertionError(
            f"Cannot rebalance: total amount {sum_amount} ({total_units} units) is less than "
            f"sum of per-order minimums ({sum_min_units} units)"
        )

    orders = [{"price": exchange.round(p + exchange.min_price, "price"), "amount": 0.0} for p in prices]

    if set_amount is None:
        units = list(min_units_per_order)
        remaining = total_units - sum_min_units
        units[0] += remaining
    else:
        target_units = round_units(min_amount_step, set_amount, ROUND_FLOOR)
        units = [max(mu, target_units) for mu in min_units_per_order]
        remaining = total_units - sum(units)
        if remaining < 0:
            # Caller should lower set_amount; we fail loudly so rebalance can adjust deterministically.
            raise AssertionError(
                f"set_amount too high: target {set_amount} => {target_units} units results in "
                f"sum(units)={sum(units)} > total_units={total_units}"
            )
        units[0] += remaining

    for o, u in zip(orders, units):
        o["amount"] = exchange.round(units_to_amount(min_amount_step, u), "amount")
        assert amount_to_units(min_amount_step, o["amount"]) == u
        assert o["amount"] * o["price"] >= exchange.min_cost

    assert sum(amount_to_units(min_amount_step, o["amount"]) for o in orders) == total_units
    return orders


def replace_orders(exchange: ExtendedSymbolExchange, orders, orders_new):
    sum_amount = exchange.round(sum([order["amount"] for order in orders]), "amount")
    sum_amount_new = exchange.round(sum([order["amount"] for order in orders_new]), "amount")

    print(f"Are sum_amount and sum_amount_new equal? {sum_amount} {sum_amount_new}")
    min_amount_step = exchange.min_amount
    assert amount_to_units(min_amount_step, sum_amount) == amount_to_units(min_amount_step, sum_amount_new), (
        f"Sum amount must be exactly equal | {sum_amount} != {sum_amount_new}"
    )

    sum_value = sum([order["price"] * order["amount"] for order in orders])
    sum_value_new = sum([order["price"] * order["amount"] for order in orders_new])

    assert sum_value_new >= sum_value, f"Sum value must be greater or equal | {sum_value_new} < {sum_value}"

    # cancel current orders
    for order in orders:
        exchange.cancel_order(order["id"], symbol=exchange.s)

    # create new orders
    for order in orders_new:
        
        print(f"{exchange.s} limit sell {order['amount']} {order['price']} ")

        exchange.create_order(
            symbol=exchange.s, type="limit", side="sell", amount=order["amount"], price=order["price"],
            rebalance_on_max_orders=False
        )

############################################


def rebalance_sell_orders(exchange_instance=None):
    """
    Rebalance sell orders by redistributing them evenly across the price spread.
    
    Args:
        exchange_instance: An instance of ExtendedSymbolExchange (optional, uses global if not provided)
        
    Returns:
        tuple: (old_orders, new_orders) - the orders before and after rebalancing
    """
    if exchange_instance is None:
        raise ValueError("rebalance_sell_orders(exchange_instance) requires an exchange instance")
    exchange = exchange_instance
    
    print("CURRENT SELL ORDERS")
    orders = exchange.open_sell_orders()
    sum_amount, sum_total, min_price, max_price = print_orders(exchange, orders)
    n = how_many_orders_can_fit_in_spread_given_amount(
        sum_amount,
        min_price,
        max_price,
        exchange.min_cost,
        exchange.min_price,
        exchange.min_amount,
    )
    # n = min(len(orders), n)

    max_num_orders = exchange.get_max_num_orders()

    if n > max_num_orders:

        print(f"Number of orders {n} is greater than max number of orders {max_num_orders} \n")

        n = int(max_num_orders * 0.8)
        
        set_amount = exchange.round(sum_amount / n, "amount")

        print("POTENTIAL NEW SELL ORDERS")
        while True:
            try:
                new_orders = get_new_orders(exchange, n, sum_amount, min_price, max_price, set_amount=set_amount)
                break
            except AssertionError:
                set_amount = exchange.round(set_amount - exchange.min_amount, "amount")
                if set_amount <= 0:
                    raise
        
        
        sum_amount = exchange.round(sum([order["amount"] for order in orders]), "amount")
        sum_amount_new = exchange.round(sum([order["amount"] for order in new_orders]), "amount")
        assert amount_to_units(exchange.min_amount, sum_amount) == amount_to_units(exchange.min_amount, sum_amount_new)
        _, new_sum_total, _, _ = print_orders(exchange, new_orders)

    else:

        print("Number of orders is less than max number of orders \n")
        
        # Still ensure we don't exceed 80% of max to leave room for new orders
        safe_limit = int(max_num_orders * 0.8)
        if n > safe_limit:
            print(f"Limiting orders to safe threshold: {n} -> {safe_limit}")
            n = safe_limit
            set_amount = exchange.round(sum_amount / n, "amount")
            while True:
                try:
                    new_orders = get_new_orders(exchange, n, sum_amount, min_price, max_price, set_amount=set_amount)
                    break
                except AssertionError:
                    set_amount = exchange.round(set_amount - exchange.min_amount, "amount")
                    if set_amount <= 0:
                        raise
        else:
            new_orders = get_new_orders(exchange, n, sum_amount, min_price, max_price)

        print("POTENTIAL NEW SELL ORDERS")
        _, new_sum_total, _, _ = print_orders(exchange, new_orders)

    if sum_total > new_sum_total:
        multiplier = sum_total / new_sum_total
        for order in new_orders:
            order["price"] = exchange.round(order["price"] * multiplier + exchange.min_price, "price")

        print("POTENTIAL NEW MULTIPLIED SELL ORDERS")
        _, _, _, _ = print_orders(exchange, new_orders)

    replace_orders(exchange, orders, new_orders)

    print("NEW SELL ORDERS")
    orders_after = exchange.open_sell_orders()
    _, _, _, _ = print_orders(exchange, orders_after)
    
    return orders, orders_after


if __name__ == "__main__":
    from config import exchange

    rebalance_sell_orders(exchange)
