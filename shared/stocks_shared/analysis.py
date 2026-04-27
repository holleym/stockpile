"""Pure analysis functions — no API calls, no I/O."""

import re
from datetime import date, timedelta
from collections import defaultdict


def _norm_opt_symbol(symbol):
    """Strip adjustment-digit suffix from option ticker so adjusted symbols match originals.
    e.g. 'AMC1 12/16/2022 24.00 P' → 'AMC 12/16/2022 24.00 P'
    """
    return re.sub(r"^([A-Z]+)\d+(\s)", r"\1\2", symbol)


def detect_open_positions(transactions):
    """Return list of currently open short option positions (net contracts > 0)."""
    pos = defaultdict(lambda: {
        "contracts": 0, "premium": 0.0,
        "type": None, "strike": None, "expiration": None
    })
    for row in transactions:
        _, action, opt_type, symbol, strike, expiration, qty, _, _, amount, _ = row
        if opt_type == "Stock" or qty == "":
            continue
        key = _norm_opt_symbol(symbol)
        p = pos[key]
        p["type"] = opt_type
        p["strike"] = strike
        p["expiration"] = expiration
        amt = float(amount) if amount != "" else 0.0
        q = int(qty)
        if action in ("Sell to Open", "Buy to Open"):
            p["contracts"] += q
            p["premium"] += amt
        elif action in ("Buy to Close", "Sell to Close", "Expired", "Assigned"):
            p["contracts"] -= q
            p["premium"] += amt

    return [{"symbol": s, **v} for s, v in pos.items() if v["contracts"] > 0]


def compute_avg_held_anchor(transactions):
    """Return (year, month, day) of the share-weighted average acquisition date
    for currently-held shares, or None if no shares are held.

    Stock Sell rows consume lots FIFO — so shares that have been sold no
    longer contribute to the weighted average.
    """
    lots = []  # [[date, shares_remaining], ...], chronological order
    for row in transactions:
        date_str, action, opt_type, _sym, _strike, _exp, qty, _, _, _, _ = row
        if opt_type != "Stock" or qty == "":
            continue
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})", date_str)
        if not m:
            continue
        lot_date = date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        q = int(qty)
        if action == "Buy":
            lots.append([lot_date, q])
        elif action == "Sell":
            remaining = q
            while remaining > 0 and lots:
                if lots[0][1] <= remaining:
                    remaining -= lots[0][1]
                    lots.pop(0)
                else:
                    lots[0][1] -= remaining
                    remaining = 0

    total = sum(shares for _, shares in lots)
    if total == 0:
        return None
    EPOCH = date(1899, 12, 30)
    weighted = round(sum((d - EPOCH).days * s for d, s in lots) / total)
    anchor = EPOCH + timedelta(days=weighted)
    return anchor.year, anchor.month, anchor.day


def compute_closed_avg_days(transactions):
    """Return FIFO-weighted average holding period in days across all sold lots.

    For a fully closed position this gives the actual weighted avg time each
    share was held, so annualized-yield formulas don't keep drifting as time
    passes after the close.  Returns None if no sells were matched to buys.
    """
    lots = []  # [[buy_date, shares_remaining], ...]
    total_share_days = 0
    total_shares = 0
    for row in transactions:
        date_str, action, opt_type, _sym, _strike, _exp, qty, _, _, _, _ = row
        if opt_type != "Stock" or qty == "":
            continue
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})", date_str)
        if not m:
            continue
        lot_date = date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        q = int(qty)
        if action == "Buy":
            lots.append([lot_date, q])
        elif action == "Sell":
            remaining = q
            while remaining > 0 and lots:
                if lots[0][1] <= remaining:
                    days = (lot_date - lots[0][0]).days
                    total_share_days += days * lots[0][1]
                    total_shares += lots[0][1]
                    remaining -= lots[0][1]
                    lots.pop(0)
                else:
                    days = (lot_date - lots[0][0]).days
                    total_share_days += days * remaining
                    total_shares += remaining
                    lots[0][1] -= remaining
                    remaining = 0
    if total_shares == 0:
        return None
    return round(total_share_days / total_shares)


def compute_status(transactions, open_positions):
    """Return (status, issues) where status is 'Closed', 'Consistent', or 'Inconsistent'.

    Checks:
    - Share count never goes negative in transaction history
    - Option contract counts never go negative for any symbol
    """
    issues = []

    if any(row[1] == "Transfer In" for row in transactions):
        issues.append("position includes a broker transfer — locate original buy transactions to resolve")

    shares = 0
    for row in transactions:
        _, action, opt_type, _sym, _, _, qty, _, _, _, _ = row
        if opt_type == "Stock" and qty != "":
            if action == "Buy":
                shares += int(qty)
            elif action == "Sell":
                shares -= int(qty)
            if shares < 0:
                issues.append("share count went negative")
                break

    option_net = defaultdict(int)
    for row in transactions:
        _, action, opt_type, symbol, _, _, qty, _, _, _, _ = row
        if opt_type in ("Call", "Put") and qty != "":
            key = _norm_opt_symbol(symbol)
            q = int(qty)
            if action in ("Sell to Open", "Buy to Open"):
                option_net[key] += q
            elif action in ("Buy to Close", "Sell to Close", "Expired", "Assigned"):
                option_net[key] -= q
                if option_net[key] < 0:
                    issues.append(f"option contracts went negative for {key}")

    if issues:
        return "Inconsistent", issues
    if shares <= 0 and not open_positions:
        return "Closed", []
    return "Consistent", []
