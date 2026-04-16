"""
Central configuration loaded from environment variables.

This module loads a dotenv file (default: ".env"). You can override which file
gets loaded by setting ENV_FILE, e.g.:

    ENV_FILE=.env.o python bot.py
"""

import os
from typing import Optional

import ccxt
from dotenv import load_dotenv

from exchange import ExtendedSymbolExchange

def _require(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable {name!r}. ")
    return value


def _get_int(name: str, *, default: Optional[int] = None) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        if default is None:
            raise RuntimeError(f"Missing required environment variable {name!r}. ")
        return default
    return int(value)


def _get_float(name: str, *, default: Optional[float] = None) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        if default is None:
            raise RuntimeError(f"Missing required environment variable {name!r}. ")
        return default
    return float(value)


def _optional(name: str) -> Optional[str]:
    value = os.getenv(name)
    return value if value not in (None, "") else None


load_dotenv()

# Credentials (required)
API_KEY: str = _optional("API_KEY")
API_SECRET: str = _optional("API_SECRET")

# MEXC (optional; used by test_mexc and other MEXC tooling)
ACCESS_KEY: str = _optional("ACCESS_KEY")
SECRET_KEY: str = _optional("SECRET_KEY")

# Trading parameters (required by bot.py)
SYMBOL: str = _require("SYMBOL")
SLEEP_MIN: int = _get_float("SLEEP_MIN")
SLEEP_MAX: int = _get_float("SLEEP_MAX")
BUY_CANCEL_TIMEOUT: float = _get_float("BUY_CANCEL_TIMEOUT")
PROFIT_MARGIN_MIN: float = _get_float("PROFIT_MARGIN_MIN")
PROFIT_MARGIN_MAX: float = _get_float("PROFIT_MARGIN_MAX")

EXCHANGE_CONFIGS = {
    "binance": {
        "apiKey": API_KEY,
        "secret": API_SECRET,
    },
    "mexc": {
        "apiKey": ACCESS_KEY,
        "secret": SECRET_KEY,
    },
}

exchange = ExtendedSymbolExchange(symbol=SYMBOL, config=EXCHANGE_CONFIGS["binance"])
