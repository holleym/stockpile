# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This directory stores Schwab brokerage transaction exports for stock and options trading analysis.

## Data Format

CSV files exported from Schwab with columns: `Date, Action, Symbol, Description, Quantity, Price, Fees & Comm, Amount`

- **Action** values include: `Buy`, `Sell`, `Buy to Open`, `Sell to Open`, `Buy to Close`, `Sell to Close`
- **Symbol** for options follows the pattern: `TICKER MM/DD/YYYY STRIKE C/P` (e.g., `AMD 01/16/2026 150.00 C`)
- **Amount** is negative for debits (purchases) and positive for credits (sales)
- Fees are listed separately in `Fees & Comm`

## File Naming

Files are named `TICKER_YYYYMMDD.csv` where the date reflects the export date.
