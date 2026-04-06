"""
MEXC smoke test: ticker, market limits, post-only limit buy one tick above best bid.
"""

import math

import ccxt

from config import EXCHANGE_CONFIGS


def _ceil_to_step(x: float, step: float) -> float:
    if step <= 0:
        return x
    return math.ceil(x / step - 1e-12) * step


def main() -> None:

    exchange = ccxt.mexc(EXCHANGE_CONFIGS["mexc"])
    symbol = 'MYST/USDT'


    
    # symbol = "BNB/USDC"
    # exchange = ccxt.binance(CCXT_CONFIG)

    
    try:
        exchange.load_markets()
        market = exchange.market(symbol)

        lim = market["limits"]
        prec = market["precision"]
        min_amount = lim["amount"]["min"]
        min_cost = lim["cost"]["min"]
        price_min = lim["price"]["min"]
        price_max = lim["price"]["max"]
        amount_step = prec["amount"]
        price_step = prec["price"]

        print(
            "Market limits / precision:\n"
            f"  min base amount: {min_amount}\n"
            f"  min order value (cost): {min_cost}\n"
            f"  price min / max: {price_min} / {price_max}\n"
            f"  amount step: {amount_step}\n"
            f"  price step: {price_step}"
        )

        ticker = exchange.fetch_ticker(symbol)
        print(
            f"\n{symbol} ticker last={ticker.get('last')} "
            f"bid={ticker.get('bid')} ask={ticker.get('ask')}"
        )

        ob = exchange.fetch_order_book(symbol, limit=5)
        if not ob["bids"]:
            raise SystemExit("Order book has no bids; cannot anchor price.")

        best_bid = ob["bids"][0][0]
        best_ask = ob["asks"][0][0] if ob["asks"] else None
        raw_price = best_bid + float(price_step)
        buy_price = float(exchange.price_to_precision(symbol, raw_price))

        if best_ask is not None and buy_price >= best_ask:
            raise SystemExit(
                f"Best bid + tick ({buy_price}) would cross or touch best ask ({best_ask}); "
                "refusing post-only buy."
            )

        need_base_for_cost = min_cost / buy_price if buy_price else 0.0
        order_amount_raw = max(min_amount, need_base_for_cost)
        order_amount = _ceil_to_step(order_amount_raw, float(amount_step))
        order_amount = float(exchange.amount_to_precision(symbol, order_amount))

        notional = order_amount * buy_price
        if notional + 1e-9 < min_cost:
            raise SystemExit(
                f"Computed amount {order_amount} @ {buy_price} => notional {notional} < min cost {min_cost}"
            )

        print(
            f"\nOrder book best bid={best_bid} best_ask={best_ask}\n"
            f"Post-only limit buy: amount={order_amount} price={buy_price} (notional ~{notional:.4f})"
        )

        order = exchange.create_order(
            symbol,
            "limit",
            "buy",
            order_amount,
            buy_price + price_step,
            {"postOnly": True},
        )
        print(f"Placed order {order}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        close = getattr(exchange, "close", None)
        if callable(close):
            close()


if __name__ == "__main__":
    main()
