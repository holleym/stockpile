"""
Tests for pure-logic functions in setup_tab.py.
Run with: pytest test_setup_tab.py -v
"""

import pytest
from stocks_shared.parsers.schwab import parse_dollar, parse_date
from layout import date_to_formula, shorten_symbol
from stocks_shared.analysis import (
    _norm_opt_symbol,
    compute_avg_held_anchor,
    compute_closed_avg_days,
    compute_status,
    detect_open_positions,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def stock(date_str, action, qty, amount=""):
    """Build a Stock transaction row."""
    return [date_str, action, "Stock", "TST", "", "", str(qty), "", "", str(amount), ""]

def option(date_str, action, opt_type, symbol, qty, amount=""):
    """Build a Call/Put transaction row."""
    return [date_str, action, opt_type, symbol, "100.00", "01/16/2026", str(qty), "", "", str(amount), ""]

def dividend(date_str, amount):
    return [date_str, "Dividend", "Dividend", "TST", "", "", "", "", "", str(amount), ""]


# ── parse_dollar ──────────────────────────────────────────────────────────────

class TestParseDollar:
    def test_plain_number(self):
        assert parse_dollar("1234.56") == 1234.56

    def test_currency_symbol(self):
        assert parse_dollar("$1,234.56") == 1234.56

    def test_negative(self):
        assert parse_dollar("-$500.00") == -500.00

    def test_negative_no_symbol(self):
        assert parse_dollar("-100.50") == -100.50

    def test_spaces(self):
        assert parse_dollar("  $1,000.00  ") == 1000.00

    def test_zero(self):
        assert parse_dollar("0") == 0.0

    def test_cents_only(self):
        assert parse_dollar("$.99") == 0.99

    def test_empty_string(self):
        assert parse_dollar("") is None

    def test_none(self):
        assert parse_dollar(None) is None

    def test_invalid(self):
        assert parse_dollar("not a number") is None


# ── parse_date ────────────────────────────────────────────────────────────────

class TestParseDate:
    def test_plain_date(self):
        assert parse_date("01/15/2024") == "01/15/2024"

    def test_as_of_suffix(self):
        assert parse_date("01/15/2024 as of 01/15/2024") == "01/15/2024"

    def test_as_of_only(self):
        assert parse_date("as of 12/31/2023") == "12/31/2023"

    def test_trailing_space(self):
        assert parse_date("01/15/2024 ") == "01/15/2024"

    def test_empty(self):
        assert parse_date("") == ""


# ── date_to_formula ───────────────────────────────────────────────────────────

class TestDateToFormula:
    def test_standard(self):
        assert date_to_formula("01/16/2026") == "DATE(2026,1,16)"

    def test_december(self):
        assert date_to_formula("12/31/2025") == "DATE(2025,12,31)"

    def test_leading_zeros_stripped(self):
        assert date_to_formula("06/09/2024") == "DATE(2024,6,9)"

    def test_empty(self):
        assert date_to_formula("") == "DATE(2099,1,1)"

    def test_none(self):
        assert date_to_formula(None) == "DATE(2099,1,1)"

    def test_wrong_format(self):
        assert date_to_formula("2026-01-16") == "DATE(2099,1,1)"


# ── shorten_symbol ────────────────────────────────────────────────────────────

class TestShortenSymbol:
    def test_call(self):
        assert shorten_symbol("NVDA 01/16/2026 150.00 C") == "150C 01/16/26"

    def test_put(self):
        assert shorten_symbol("SPY 12/31/2025 500.00 P") == "500P 12/31/25"

    def test_trailing_zeros_stripped(self):
        assert shorten_symbol("AAPL 06/20/2024 180.50 C") == "180.5C 06/20/24"

    def test_whole_strike(self):
        assert shorten_symbol("TST 03/15/2025 100.00 P") == "100P 03/15/25"

    def test_non_option_unchanged(self):
        assert shorten_symbol("AAPL") == "AAPL"

    def test_partial_match_unchanged(self):
        assert shorten_symbol("AAPL 01/16/2026 C") == "AAPL 01/16/2026 C"


# ── _norm_opt_symbol ──────────────────────────────────────────────────────────

class TestNormOptSymbol:
    def test_adjustment_digit_stripped(self):
        assert _norm_opt_symbol("AMC1 12/16/2022 24.00 P") == "AMC 12/16/2022 24.00 P"

    def test_no_adjustment(self):
        assert _norm_opt_symbol("AAPL 01/16/2026 150.00 C") == "AAPL 01/16/2026 150.00 C"

    def test_multi_digit_adjustment(self):
        assert _norm_opt_symbol("IBM10 06/20/2025 180.00 C") == "IBM 06/20/2025 180.00 C"

    def test_single_letter_ticker(self):
        assert _norm_opt_symbol("A1 12/31/2023 10.00 P") == "A 12/31/2023 10.00 P"


# ── compute_avg_held_anchor ───────────────────────────────────────────────────

class TestComputeAvgHeldAnchor:
    def test_no_transactions(self):
        assert compute_avg_held_anchor([]) is None

    def test_all_sold_returns_none(self):
        txns = [
            stock("01/01/2024", "Buy", 100, -5000),
            stock("06/01/2024", "Sell", 100, 5500),
        ]
        assert compute_avg_held_anchor(txns) is None

    def test_single_buy(self):
        txns = [stock("01/15/2024", "Buy", 100, -5000)]
        result = compute_avg_held_anchor(txns)
        assert result == (2024, 1, 15)

    def test_two_equal_buys_anchor_is_midpoint(self):
        # Buy 100 on Jan 1, Buy 100 on Mar 1 → anchor is midpoint of the two dates
        from datetime import date, timedelta
        EPOCH = date(1899, 12, 30)
        d1 = date(2024, 1, 1)
        d2 = date(2024, 3, 1)
        expected_days = round(((d1 - EPOCH).days * 100 + (d2 - EPOCH).days * 100) / 200)
        expected = EPOCH + timedelta(days=expected_days)
        txns = [
            stock("01/01/2024", "Buy", 100, -5000),
            stock("03/01/2024", "Buy", 100, -5000),
        ]
        result = compute_avg_held_anchor(txns)
        assert result == (expected.year, expected.month, expected.day)

    def test_fifo_sell_consumes_oldest_lot(self):
        # Buy 100 on Jan 1, Buy 100 on Jul 1, Sell 100 → only Jul 1 lot remains
        txns = [
            stock("01/01/2024", "Buy", 100, -5000),
            stock("07/01/2024", "Buy", 100, -5000),
            stock("09/01/2024", "Sell", 100, 5500),
        ]
        result = compute_avg_held_anchor(txns)
        assert result == (2024, 7, 1)

    def test_partial_sell(self):
        # Buy 100 on Jan 1, Sell 50 → 50 shares remain from Jan 1 lot
        txns = [
            stock("01/01/2024", "Buy", 100, -5000),
            stock("06/01/2024", "Sell", 50, 2750),
        ]
        result = compute_avg_held_anchor(txns)
        assert result == (2024, 1, 1)

    def test_only_sells_returns_none(self):
        txns = [stock("01/01/2024", "Sell", 100, 5000)]
        assert compute_avg_held_anchor(txns) is None

    def test_non_stock_rows_ignored(self):
        txns = [
            option("01/01/2024", "Sell to Open", "Call", "TST 01/16/2026 100.00 C", 1, 150),
            stock("03/01/2024", "Buy", 100, -5000),
        ]
        result = compute_avg_held_anchor(txns)
        assert result == (2024, 3, 1)


# ── compute_closed_avg_days ───────────────────────────────────────────────────

class TestComputeClosedAvgDays:
    def test_no_transactions(self):
        assert compute_closed_avg_days([]) is None

    def test_no_sells(self):
        txns = [stock("01/01/2024", "Buy", 100, -5000)]
        assert compute_closed_avg_days(txns) is None

    def test_no_buys(self):
        txns = [stock("01/01/2024", "Sell", 100, 5000)]
        assert compute_closed_avg_days(txns) is None

    def test_same_day_buy_sell(self):
        txns = [
            stock("01/01/2024", "Buy", 100, -5000),
            stock("01/01/2024", "Sell", 100, 5100),
        ]
        assert compute_closed_avg_days(txns) == 0

    def test_held_exactly_30_days(self):
        txns = [
            stock("01/01/2024", "Buy", 100, -5000),
            stock("01/31/2024", "Sell", 100, 5500),
        ]
        assert compute_closed_avg_days(txns) == 30

    def test_two_lots_different_hold_periods(self):
        # Buy 100 on Jan 1, Buy 100 on Feb 1, Sell all 200 on Mar 1
        # Lot 1: 100 shares × 59 days (Jan1→Mar1)
        # Lot 2: 100 shares × 29 days (Feb1→Mar1)
        # Weighted avg: (59 + 29) / 2 = 44 days
        txns = [
            stock("01/01/2024", "Buy", 100, -5000),
            stock("02/01/2024", "Buy", 100, -5000),
            stock("03/01/2024", "Sell", 200, 11000),
        ]
        assert compute_closed_avg_days(txns) == 44

    def test_fifo_two_sells_from_one_lot(self):
        # Buy 100 on Jan 1, Sell 50 on Feb 1 (31 days), Sell 50 on Mar 1 (60 days)
        # Weighted avg: (31 + 60) / 2 = 45 (rounds to 45 or 46 depending on Feb days)
        from datetime import date
        jan1 = date(2024, 1, 1)
        feb1 = date(2024, 2, 1)
        mar1 = date(2024, 3, 1)
        d1 = (feb1 - jan1).days  # 31
        d2 = (mar1 - jan1).days  # 60
        expected = round((d1 * 50 + d2 * 50) / 100)
        txns = [
            stock("01/01/2024", "Buy", 100, -5000),
            stock("02/01/2024", "Sell", 50, 2600),
            stock("03/01/2024", "Sell", 50, 2800),
        ]
        assert compute_closed_avg_days(txns) == expected

    def test_non_stock_rows_ignored(self):
        txns = [
            option("01/01/2024", "Sell to Open", "Call", "TST 01/16/2026 100.00 C", 1, 150),
            stock("01/01/2024", "Buy", 100, -5000),
            stock("04/10/2024", "Sell", 100, 5500),
        ]
        from datetime import date
        days = (date(2024, 4, 10) - date(2024, 1, 1)).days
        assert compute_closed_avg_days(txns) == days


# ── compute_status ────────────────────────────────────────────────────────────

class TestComputeStatus:
    def test_empty_is_closed(self):
        status, issues = compute_status([], [])
        assert status == "Closed"
        assert issues == []

    def test_all_sold_is_closed(self):
        txns = [
            stock("01/01/2024", "Buy", 100, -5000),
            stock("06/01/2024", "Sell", 100, 5500),
        ]
        status, issues = compute_status(txns, [])
        assert status == "Closed"

    def test_open_shares_is_consistent(self):
        txns = [stock("01/01/2024", "Buy", 100, -5000)]
        status, issues = compute_status(txns, [])
        assert status == "Consistent"
        assert issues == []

    def test_sell_before_buy_is_inconsistent(self):
        txns = [
            stock("01/01/2024", "Sell", 100, 5000),
            stock("02/01/2024", "Buy", 100, -5000),
        ]
        status, issues = compute_status(txns, [])
        assert status == "Inconsistent"
        assert any("negative" in i for i in issues)

    def test_option_close_without_open_is_inconsistent(self):
        sym = "TST 01/16/2026 100.00 C"
        txns = [
            stock("01/01/2024", "Buy", 100, -5000),
            option("02/01/2024", "Buy to Close", "Call", sym, 1, -200),
        ]
        status, issues = compute_status(txns, [])
        assert status == "Inconsistent"

    def test_open_option_position_is_consistent(self):
        sym = "TST 01/16/2026 100.00 C"
        txns = [
            stock("01/01/2024", "Buy", 100, -5000),
            option("02/01/2024", "Sell to Open", "Call", sym, 1, 300),
        ]
        open_pos = [{"symbol": sym, "contracts": 1, "premium": 300,
                     "type": "Call", "strike": "100.00", "expiration": "01/16/2026"}]
        status, issues = compute_status(txns, open_pos)
        assert status == "Consistent"


# ── detect_open_positions ─────────────────────────────────────────────────────

class TestDetectOpenPositions:
    def test_no_options_returns_empty(self):
        txns = [stock("01/01/2024", "Buy", 100, -5000)]
        assert detect_open_positions(txns) == []

    def test_open_call(self):
        sym = "TST 01/16/2026 100.00 C"
        txns = [option("01/01/2024", "Sell to Open", "Call", sym, 1, 300)]
        result = detect_open_positions(txns)
        assert len(result) == 1
        assert result[0]["type"] == "Call"
        assert result[0]["contracts"] == 1

    def test_closed_call_not_returned(self):
        sym = "TST 01/16/2026 100.00 C"
        txns = [
            option("01/01/2024", "Sell to Open", "Call", sym, 1, 300),
            option("02/01/2024", "Buy to Close", "Call", sym, 1, -100),
        ]
        assert detect_open_positions(txns) == []

    def test_expired_option_not_returned(self):
        sym = "TST 01/16/2026 100.00 C"
        txns = [
            option("01/01/2024", "Sell to Open", "Call", sym, 1, 300),
            option("01/17/2026", "Expired", "Call", sym, 1, 0),
        ]
        assert detect_open_positions(txns) == []

    def test_open_put(self):
        sym = "TST 01/16/2026 95.00 P"
        txns = [option("01/01/2024", "Sell to Open", "Put", sym, 1, 250)]
        result = detect_open_positions(txns)
        assert len(result) == 1
        assert result[0]["type"] == "Put"

    def test_adjustment_suffix_grouped_correctly(self):
        # Sell to Open with adjusted symbol, then Buy to Close with base symbol
        sym_adj = "TST1 01/16/2026 100.00 C"
        sym_base = "TST 01/16/2026 100.00 C"
        txns = [
            option("01/01/2024", "Sell to Open", "Call", sym_adj, 1, 300),
            option("02/01/2024", "Buy to Close", "Call", sym_base, 1, -100),
        ]
        assert detect_open_positions(txns) == []

    def test_premium_accumulates(self):
        sym = "TST 01/16/2026 100.00 C"
        txns = [
            option("01/01/2024", "Sell to Open", "Call", sym, 1, 300),
            option("02/01/2024", "Buy to Close", "Call", sym, 1, -100),
            option("03/01/2024", "Sell to Open", "Call", sym, 1, 250),
        ]
        result = detect_open_positions(txns)
        assert len(result) == 1
        assert result[0]["premium"] == pytest.approx(300 - 100 + 250)
