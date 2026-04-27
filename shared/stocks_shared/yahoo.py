"""Yahoo Finance helpers: live prices, option chains, and historical OHLC."""

import re

_price_cache: dict[str, float | None] = {}
_chain_cache: dict[tuple[str, str], object] = {}


def fetch_live_price(ticker: str) -> float | None:
    """Return the last trade or regular market price for ticker."""
    if ticker in _price_cache:
        return _price_cache[ticker]
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).fast_info
        price = info.get("lastPrice") or info.get("regularMarketPrice")
    except Exception:
        price = None
    _price_cache[ticker] = price
    return price


def fetch_option_chain(ticker: str, exp_yf: str):
    """Return the option chain for ticker at expiration exp_yf (YYYY-MM-DD), cached."""
    key = (ticker, exp_yf)
    if key in _chain_cache:
        return _chain_cache[key]
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        chain = t.option_chain(exp_yf) if exp_yf in t.options else None
    except Exception:
        chain = None
    _chain_cache[key] = chain
    return chain


def fetch_option_market_value(ticker: str, opt_type: str, expiration_str: str,
                              strike, contracts: int) -> float | None:
    """Return total market value as a negative number (short position = liability)."""
    try:
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})", expiration_str or "")
        if not m:
            return None
        exp_yf = f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
        chain = fetch_option_chain(ticker, exp_yf)
        if chain is None:
            return None
        df = chain.calls if opt_type == "Call" else chain.puts
        row = df[df["strike"] == float(strike)]
        if row.empty:
            return None
        bid, ask, last = row["bid"].iloc[0], row["ask"].iloc[0], row["lastPrice"].iloc[0]
        price = (bid + ask) / 2 if bid > 0 and ask > 0 else last
        return round(-price * contracts * 100, 2)
    except Exception:
        return None


def fetch_history(ticker: str, start: str | None = None, end: str | None = None):
    """Fetch historical daily close prices as a pandas DataFrame.

    Returns DataFrame with DatetimeIndex and 'Close' column.
    start/end: 'YYYY-MM-DD' strings (passed directly to yfinance).
    """
    import pandas as pd
    import yfinance as yf

    df = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)
    if df.empty:
        return pd.DataFrame(columns=["Close"])
    return df[["Close"]].copy()
