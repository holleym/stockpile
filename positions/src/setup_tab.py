#!/usr/bin/env python3
"""
setup_tab.py — Build Position Tracker tabs from a brokerage all-transactions CSV.

Usage:
    python3 setup_tab.py ALL_TRANS.csv Schwab

The script clears the spreadsheet, then creates a tab per ticker plus Summary
tabs and an Other Transactions tab. Live prices are fetched from Yahoo Finance.

Requirements:
    pip install google-auth google-auth-oauthlib google-api-python-client yfinance
"""

import re
import sys
import traceback
from datetime import datetime
from pathlib import Path

import config
import sheets
from stocks_shared.analysis import (
    compute_avg_held_anchor,
    compute_closed_avg_days,
    compute_status,
    detect_open_positions,
)
from layout import TXN_ROW, build_sections


# ── Yahoo Finance ─────────────────────────────────────────────────────────────
from stocks_shared.yahoo import (
    fetch_live_price as fetch_yahoo_price,
    fetch_option_market_value,
)


# ── Ticker processing ─────────────────────────────────────────────────────────

def process_ticker(ticker, transactions, brokerage, service,
                   current_price=None, current_call_value=None, current_put_value=None):
    """Build/update a single ticker tab and its Summary row."""
    tab_name = f"{ticker}-{brokerage}"
    open_positions = detect_open_positions(transactions)
    status, issues = compute_status(transactions, open_positions)

    print(f"  Ticker: {ticker}  |  Status: {status}  |  Transactions: {len(transactions)}")
    for issue in issues:
        print(f"    ! {issue}")

    if status == "Inconsistent":
        print("  Skipping tab — recording in Summary as Inconsistent.")
        sheets._write_summary_row(service, tab_name, status, issues)
        return

    if current_price is None:
        current_price = fetch_yahoo_price(ticker)
        if current_price is not None:
            print(f"  Fetched price from Yahoo Finance: {current_price}")

    open_calls = [p for p in open_positions if p["type"] == "Call"]
    open_puts  = [p for p in open_positions if p["type"] == "Put"]

    if current_call_value is None and open_calls:
        total = sum(
            v for p in open_calls
            for v in [fetch_option_market_value(ticker, "Call", p["expiration"], p["strike"], p["contracts"])]
            if v is not None
        )
        if total != 0:
            current_call_value = round(total, 2)
            print(f"  Fetched call market value from Yahoo: {current_call_value}")

    if current_put_value is None and open_puts:
        total = sum(
            v for p in open_puts
            for v in [fetch_option_market_value(ticker, "Put", p["expiration"], p["strike"], p["contracts"])]
            if v is not None
        )
        if total != 0:
            current_put_value = round(total, 2)
            print(f"  Fetched put market value from Yahoo: {current_put_value}")

    print(f"  Price: {current_price}  Call MV: {current_call_value}  Put MV: {current_put_value}")
    print(f"  Open positions: {len(open_positions)}")
    for p in open_positions:
        print(f"    {p['type']} {p['symbol']}  contracts={p['contracts']}  prem={p['premium']:.2f}")

    sheet_id = sheets.recreate_tab(service, tab_name)
    print(f"  Recreated tab '{tab_name}'.")

    print("  Writing layout...")
    last_row = TXN_ROW + len(transactions) - 1
    avg_held_anchor = compute_avg_held_anchor(transactions)
    if avg_held_anchor:
        print(f"  FIFO avg-held anchor: {avg_held_anchor[0]:04d}-{avg_held_anchor[1]:02d}-{avg_held_anchor[2]:02d}")
    closed_avg_days = compute_closed_avg_days(transactions) if status == "Closed" else None
    if closed_avg_days is not None:
        print(f"  Closed position avg days held: {closed_avg_days}")

    sections = build_sections(tab_name, open_positions, last_row,
                               avg_held_anchor, brokerage, status, closed_avg_days)
    sheets.batch_write(service, tab_name, sections)

    sheets.write_range(service, tab_name, "B5",
                       [[current_price if current_price is not None else ""]])
    sheets.write_range(service, tab_name, "B7:B8", [
        [current_call_value if current_call_value is not None else ""],
        [current_put_value if current_put_value is not None else ""],
    ])

    print(f"  Writing {len(transactions)} transactions...")
    chunk = 50
    for i in range(0, len(transactions), chunk):
        start_row = TXN_ROW + i
        end_row = start_row + len(transactions[i:i+chunk]) - 1
        sheets.write_range(service, tab_name, f"A{start_row}:K{end_row}", transactions[i:i+chunk])

    adj_text = (
        "** Adj Cost Basis / Share: net sum of all cash transactions (stock buys/sells, "
        "option premiums received/paid, dividends, fees) divided by current shares held. "
        "Open options contribute only their received premium since no close transaction "
        "has occurred, making this equivalent to cost basis assuming all open options "
        "expire worthless."
    )
    tv_call_text = (
        "** TV Ann Yield: annualized yield of the open call's time value relative to "
        "the close-out value of the covered shares (covered shares market value + call market value), "
        "scaled by days remaining on the contract."
    )
    tv_put_text = (
        "** TV Ann Yield: annualized yield of the open put's time value relative to "
        "the cash securing the puts (strike * 100 * contracts), "
        "scaled by days remaining on the contract."
    )
    ic_yield_text = (
        "Ann Yield on Invested Capital: Total P&L divided by total capital invested in the position "
        "(stock purchases net of sales), annualized by Avg Days Held."
    )
    cov_yield_text = (
        "Ann Yield on Close-out Value: Total P&L divided by the current close-out value "
        "(stock market value + open options market value), annualized by Avg Days Held."
    )

    if issues:
        sheets.write_range(service, tab_name, "K1", [["Data issues: " + "; ".join(issues)]])
    sheets.write_range(service, tab_name, "K6",  [[adj_text]])
    sheets.write_range(service, tab_name, "K16", [[tv_call_text]])
    sheets.write_range(service, tab_name, "K24", [[tv_put_text]])
    sheets.write_range(service, tab_name, "K28", [[ic_yield_text]])
    sheets.write_range(service, tab_name, "K29", [[cov_yield_text]])

    def footnote_merge(row0):
        return {"mergeCells": {
            "range": {"sheetId": sheet_id,
                      "startRowIndex": row0, "endRowIndex": row0 + 1,
                      "startColumnIndex": 10, "endColumnIndex": 26},
            "mergeType": "MERGE_ALL",
        }}

    def footnote_overflow(row0):
        return {"repeatCell": {
            "range": {"sheetId": sheet_id,
                      "startRowIndex": row0, "endRowIndex": row0 + 1,
                      "startColumnIndex": 10, "endColumnIndex": 26},
            "cell": {"userEnteredFormat": {"wrapStrategy": "OVERFLOW_CELL"}},
            "fields": "userEnteredFormat.wrapStrategy",
        }}

    merge_fmt = [
        footnote_merge(5), footnote_merge(15), footnote_merge(23),
        footnote_merge(27), footnote_merge(28),
        sheets.light_bg(sheet_id, 5, 0, 6, 2),
        sheets.light_bg(sheet_id, 5, 10, 6, 26),
        sheets.light_bg(sheet_id, 15, 6, 16, 8),
        sheets.light_bg(sheet_id, 15, 10, 16, 26),
        sheets.light_bg(sheet_id, 23, 6, 24, 8),
        sheets.light_bg(sheet_id, 23, 10, 24, 26),
        sheets.light_bg(sheet_id, 27, 6, 28, 8),
        sheets.light_bg(sheet_id, 27, 10, 28, 26),
        sheets.light_bg(sheet_id, 28, 6, 29, 8),
        sheets.light_bg(sheet_id, 28, 10, 29, 26),
        footnote_overflow(4), footnote_overflow(15), footnote_overflow(23),
        footnote_overflow(27), footnote_overflow(28),
    ]
    if issues:
        merge_fmt += [
            footnote_merge(0), footnote_overflow(0),
            sheets.light_bg(sheet_id, 0, 10, 1, 26),
        ]
    sheets.apply_fmt(service, sheet_id, merge_fmt)

    print("  Applying formatting...")
    fmt_requests = [
        *sheets.title_row(sheet_id),
        sheets.status_cell_fmt(sheet_id, status),
        sheets.section_header(sheet_id, 2),
        sheets.section_header(sheet_id, 9),
        sheets.section_header(sheet_id, 17),
        sheets.section_header(sheet_id, 25),
        sheets.section_header(sheet_id, TXN_ROW - 3),
        sheets.col_header(sheet_id, TXN_ROW - 2),
        sheets.yellow_bg(sheet_id, 4, 1, 5, 2),
        sheets.yellow_bg(sheet_id, 6, 1, 8, 2),
        sheets.currency(sheet_id, 4, 1, 8, 2),
        sheets.plain_number(sheet_id, 3, 4, 4, 5),
        sheets.currency(sheet_id, 4, 4, 7, 5),
        sheets.currency(sheet_id, 3, 7, 4, 8),
        sheets.percent(sheet_id, 4, 7, 5, 8),
        sheets.plain_number(sheet_id, 5, 7, 7, 8),
        sheets.percent(sheet_id, 7, 7, 8, 8),
        sheets.currency(sheet_id, 10, 1, 15, 2),
        sheets.currency(sheet_id, 10, 4, 11, 5),
        sheets.plain_number(sheet_id, 12, 4, 13, 5),
        sheets.plain_number(sheet_id, 13, 4, 14, 5),
        sheets.right_align(sheet_id, 14, 4, 15, 5),
        sheets.currency(sheet_id, 10, 7, 15, 8),
        sheets.percent(sheet_id, 15, 7, 16, 8),
        sheets.currency(sheet_id, 18, 1, 23, 2),
        sheets.currency(sheet_id, 18, 4, 19, 5),
        sheets.plain_number(sheet_id, 20, 4, 21, 5),
        sheets.plain_number(sheet_id, 21, 4, 22, 5),
        sheets.right_align(sheet_id, 22, 4, 23, 5),
        sheets.currency(sheet_id, 18, 7, 23, 8),
        sheets.percent(sheet_id, 23, 7, 24, 8),
        sheets.currency(sheet_id, 26, 1, 27, 2),
        sheets.plain_number(sheet_id, 27, 1, 28, 2),
        sheets.currency(sheet_id, 28, 1, 30, 2),
        sheets.currency(sheet_id, 26, 4, 31, 5),
        sheets.currency(sheet_id, 26, 7, 27, 8),
        sheets.percent(sheet_id, 27, 7, 29, 8),
        sheets.currency(sheet_id, TXN_ROW - 1, 7, 1000, 10),
        sheets.green_if_positive(sheet_id, 3, 7, 5, 8),
        sheets.green_if_positive(sheet_id, 7, 7, 8, 8),
        sheets.green_if_positive(sheet_id, 12, 1, 13, 2),
        sheets.green_if_positive(sheet_id, 14, 1, 15, 2),
        sheets.green_if_positive(sheet_id, 12, 7, 13, 8),
        sheets.green_if_positive(sheet_id, 20, 1, 21, 2),
        sheets.green_if_positive(sheet_id, 22, 1, 23, 2),
        sheets.green_if_positive(sheet_id, 20, 7, 21, 8),
        sheets.green_if_positive(sheet_id, 10, 1, 11, 2),
        sheets.green_if_positive(sheet_id, 18, 1, 19, 2),
        sheets.green_if_positive(sheet_id, 5, 4, 6, 5),
        sheets.green_if_positive(sheet_id, 10, 7, 11, 8),
        sheets.green_if_positive(sheet_id, 18, 7, 19, 8),
        sheets.green_if_positive(sheet_id, 26, 4, 31, 5),
        sheets.green_if_positive(sheet_id, 26, 1, 27, 2),
        sheets.green_if_positive(sheet_id, 28, 1, 30, 2),
        sheets.green_if_positive(sheet_id, 27, 7, 29, 8),
    ]
    sheets.apply_fmt(service, sheet_id, fmt_requests)

    print("  Updating Summary...")
    sheets._write_summary_row(service, tab_name, status, issues)
    print(f"  Done: '{tab_name}'")


