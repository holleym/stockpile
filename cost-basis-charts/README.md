# Cost Basis Charts

Visualize your stock cost basis over time, overlaid on Yahoo Finance
historical prices, built from brokerage transaction exports using
Claude Code.

**Watch:** [Charts Your Broker Doesn't Show You (Using Claude Code)](https://youtu.be/LqroeMNC7AU)

## What this builds

- Parse brokerage transaction CSV (Schwab, Robinhood, Fidelity,
  Merrill Edge) to compute running adjusted cost basis per share
- Fetch historical price data from Yahoo Finance
- Chart: stock price vs. cost basis over time
- Chart: cumulative option premium collected over time
- Chart: P&L over time

## How to run

Run from the **repo root** using `uv run`:

```bash
# All configured symbols
uv run cost-basis-charts/run_charts.py

# Single symbol only
uv run cost-basis-charts/run_charts.py --symbol SCHW
```

HTML output (and optional PNG) is written to
`cost-basis-charts/output/`. Configure accounts in
`cost-basis-charts/config.toml` (copy from
`cost-basis-charts/config.toml.example`).

Never use `python` or `python3` directly — dependencies won't be
available. Run `uv sync` from the repo root first if you haven't
already.

## Data inputs

- Brokerage transaction CSV — Schwab, Robinhood, Fidelity, or Merrill
  Lynch (same parsers as the Position Tracker project)
- Yahoo Finance historical OHLC via `yfinance`

## Support

If you find this useful, you can support the work here:

- GitHub Sponsors: https://github.com/sponsors/medloh
- Patreon: https://www.patreon.com/OptionsforLongTermInvestors
