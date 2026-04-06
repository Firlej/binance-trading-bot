"""
Pure and shared utility helpers (no I/O, no exchange state).
"""

import math
from decimal import Decimal


def amount_scale_from_step(step: float) -> int:
    """
    Number of decimal places implied by an exchange amount step (e.g. min lot size).

    Treats ``step`` as a decimal string so floats like ``0.001`` map to scale 3.
    For integer steps, returns 0.
    """
    step_d = Decimal(str(step))
    exp = step_d.as_tuple().exponent
    return -exp if exp < 0 else 0


def amount_to_units(min_amount: float, amount: float) -> int:
    """
    Convert a base ``amount`` to integer units where one unit is ``min_amount``.

    Raises ``ValueError`` if ``amount`` is not an exact multiple of the step
    implied by ``min_amount``.
    """
    scale = amount_scale_from_step(min_amount)
    unit = Decimal(10) ** scale
    amount_d = Decimal(str(amount))
    units = amount_d * unit
    if units != units.to_integral_value():
        raise ValueError(f"Amount {amount} is not a multiple of min_amount {min_amount}")
    return int(units)


def units_to_amount(min_amount: float, units: int) -> float:
    """
    Convert integer units (see ``amount_to_units``) back to a base float amount.
    """
    scale = amount_scale_from_step(min_amount)
    unit = Decimal(10) ** scale
    return float(Decimal(units) / unit)


def round_units(min_amount: float, amount: float, rounding) -> int:
    """
    Convert ``amount`` to units using ``min_amount``'s step, rounding with the
    given ``decimal`` module rounding mode (e.g. ``ROUND_FLOOR``, ``ROUND_CEILING``).
    """
    scale = amount_scale_from_step(min_amount)
    unit = Decimal(10) ** scale
    amount_d = Decimal(str(amount))
    units = (amount_d * unit).to_integral_value(rounding=rounding)
    return int(units)


def calculate_min_order_amount(price: float, min_cost: float, min_price: float, min_amount: float) -> float:
    """
    Minimum base amount for one order given exchange limits (cost floor, price tick, amount step).
    """
    effective_min_cost = min_cost + min_price
    return math.ceil(effective_min_cost / price / min_amount) * min_amount


def map_range(x, a, b, y, z):
    """
    Map a value from one range to another.
    """
    return (x - a) * (z - y) / (b - a) + y


def log_error(e, name):
    """
    Print a formatted error message to the console.
    """
    module = e.__module__ if hasattr(e, "__module__") else ""
    print(f'''
    Error in {name}:
    {e.__class__=}
    {module=}
    {e.args=}
    {e.__context__=}
    Error occured in {e.__traceback__.tb_frame.f_code.co_filename} at line {e.__traceback__.tb_lineno}
    ''')


def log_order(o, o_prev=None):
    """
    Log an order to the console.
    """
    amount = o["amount"] if o["amount"] else o["filled"]
    value = o["price"] * o["amount"]

    profit = "X"
    if o_prev is not None:
        value_prev = o_prev["price"] * o_prev["amount"]
        profit = value - value_prev

    print(
        f'{o["datetime"]} | {o["id"]} | {o["type"].upper():<6} | {o["side"].upper():<4} | {amount:<7} | {o["price"]:<8} | {value:<18} | {o["status"]:<6} | Profit: {profit:<18}'
    )


def can_n_orders_fit_in_range(n, amount, spread_min_price, spread_max_price, min_cost, min_price_tick, min_amount):
    """
    Whether `amount` base can cover `n` orders at prices linearly spaced between spread endpoints,
    each at least calculate_min_order_amount(...) at that price.
    """
    spread = spread_max_price - spread_min_price
    spread_per_order = spread / (n - 1)

    price = spread_min_price
    for _ in range(n):
        amount -= calculate_min_order_amount(price, min_cost, min_price_tick, min_amount)
        price += spread_per_order

    return amount >= 0


def how_many_orders_can_fit_in_spread_given_amount(amount, spread_min_price, spread_max_price, min_cost, min_price_tick, min_amount):
    """
    Largest n such that can_n_orders_fit_in_range(n, ...) is True (search from n=2 upward).
    """
    n = 2
    while can_n_orders_fit_in_range(n, amount, spread_min_price, spread_max_price, min_cost, min_price_tick, min_amount):
        n += 1
    return n - 1