# ── Main ──────────────────────────────────────────────────────────────────────

def _load_parser(brokerage: str):
    b = brokerage.lower()
    if b == "schwab":
        from stocks_shared.parsers.schwab import parse_all_transactions
        return parse_all_transactions
    if b == "robinhood":
        from stocks_shared.parsers.robinhood import parse_all_transactions
        return parse_all_transactions
    print(f"Error: Unknown brokerage '{brokerage}'. Supported: Schwab")
    sys.exit(1)


def _run_account(acct, csv_path: str, service):
    parse_all_transactions = _load_parser(acct.brokerage)

    sheets.configure(acct.sheet_id, config.CREDS_PATH, config.TOKEN_PATH)

    print(f"Parsing {csv_path}...")
    ticker_transactions, other_rows = parse_all_transactions(csv_path)
    tickers = sorted(ticker_transactions.keys())
    print(f"Found {len(tickers)} ticker(s): {', '.join(tickers)}")

    print("Clearing existing tabs...")
    sheets.clear_all_tabs(service)
    print("Creating summary tabs...")
    for stab in ["Summary-Open", "Summary-Closed", "Summary-Inconsistent"]:
        sheets._ensure_summary_tab(service, stab)

    for ticker in tickers:
        print(f"\n  Processing {ticker}...")
        process_ticker(ticker, ticker_transactions[ticker], acct.brokerage, service)

    if other_rows:
        print(f"\nWriting Other Transactions tab ({len(other_rows)} rows)...")
        sheets.write_other_transactions_tab(service, other_rows)

    sheets.delete_placeholder(service)
    sheets.reorder_summary_tabs_first(service)
    print("\nWriting Summary totals...")
    sheets.write_summary_totals(service, "Summary-Open")
    sheets.write_summary_totals(service, "Summary-Closed")


