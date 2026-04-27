# Cost Basis Charts — YouTube Tutorial

Visualize your stock cost basis over time, overlaid on Yahoo Finance historical prices,
built from brokerage transaction exports using Claude Code.

## What this builds

- Parse Schwab/Robinhood transaction CSV to compute running adjusted cost basis per share
- Fetch historical price data from Yahoo Finance
- Chart: stock price vs. cost basis over time
- Chart: cumulative option premium collected over time
- Chart: P&L over time

## Data inputs

- Brokerage transaction CSV (same format as the Position Tracker project)
- Yahoo Finance historical OHLC via `yfinance`

## YouTube angle

Full Claude Code workflow — describe the feature, iterate on the output visually,
no manual coding required.
