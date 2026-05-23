# Options Position Tracker

Track your covered calls, sold puts, dividends, and underlying stock
performance in Google Sheets — automatically built from your brokerage
transaction history.

One command turns a brokerage CSV export into a fully formatted Google
Sheet with live prices, annualized yields, P&L breakdown, and a summary
tab across all your positions.

Built entirely with [Claude Code](https://claude.ai/code) — no manual coding required.

**Watch:** [Claude Built My Stock & Options Tracker in Google Sheets from my Schwab Transactions](https://youtu.be/9uf3cyOWPBQ)

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
- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- A supported brokerage account (Schwab, Robinhood, Fidelity, or
  Merrill Edge)
- A Google account

### Step 1 — Get the code

```
git clone https://github.com/medloh/stockpile.git
cd stockpile
uv sync
```

### Step 2 — Download your transaction history

Export your full transaction history from your brokerage and place the
CSV in the `input/` folder. Supported brokerages and their export
locations:

- **Schwab** — Accounts → History → Export
- **Robinhood** — Account → Statements & History → Export to CSV
- **Fidelity** — Activity & Orders → Download
- **Merrill Edge** — Accounts → Statements & Documents → Download

Go back as far as possible — the script uses the full history to
compute cost basis and option P&L.

### Step 3 — Set up Google Sheets access

Follow the instructions in `google-sheets-setup/`.

### Step 4 — Configure and run

Copy the example config and fill in your details:

```
# macOS / Linux / Git Bash
cp positions/config.toml.example positions/config.toml

# Windows PowerShell
copy positions\config.toml.example positions\config.toml
```

Then run from the repo root:

```
uv run positions/run_tracker.py
```

The first run opens a browser to authorize Google Sheets access.
After that it runs silently. It fetches live prices from Yahoo Finance
and rebuilds all tabs from scratch.

### Step 5 — Update anytime

Download a fresh CSV and run the same command. The script always
rebuilds from the latest export.

---

## Usage

Run from the **parent `stockpile/` directory** using `uv run`:

```
uv run positions/run_tracker.py                              # run all configured accounts
uv run positions/run_tracker.py --brokerage schwab           # run only Schwab accounts
uv run positions/run_tracker.py --csv input/OTHER.csv        # override CSV path
uv run positions/run_tracker.py --brokerage schwab --csv input/OTHER.csv
```

`uv run` picks up the workspace virtualenv and the `stocks-shared` dependency automatically.

---

## Notes

- Supported brokerages: **Schwab**, **Robinhood**, **Fidelity**,
  **Merrill Edge** — set `brokerage` in `config.toml` to match your
  export file
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
- Interactive Brokers, E*TRADE — each has its own export format
- Goal: same script, same output, regardless of where your account lives
- Schwab, Robinhood, Fidelity, and Merrill Edge are already supported

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
