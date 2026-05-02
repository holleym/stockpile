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
from layout import TXN_ROW, build_sections, build_txn_only_sections


# ── Yahoo Finance ─────────────────────────────────────────────────────────────
from stocks_shared.yahoo import (
    fetch_live_price as fetch_yahoo_price,
    fetch_option_market_value,
    fetch_history,
)


# ── Ticker processing ─────────────────────────────────────────────────────────

def _txn_display(row):
    """Return the row with qty negated for sell-side actions."""
    row = list(row)
    action = str(row[1]).strip() if len(row) > 1 else ""
    if action.startswith("Sell") and row[6] not in ("", None):
        try:
            row[6] = -abs(int(row[6]))
        except (ValueError, TypeError):
            pass
    return row


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
        print("  Creating transaction-log-only tab for inconsistent position.")
        sheet_id = sheets.recreate_tab(service, tab_name)
        ITXN = 7  # transaction data start row for inconsistent tabs
        sheets.batch_write(service, tab_name, {
            "A1:C1": [[ticker, "Status", "Inconsistent"]],
            "A3:A3": [["; ".join(issues)]],
            "A5:K5": [["TRANSACTION LOG", "", "", "", "", "", "", "", "", "", ""]],
            "A6:K6": [["Date", "Action", "Type", "Symbol", "Strike", "Expiration",
                       "Qty", "Price", "Fees", "Net Amount", "Notes"]],
        })
        chunk = 50
        for idx in range(0, len(transactions), chunk):
            start_row = ITXN + idx
            batch = [_txn_display(r) for r in transactions[idx:idx+chunk]]
            end_row = start_row + len(batch) - 1
            sheets.write_range(service, tab_name, f"A{start_row}:K{end_row}", batch)
        sheets.apply_fmt(service, sheet_id, [
            *sheets.title_row(sheet_id),
            sheets.status_cell_fmt(sheet_id, status),
            sheets.section_header(sheet_id, 4),  # row 5 — blue TXN LOG header
            sheets.col_header(sheet_id, 5),       # row 6 — light green column headers
        ])
        sheets._write_summary_row(service, tab_name, status, issues,
                                   show_calls=False, show_puts=False)
        return

    if current_price is None:
        current_price = fetch_yahoo_price(ticker)
        if current_price is not None:
            print(f"  Fetched price from Yahoo Finance: {current_price}")

    # Fetch underlying price at open_date for each open position
    for p in open_positions:
        p["price_at_open"] = None
        od = p.get("open_date")
        if od:
            try:
                import re as _re
                m = _re.match(r"(\d{2})/(\d{2})/(\d{4})", od)
                if m:
                    ymd = f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
                    from datetime import timedelta, date as _date
                    d = _date.fromisoformat(ymd)
                    end = (d + timedelta(days=4)).isoformat()  # +4 to catch weekends
                    hist = fetch_history(ticker, start=ymd, end=end)
                    if not hist.empty:
                        p["price_at_open"] = round(float(hist["Close"].iloc[0]), 2)
            except Exception:
                pass

    open_calls = [p for p in open_positions if p["type"] == "Call"]
    open_puts  = [p for p in open_positions if p["type"] == "Put"]
    show_calls = bool(open_calls) or any(row[2] == "Call" for row in transactions)
    show_puts  = bool(open_puts)  or any(row[2] == "Put"  for row in transactions)

    # Compute dynamic row positions (mirrors layout.py build_sections logic)
    _p = 19 if show_calls else 10
    _i = (_p + 9) if show_puts else (19 if show_calls else 10)
    txn_row = _i + 9

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
    last_row = txn_row + len(transactions) - 1
    avg_held_anchor = compute_avg_held_anchor(transactions)
    if avg_held_anchor:
        print(f"  FIFO avg-held anchor: {avg_held_anchor[0]:04d}-{avg_held_anchor[1]:02d}-{avg_held_anchor[2]:02d}")
    closed_avg_days = compute_closed_avg_days(transactions) if status == "Closed" else None
    if closed_avg_days is not None:
        print(f"  Closed position avg days held: {closed_avg_days}")

    sections = build_sections(tab_name, open_positions, last_row,
                               avg_held_anchor, brokerage, status, closed_avg_days,
                               show_calls=show_calls, show_puts=show_puts)
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
        start_row = txn_row + i
        batch = [_txn_display(r) for r in transactions[i:i+chunk]]
        end_row = start_row + len(batch) - 1
        sheets.write_range(service, tab_name, f"A{start_row}:K{end_row}", batch)

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

    # Aliases used in formatting below (same values as _p/_i/_txn_row computed above)
    p = _p
    i = _i

    if issues:
        sheets.write_range(service, tab_name, "K1", [["Data issues: " + "; ".join(issues)]])
    sheets.write_range(service, tab_name, "K6", [[adj_text]])
    if show_calls:
        sheets.write_range(service, tab_name, "K17", [[tv_call_text]])
    if show_puts:
        sheets.write_range(service, tab_name, f"K{p+7}", [[tv_put_text]])
    sheets.write_range(service, tab_name, f"K{i+2}", [[ic_yield_text]])
    sheets.write_range(service, tab_name, f"K{i+3}", [[cov_yield_text]])

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

    # p0, i0: 0-indexed row numbers for put/income sections
    p0 = p - 1
    i0 = i - 1

    merge_fmt = [
        footnote_merge(5),
        *([footnote_merge(16),
           sheets.light_bg(sheet_id, 16, 6, 17, 8),
           sheets.light_bg(sheet_id, 16, 10, 17, 26),
           footnote_overflow(16)] if show_calls else []),
        *([footnote_merge(p0 + 7),
           sheets.light_bg(sheet_id, p0 + 7, 6, p0 + 8, 8),
           sheets.light_bg(sheet_id, p0 + 7, 10, p0 + 8, 26),
           footnote_overflow(p0 + 7)] if show_puts else []),
        footnote_merge(i0 + 2), footnote_merge(i0 + 3),
        sheets.light_bg(sheet_id, 5, 0, 6, 2),
        sheets.light_bg(sheet_id, 5, 10, 6, 26),
        sheets.light_bg(sheet_id, i0 + 2, 6, i0 + 3, 8),
        sheets.light_bg(sheet_id, i0 + 2, 10, i0 + 3, 26),
        sheets.light_bg(sheet_id, i0 + 3, 6, i0 + 4, 8),
        sheets.light_bg(sheet_id, i0 + 3, 10, i0 + 4, 26),
        footnote_overflow(4), footnote_overflow(i0 + 2), footnote_overflow(i0 + 3),
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
        sheets.section_header(sheet_id, 2),                      # CURRENT VALUES
        sheets.section_header(sheet_id, i0),                     # INCOME/P&L/RETURNS
        sheets.section_header(sheet_id, txn_row - 3),             # TXN LOG
        sheets.col_header(sheet_id, txn_row - 2),
        sheets.yellow_bg(sheet_id, 4, 1, 5, 2),
        sheets.yellow_bg(sheet_id, 6, 1, 8, 2),
        sheets.currency(sheet_id, 4, 1, 8, 2),
        sheets.plain_number(sheet_id, 3, 4, 4, 5),
        sheets.currency(sheet_id, 4, 4, 7, 5),
        sheets.currency(sheet_id, 3, 7, 4, 8),
        sheets.percent(sheet_id, 4, 7, 5, 8),
        sheets.plain_number(sheet_id, 5, 7, 7, 8),
        sheets.percent(sheet_id, 7, 7, 8, 8),
        # Income / P&L / Returns (dynamic rows)
        sheets.currency(sheet_id, i0 + 1, 1, i0 + 2, 2),        # Total Dividends
        sheets.plain_number(sheet_id, i0 + 2, 1, i0 + 3, 2),    # Dividend Count
        sheets.currency(sheet_id, i0 + 3, 1, i0 + 5, 2),        # Net premiums
        sheets.currency(sheet_id, i0 + 1, 4, i0 + 6, 5),        # P&L data
        sheets.currency(sheet_id, i0 + 1, 7, i0 + 2, 8),        # Close-out Value
        sheets.percent(sheet_id, i0 + 2, 7, i0 + 4, 8),         # Ann Yields
        sheets.currency(sheet_id, txn_row - 1, 7, 1000, 10),
        sheets.green_if_positive(sheet_id, 3, 7, 5, 8),
        sheets.green_if_positive(sheet_id, 7, 7, 8, 8),
        sheets.green_if_positive(sheet_id, 5, 4, 6, 5),
        sheets.green_if_positive(sheet_id, i0 + 1, 4, i0 + 6, 5),  # P&L breakdown
        sheets.green_if_positive(sheet_id, i0 + 1, 1, i0 + 2, 2),  # Dividends
        sheets.green_if_positive(sheet_id, i0 + 3, 1, i0 + 5, 2),  # Net premiums
        sheets.green_if_positive(sheet_id, i0 + 2, 7, i0 + 4, 8),  # Ann Yields
    ]

    if show_calls:
        fmt_requests += [
            sheets.section_header(sheet_id, 9),                  # CALL HISTORY
            sheets.currency(sheet_id, 10, 1, 15, 2),             # Call history data
            sheets.currency(sheet_id, 10, 4, 11, 5),             # Strike
            sheets.date_fmt(sheet_id, 12, 4, 13, 5),             # Date Opened
            sheets.currency(sheet_id, 14, 4, 15, 5),             # Price at Open
            sheets.plain_number(sheet_id, 13, 4, 14, 5),         # Days Open
            sheets.plain_number(sheet_id, 15, 4, 16, 5),         # Days Left
            sheets.plain_number(sheet_id, 16, 4, 17, 5),         # Contracts
            sheets.currency(sheet_id, 10, 7, 13, 8),             # Metrics premium-P&L
            sheets.right_align(sheet_id, 13, 7, 14, 8),          # Status
            sheets.currency(sheet_id, 14, 7, 16, 8),             # Intrinsic/Time Value
            sheets.percent(sheet_id, 16, 7, 17, 8),              # TV Ann Yield
            sheets.green_if_positive(sheet_id, 12, 1, 13, 2),    # Net Call Premium
            sheets.green_if_positive(sheet_id, 14, 1, 15, 2),    # Covered Call Results
            sheets.green_if_positive(sheet_id, 10, 1, 11, 2),    # Call Premium Received
            sheets.green_if_positive(sheet_id, 10, 7, 11, 8),    # Metrics Premium Received
            sheets.green_if_positive(sheet_id, 12, 7, 13, 8),    # Unrealized P&L
        ]

    if show_puts:
        fmt_requests += [
            sheets.section_header(sheet_id, p0),                 # PUT HISTORY
            sheets.currency(sheet_id, p0 + 1, 1, p0 + 6, 2),    # Put history data
            sheets.currency(sheet_id, p0 + 1, 4, p0 + 2, 5),    # Strike
            sheets.date_fmt(sheet_id, p0 + 3, 4, p0 + 4, 5),    # Date Opened
            sheets.currency(sheet_id, p0 + 5, 4, p0 + 6, 5),    # Price at Open
            sheets.plain_number(sheet_id, p0 + 4, 4, p0 + 5, 5),# Days Open
            sheets.plain_number(sheet_id, p0 + 6, 4, p0 + 7, 5),# Days Left
            sheets.plain_number(sheet_id, p0 + 7, 4, p0 + 8, 5),# Contracts
            sheets.currency(sheet_id, p0 + 1, 7, p0 + 4, 8),    # Metrics premium-P&L
            sheets.right_align(sheet_id, p0 + 4, 7, p0 + 5, 8), # Status
            sheets.currency(sheet_id, p0 + 5, 7, p0 + 7, 8),    # Intrinsic/Time Value
            sheets.percent(sheet_id, p0 + 7, 7, p0 + 8, 8),     # TV Ann Yield
            sheets.green_if_positive(sheet_id, p0 + 3, 1, p0 + 4, 2),  # Net Put Premium
            sheets.green_if_positive(sheet_id, p0 + 5, 1, p0 + 6, 2),  # Put Results
            sheets.green_if_positive(sheet_id, p0 + 1, 1, p0 + 2, 2),  # Put Premium Received
            sheets.green_if_positive(sheet_id, p0 + 1, 7, p0 + 2, 8),  # Metrics Premium Received
            sheets.green_if_positive(sheet_id, p0 + 3, 7, p0 + 4, 8),  # Unrealized P&L
        ]
    sheets.apply_fmt(service, sheet_id, fmt_requests)

    print("  Updating Summary...")
    sheets._write_summary_row(service, tab_name, status, issues,
                               show_calls=show_calls, show_puts=show_puts)
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
