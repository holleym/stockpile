"""Generate interactive Plotly cost basis charts."""

from pathlib import Path
import pandas as pd
import plotly.graph_objects as go


def create_cost_basis_chart(symbol: str, price_history, cost_basis_series: list,
                            output_path: str) -> None:
    """Write an HTML Plotly chart with three lines:
      1. Close price (Yahoo Finance)
      2. Adjusted cost basis (FIFO minus net option premiums and dividends)
      3. Plain FIFO cost basis

    price_history: DataFrame with DatetimeIndex and 'Close' column.
    cost_basis_series: list of dicts from compute_cost_basis_series().
    output_path: destination .html file path.
    """
    if not cost_basis_series:
        print(f"  No cost basis data for {symbol}, skipping chart.")
        return

    # Build daily cost basis series via forward-fill
    cb_df = pd.DataFrame(cost_basis_series)
    cb_df["date"] = pd.to_datetime(cb_df["date"])
    cb_df = cb_df.set_index("date").sort_index()

    # Strip timezone from yfinance index for alignment
    price_history = price_history.copy()
    if price_history.index.tz is not None:
        price_history.index = price_history.index.tz_convert(None)
    price_history = price_history.sort_index()

    # Forward-fill cost basis on business days through end of price history
    end = price_history.index.max()
    daily_idx = pd.date_range(start=cb_df.index.min(), end=end, freq="B")
    cb_daily = cb_df.reindex(daily_idx).ffill().dropna(subset=["shares"])
    cb_daily = cb_daily[cb_daily["shares"] > 0]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=price_history.index,
        y=price_history["Close"],
        name="Close Price",
        line=dict(color="royalblue", width=2.5),
    ))

    fig.add_trace(go.Scatter(
        x=cb_daily.index,
        y=cb_daily["adjusted_cost"],
        name="Adjusted Cost Basis",
        line=dict(color="darkorange", width=2),
    ))

    fig.add_trace(go.Scatter(
        x=cb_daily.index,
        y=cb_daily["fifo_cost"],
        name="FIFO Cost Basis",
        line=dict(color="#aaaaaa", width=1.5, dash="dot"),
    ))

    fig.update_layout(
        title=dict(text=f"<b>{symbol}</b> — Price vs. Cost Basis", font_size=20),
        xaxis_title="Date",
        yaxis_title="Price (USD)",
        hovermode="x unified",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=520,
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(output_path, include_plotlyjs="cdn")
    print(f"  Chart saved → {output_path}")
