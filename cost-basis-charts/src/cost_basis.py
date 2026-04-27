"""Compute running FIFO cost basis per share over time from a transaction list."""

from collections import deque
from datetime import datetime


def _parse_date(date_str):
    return datetime.strptime(date_str, "%m/%d/%Y").date()


def compute_cost_basis_series(transactions):
    """Compute running cost basis per share over time.

    Returns a list of dicts, one entry per transaction that changes shares or
    cost basis, only for periods where shares > 0:

      {
        'date':          datetime.date,
        'shares':        int,
        'fifo_cost':     float,      # plain FIFO avg cost per share
        'adjusted_cost': float,      # FIFO cost minus net option premiums and dividends
      }

    Transaction row format (11 elements):
      [date, action, opt_type, symbol, strike, expiration, qty, price, fees, amount, notes]

    Cost basis adjustments:
      - Buy / Transfer In: adds shares at purchase price (Transfer In uses 0 if no price)
      - Sell: removes lots FIFO; scales the adjustment proportionally with shares sold
      - Sell to Open (call or put): premium received reduces adjusted cost basis
      - Buy to Close: premium paid increases adjusted cost basis
      - Expired / Assigned: no direct cash effect (share sale handled separately)
      - Dividend: cash received reduces adjusted cost basis
    """
    lots = deque()       # [(date, qty_remaining, cost_per_share), ...]
    fifo_total = 0.0     # sum of remaining lot costs: qty * cost_per_share
    shares_held = 0
    adjustment = 0.0     # cumulative net premiums + dividends (positive = lowers cost)

    series = []

    for row in transactions:
        date_str, action, opt_type, symbol, strike, expiration, qty, price, fees, amount, _ = row

        if not date_str or not action:
            continue
        try:
            txn_date = _parse_date(date_str)
        except (ValueError, TypeError):
            continue

        qty_i = int(qty) if qty not in ("", None) else 0
        price_f = float(price) if price not in ("", None) else 0.0
        amount_f = float(amount) if amount not in ("", None) else 0.0

        if opt_type == "Stock":
            if action in ("Buy", "Transfer In"):
                fifo_total += qty_i * price_f
                shares_held += qty_i
                lots.append((txn_date, qty_i, price_f))

            elif action == "Sell" and shares_held > 0:
                old_shares = shares_held
                remaining = qty_i
                while remaining > 0 and lots:
                    lot_date, lot_qty, lot_price = lots[0]
                    if lot_qty <= remaining:
                        fifo_total -= lot_qty * lot_price
                        shares_held -= lot_qty
                        remaining -= lot_qty
                        lots.popleft()
                    else:
                        fifo_total -= remaining * lot_price
                        shares_held -= remaining
                        lots[0] = (lot_date, lot_qty - remaining, lot_price)
                        remaining = 0
                # Adjustment is tied to shares — scale it down proportionally
                if old_shares > 0:
                    adjustment *= shares_held / old_shares

        elif opt_type in ("Call", "Put"):
            if action == "Sell to Open":
                # Premium received (amount is positive cash inflow)
                adjustment += amount_f
            elif action == "Buy to Close":
                # Premium paid (amount is negative cash outflow), reduces the adjustment
                adjustment += amount_f

        elif opt_type == "Dividend":
            # Dividend received (amount is positive)
            adjustment += amount_f

        if shares_held > 0:
            fifo_cost = fifo_total / shares_held
            adjusted_cost = (fifo_total - adjustment) / shares_held
            series.append({
                "date": txn_date,
                "shares": shares_held,
                "fifo_cost": round(fifo_cost, 4),
                "adjusted_cost": round(adjusted_cost, 4),
            })

    return series