_LOG_PATH = Path(__file__).parent.parent / "tracker.log"


def _log(msg: str):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Build position tracker tabs from brokerage CSV exports.",
        epilog="With no arguments, runs all accounts configured in config.toml.",
    )
    parser.add_argument("--brokerage", metavar="NAME", help="Only run accounts for this brokerage (e.g. schwab).")
    parser.add_argument("--csv", dest="csv_override", metavar="FILE", help="Override the CSV file path from config.")
    args = parser.parse_args()

    _log("=== Run started ===")
    try:
        accounts = config.get_all_accounts(args.brokerage)
        if not accounts:
            desc = f"for brokerage '{args.brokerage}'" if args.brokerage else "in config.toml"
            _log(f"ERROR: No configured accounts found {desc}.")
            sys.exit(1)

        sheets.configure(accounts[0].sheet_id, config.CREDS_PATH, config.TOKEN_PATH)
        _log("Connecting to Google Sheets...")
        service = sheets.get_service()

        for acct in accounts:
            csv_path = args.csv_override or acct.csv
            if not csv_path:
                _log(f"Skipping {acct.brokerage} ({acct.sheet_id}): no CSV configured and --csv not provided.")
                continue

            _log(f"Processing: {acct.brokerage} | CSV: {csv_path}")
            _run_account(acct, csv_path, service)
            _log(f"Done: {acct.brokerage} / {acct.sheet_id}")

        _log("=== Run completed successfully ===")

    except Exception as e:
        _log(f"ERROR: {e}")
        _log(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
