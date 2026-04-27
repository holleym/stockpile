# Options Position Tracker

Track your covered calls, sold puts, dividends, and underlying stock performance
in Google Sheets — automatically built from your Schwab transaction history.

One command turns a Schwab CSV export into a fully formatted Google Sheet with
live prices, annualized yields, P&L breakdown, and a summary tab across all
your positions.

Built entirely with [Claude Code](https://claude.ai/code) — no manual coding required.

**Watch the setup video:** https://youtu.be/9uf3cyOWPBQ

> **Beta:** This is new code under active development. Numbers may contain bugs —
> verify anything important against your brokerage statements before acting on it.

---

## What it tracks

- **Stock Position** — shares held, avg cost, market value, total invested
- **Stock Results** — gain $, gain %, annualized gain
- **Call History Stats & Open Calls** — premium received/paid, current position, days left, ITM/OTM status
- **Put History Stats & Open Puts** — same for sold puts
- **Open Call/Put Metrics** — intrinsic value, time value, TV annualized yield
- **Dividends** — total collected, payment count
- **P&L Breakdown** — stock gain + call results + put results + dividends = total P&L
- **Returns** — close-out value, annualized yield on invested capital and close-out value
- **Summary tabs** — three tabs covering open positions, closed positions, and anything the script couldn't reconcile

---

## Setup

### What you need
- Python 3 installed
- A Schwab brokerage account
- A Google account

### Step 1 — Get the code

Download or clone this repo:

```
git clone https://github.com/medloh/stocks-positions.git
cd stocks-positions
```

Install dependencies:

```
pip install google-auth google-auth-oauthlib google-api-python-client yfinance
```

### Step 2 — Download your transaction history from Schwab

1. Log in to Schwab and go to **Accounts → History**
2. Set the date range to cover your full history — go back as far as you can
3. Click **Export** — it downloads as a CSV
4. Save it as `ALL_TRANS.csv` in the repo root folder

The script handles all tickers from a single export. You don't need to clean
up or reformat the file.

### Step 3 — Set up Google Sheets access

Follow the instructions in `docs/google_sheets_setup.md`.

### Step 4 — Run the script

```
python src/setup_tab.py ALL_TRANS.csv Schwab
```

The first time you run it, a browser window will open asking you to authorize
access to your Google Sheets account. Click Allow. After that it runs silently.

The script will work through all your tickers, fetch current stock and option
prices from Yahoo Finance, and build a tab per ticker plus three summary tabs.
Depending on how many positions you have, this takes a few minutes.

### Step 5 — Update anytime

Download a fresh CSV from Schwab and run the same command. The script clears
the spreadsheet and rebuilds everything from scratch.

---

## Usage

```
python run_tracker.py                   # run all configured accounts
python run_tracker.py --brokerage schwab  # run only Schwab accounts
python run_tracker.py --csv OTHER.csv --brokerage schwab  # override CSV path
```

---

## Notes

- Currently supports Schwab CSV exports only
- Option market values are fetched from Yahoo Finance using the (bid+ask)/2 midpoint
- The script always deletes and recreates the ticker tab — the Summary tab is preserved
- Open Calls and Open Puts sections display all currently open contracts for the position
- **Multiple accounts run serially, not in parallel.** The Google Sheets API quota is
  per project, not per spreadsheet — running accounts in parallel would share the same
  rate limit bucket and increase 429 errors rather than saving time. Yahoo Finance has
  the same constraint per IP. Stock prices and option chains are cached in memory across
  accounts, so the same ticker is only fetched once per run regardless of how many
  accounts hold it.

---

## Roadmap

Future features, roughly in priority order.

### Other broker support
- Fidelity, Interactive Brokers, E*TRADE — each has its own export format
- Goal: same script, same output, regardless of where your account lives

### Audience-requested metrics
- Open for requests in comments — will track and add the most-asked-for ones

### Multi-account support
- Combine multiple accounts (e.g., individual + IRA) into a single consolidated sheet
- Summary tabs would aggregate across all accounts with per-account breakdowns

### Threshold alerts
- Let users set a minimum TV Ann Yield per position
- Highlight rows in red when an open call drops below the threshold — time to roll

### Income-over-time chart
- Cumulative option premium + dividends collected per position, plotted over time
- Makes the "covered call compounding" story visual

### Tax lot / wash sale awareness
- Flag potential wash sales when a position is closed at a loss and reopened within 30 days
- Short-term vs. long-term gain breakdown per position

### Benchmark comparison
- Show annualized return vs. SPY or QQQ for the same holding period
- Answers: "would I have done better just holding the index?"

### Dividend calendar
- Pull upcoming ex-dividend dates for all held positions
- Useful for timing covered call expirations around dividend dates

### Greeks snapshot
- Fetch delta and theta for open options from Yahoo Finance
- Particularly useful for put sellers monitoring assignment risk

### Automated scheduling
- Instructions (or a wrapper script) for running on a daily schedule via Task Scheduler
  (Windows) or cron (Mac/Linux) so the sheet stays current without manual steps

### Charts
- Position tabs: P&L breakdown pie chart (stock vs. calls vs. puts vs. dividends), cumulative
  income over time (premium + dividends), stock price vs. adjusted cost basis over time
- Summary tabs: portfolio close-out value by ticker (bar chart), annualized yield comparison
  across positions
