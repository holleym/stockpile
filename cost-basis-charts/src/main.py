#!/usr/bin/env python3
"""Generate cost basis vs. price charts for all symbols in a brokerage CSV."""

import argparse
import logging
import sys
from pathlib import Path

from stocks_shared.yahoo import fetch_history
import config
from cost_basis import compute_cost_basis_series
from charts import create_cost_basis_chart

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)


def _get_parser(brokerage: str):
    b = brokerage.lower()
    if b == "schwab":
        from stocks_shared.parsers.schwab import parse_all_transactions
    elif b == "robinhood":
        from stocks_shared.parsers.robinhood import parse_all_transactions
    else:
        sys.exit(f"Unknown brokerage '{brokerage}'. Supported: schwab, robinhood")
    return parse_all_transactions


def main():
    parser = argparse.ArgumentParser(description="Generate cost basis charts from a brokerage CSV")
    parser.add_argument("--csv", metavar="FILE", help="Override the CSV path from config.toml")
    parser.add_argument("--brokerage", metavar="NAME", choices=["schwab", "robinhood"],
                        help="Only run accounts for this brokerage")
    parser.add_argument("--symbol", metavar="TICKER",
                        help="Chart only this symbol (overrides config.toml symbols list)")
    parser.add_argument("--output-dir", metavar="DIR", help="Override output directory from config.toml")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else config.OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    accounts = config.get_all_accounts(brokerage_filter=args.brokerage)
    if not accounts:
        sys.exit("No accounts configured. Copy config.toml.example to config.toml and fill it in.")

    for acct in accounts:
        csv_path = args.csv or acct.csv
        if not csv_path:
            log.warning("No CSV path for %s account, skipping.", acct.brokerage)
            continue

        log.info("Parsing %s (%s)...", csv_path, acct.brokerage)
        parse_all = _get_parser(acct.brokerage)
        ticker_transactions, _ = parse_all(csv_path)

        # Priority: --symbol CLI arg > config symbols list > all symbols in CSV
        if args.symbol:
            symbols = [args.symbol]
        elif acct.symbols:
            symbols = acct.symbols
        else:
            symbols = sorted(ticker_transactions)

        for symbol in symbols:
            txns = ticker_transactions.get(symbol)
            if not txns:
                log.warning("No transactions found for %s", symbol)
                continue

            log.info("Processing %s (%d transactions)...", symbol, len(txns))
            series = compute_cost_basis_series(txns)
            if not series:
                log.info("  No stock transactions for %s, skipping.", symbol)
                continue

            start_date = series[0]["date"].strftime("%Y-%m-%d")
            log.info("  Fetching Yahoo Finance history from %s...", start_date)
            price_history = fetch_history(symbol, start=start_date)
            if price_history.empty:
                log.warning("  No price data from Yahoo Finance for %s, skipping.", symbol)
                continue

            output_path = output_dir / f"{symbol}_cost_basis.html"
            create_cost_basis_chart(symbol, price_history, series, str(output_path))

    log.info("Done.")


if __name__ == "__main__":
    main()
