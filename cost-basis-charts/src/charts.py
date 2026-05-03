"""Generate interactive Plotly cost basis charts."""

from pathlib import Path
import pandas as pd
import plotly.graph_objects as go


def _pl_fmt(series):
    """Format a Series of P&L values as '+$X.XX' / '-$X.XX' strings."""
    return [f"+${v:.2f}" if v >= 0 else f"-${abs(v):.2f}" for v in series]


def _place_annotations(fig, items, x, label_bg="rgba(255,255,255,0.92)", data_x=None):
    """Place annotations at data x with collision avoidance.

    items: list of (y_data, text, color), any order.
    Sorts by y descending and nudges overlapping labels downward.
    Draws a dotted connector from (data_x, y_data) to (x, nudged_y).
    """
    if not items:
        return

    y_max = max(i[0] for i in items) * 1.15 or 1
    min_sep = y_max * (52 / 420)

    sorted_items = sorted(items, key=lambda i: i[0], reverse=True)
    adj_y = [item[0] for item in sorted_items]

    for i in range(1, len(adj_y)):
        if adj_y[i - 1] - adj_y[i] < min_sep:
            adj_y[i] = adj_y[i - 1] - min_sep

    for (y_data, text, color), y in zip(sorted_items, adj_y):
        if data_x is not None:
            fig.add_trace(go.Scatter(
                x=[data_x, x],
                y=[y_data, y],
                mode="lines",
                line=dict(color=color, width=1, dash="dot"),
                showlegend=False,
                hoverinfo="skip",
            ))
        fig.add_annotation(
            xref="x", x=x,
            yref="y", y=y,
            text=text,
            showarrow=False, xanchor="left", align="left",
            font=dict(color=color, size=13),
            bgcolor=label_bg,
            bordercolor=color, borderwidth=1, borderpad=7,
        )


SCHEMES = [
    # Classic — white background
    {"close": "royalblue", "adj": "darkorange", "fifo": "#9b59b6",
     "intrinsic": "firebrick", "time_value": "slateblue", "strike": "dimgray",
     "income": "seagreen", "income_fill": "rgba(46,139,87,0.15)",
     "template": "plotly_white", "paper_bg": "#ffffff", "plot_bg": "#ffffff",
     "font_color": "#222222", "label_bg": "rgba(255,255,255,0.92)"},
    # Teal — warm off-white background
    {"close": "#00838F", "adj": "#E64A19", "fifo": "#2E7D32",
     "intrinsic": "#AD1457", "time_value": "#4527A0", "strike": "#546E7A",
     "income": "#1B5E20", "income_fill": "rgba(27,94,32,0.15)",
     "template": "plotly_white", "paper_bg": "#f5f0eb", "plot_bg": "#f5f0eb",
     "font_color": "#222222", "label_bg": "rgba(245,240,235,0.92)"},
    # Midnight — near-black dark background
    {"close": "#58a6ff", "adj": "#ffa657", "fifo": "#d2a8ff",
     "intrinsic": "#ff7b72", "time_value": "#79c0ff", "strike": "#8b949e",
     "income": "#3fb950", "income_fill": "rgba(63,185,80,0.12)",
     "template": "plotly_dark", "paper_bg": "#0d1117", "plot_bg": "#0d1117",
     "font_color": "#e6edf3", "label_bg": "rgba(13,17,23,0.92)"},
    # Earth — light gray background
    {"close": "#5C6BC0", "adj": "#C8960C", "fifo": "#388E3C",
     "intrinsic": "#BF360C", "time_value": "#37474F", "strike": "#795548",
     "income": "#2E7D32", "income_fill": "rgba(46,125,50,0.15)",
     "template": "plotly_white", "paper_bg": "#f0f0f0", "plot_bg": "#f0f0f0",
     "font_color": "#222222", "label_bg": "rgba(240,240,240,0.92)"},
    # Slate — dark navy background
    {"close": "#64b5f6", "adj": "#ffcc02", "fifo": "#a5d6a7",
     "intrinsic": "#ef9a9a", "time_value": "#b39ddb", "strike": "#78909c",
     "income": "#56d364", "income_fill": "rgba(86,211,100,0.12)",
     "template": "plotly_dark", "paper_bg": "#1a1f2e", "plot_bg": "#1a1f2e",
     "font_color": "#e0e0e0", "label_bg": "rgba(26,31,46,0.92)"},
]

_DARK_SCHEMES = [s for s in SCHEMES if s["template"] == "plotly_dark"]


def _format_open_options(open_options: list) -> str:
    today = pd.Timestamp.today().normalize()
    parts = []
    for opt in open_options:
        exp = opt.get("expiration", "")
        try:
            m, d, y = exp.split("/")
            exp_ts  = pd.Timestamp(f"{y}-{m}-{d}")
            exp_fmt = exp_ts.strftime("%b %d, %Y")
            days_left = (exp_ts - today).days
            days_str  = f"{days_left}d" if days_left > 0 else "expired"
            exp_label = f"{exp_fmt} ({days_str})"
        except Exception:
            exp_label = exp
        parts.append(f"{opt['qty']} {opt['opt_type']} | Strike ${float(opt['strike']):.2f} | Exp {exp_label}")
    return "   ·   ".join(parts)


def create_cost_basis_chart(symbol: str, price_history, cost_basis_series: list,
                            output_path: str, live_cost_series=None,
                            option_breakdown=None, open_options=None,
                            save_png: bool = False) -> None:
    if not cost_basis_series:
        print(f"  No cost basis data for {symbol}, skipping chart.")
        return

    sc = _DARK_SCHEMES[hash(symbol) % len(_DARK_SCHEMES)]

    # Build daily cost basis series via forward-fill
    cb_df = pd.DataFrame(cost_basis_series)
    cb_df["date"] = pd.to_datetime(cb_df["date"])
    cb_df = cb_df.set_index("date").sort_index()
    cb_df = cb_df[~cb_df.index.duplicated(keep="last")]

    # Strip timezone and normalize to midnight so dates align with cb_daily's date_range index
    price_history = price_history.copy()
    if price_history.index.tz is not None:
        price_history.index = price_history.index.tz_convert(None)
    price_history.index = price_history.index.normalize()
    price_history = price_history.sort_index()

    # Forward-fill cost basis on business days through end of price history
    end = price_history.index.max()
    daily_idx = pd.date_range(start=cb_df.index.min(), end=end, freq="B")
    cb_daily = cb_df.reindex(daily_idx).ffill().dropna(subset=["shares"])
    cb_daily = cb_daily[cb_daily["shares"] > 0]

    # Align data for hover P&L customdata
    adj_at_ph   = cb_daily["adjusted_cost"].reindex(price_history.index, method="ffill")
    fifo_at_ph  = cb_daily["fifo_cost"].reindex(price_history.index, method="ffill")
    close_at_cb = price_history["Close"].reindex(cb_daily.index, method="nearest")

    close_pl = (price_history["Close"] - adj_at_ph).round(2)
    adj_pl   = (close_at_cb - cb_daily["adjusted_cost"]).round(2)
    fifo_pl  = (close_at_cb - cb_daily["fifo_cost"]).round(2)

    # Current values for right-edge annotations
    last_close  = float(price_history["Close"].iloc[-1])
    last_adj    = float(cb_daily["adjusted_cost"].iloc[-1])
    last_fifo   = float(cb_daily["fifo_cost"].iloc[-1])
    last_shares = int(cb_daily["shares"].iloc[-1])
    last_income    = float(cb_daily["total_income"].iloc[-1]) if "total_income" in cb_daily.columns else 0.0
    last_income_ps = last_fifo - last_adj

    pl_vs_adj     = last_close - last_adj
    pl_vs_adj_pct = pl_vs_adj / last_adj * 100
    pl_sign       = "+" if pl_vs_adj >= 0 else "-"
    pl_color      = "seagreen" if pl_vs_adj >= 0 else "crimson"

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=price_history.index,
        y=price_history["Close"],
        name="Close Price",
        line=dict(color=sc["close"], width=3),
        customdata=_pl_fmt(close_pl),
        hovertemplate=(
            "<b>%{x|%b %d, %Y}</b><br>"
            "Close: $%{y:.2f}<br>"
            "P&L: %{customdata}/shr"
            "<extra>Close Price</extra>"
        ),
    ))

    fig.add_trace(go.Scatter(
        x=cb_daily.index,
        y=cb_daily["adjusted_cost"],
        name="Adjusted Cost Basis",
        line=dict(color=sc["adj"], width=3),
        customdata=_pl_fmt(adj_pl),
        hovertemplate=(
            "<b>%{x|%b %d, %Y}</b><br>"
            "Adj. Cost: $%{y:.2f}/shr<br>"
            "P&L: %{customdata}/shr"
            "<extra>Adjusted Cost Basis</extra>"
        ),
    ))

    fig.add_trace(go.Scatter(
        x=cb_daily.index,
        y=cb_daily["fifo_cost"],
        name="FIFO Cost Basis",
        line=dict(color=sc["fifo"], width=3),
        customdata=list(zip(_pl_fmt(fifo_pl), cb_daily["shares"].astype(int))),
        hovertemplate=(
            "<b>%{x|%b %d, %Y}</b><br>"
            "FIFO Cost: $%{y:.2f}/shr<br>"
            "Shares: %{customdata[1]}<br>"
            "P&L: %{customdata[0]}/shr"
            "<extra>FIFO Cost Basis</extra>"
        ),
    ))

    # Income per share area + event annotations
    if "total_income" in cb_daily.columns and last_income > 0.5:
        income_ps = (cb_daily["fifo_cost"] - cb_daily["adjusted_cost"]).round(2)
        fig.add_trace(go.Scatter(
            x=cb_daily.index,
            y=income_ps,
            name="Income/Share",
            mode="lines",
            line=dict(color=sc["income"], width=2),
            fill="tozeroy",
            fillcolor=sc["income_fill"],
            customdata=cb_daily["total_income"].round(0).values,
            hovertemplate=(
                "<b>%{x|%b %d, %Y}</b><br>"
                "Income/share: +$%{y:.2f}<br>"
                "Total income: +$%{customdata:,.0f}"
                "<extra>Income</extra>"
            ),
        ))

        income_events = pd.DataFrame([
            e for e in cost_basis_series if e.get("affects") == "adjusted"
        ])
        if not income_events.empty:
            income_events["date"] = pd.to_datetime(income_events["date"])
            ev_ps    = income_ps.reindex(income_events["date"], method="nearest")
            ev_total = cb_daily["total_income"].reindex(income_events["date"], method="nearest")
            fig.add_trace(go.Scatter(
                x=income_events["date"],
                y=ev_ps.values,
                mode="markers",
                marker=dict(size=8, color=sc["income"], symbol="circle",
                            line=dict(width=1.5, color="white")),
                text=[f"+${ps:.2f}/shr  ${tot:,.0f} total"
                      for ps, tot in zip(ev_ps, ev_total)],
                hovertemplate="%{text}<extra></extra>",
                showlegend=False,
            ))

    # Collect all right-edge annotations then place with collision avoidance
    annot_items = [
        (last_close,
         f"<b>Close: ${last_close:.2f}</b><br>"
         f"P&L vs adj. cost: {pl_sign}${abs(pl_vs_adj):.2f}/shr",
         sc["close"]),
        (last_adj,  f"<b>Adj. Cost: ${last_adj:.2f}/shr</b>",  sc["adj"]),
        (last_fifo, f"<b>FIFO Cost: ${last_fifo:.2f}/shr</b><br>{last_shares} shares", sc["fifo"]),
    ]
    if last_income > 0.5:
        annot_items.append((
            last_income_ps,
            f"<b>Income: +${last_income_ps:.2f}/shr</b><br>"
            f"<b>${last_income:,.0f} total</b>",
            sc["income"],
        ))

    # Live adjusted cost: full BS-estimated line from option open date to today
    if live_cost_series is not None and not live_cost_series.empty:
        last_live  = float(live_cost_series.iloc[-1])
        lpl        = last_close - last_live
        lpl_pct    = lpl / last_live * 100
        lpl_sign   = "+" if lpl >= 0 else "-"
        lpl_color  = "seagreen" if lpl >= 0 else "crimson"
        last_date  = live_cost_series.index[-1]

        close_at_live = price_history["Close"].reindex(live_cost_series.index, method="nearest")
        live_pl = (close_at_live - live_cost_series).round(2)

        fig.add_trace(go.Scatter(
            x=live_cost_series.index,
            y=live_cost_series.values,
            name="Live Adj. Cost (w/ open options)",
            mode="lines",
            line=dict(color=lpl_color, width=2.5, dash="dash"),
            customdata=_pl_fmt(live_pl),
            hovertemplate=(
                "<b>%{x|%b %d, %Y}</b><br>"
                "Live Adj. Cost: $%{y:.2f}/shr<br>"
                "P&L: %{customdata}/shr"
                "<extra>Live Adj. Cost</extra>"
            ),
        ))
        fig.add_trace(go.Scatter(
            x=[last_date], y=[last_live],
            mode="markers",
            marker=dict(size=14, symbol="diamond", color=lpl_color,
                        line=dict(width=2, color="white")),
            showlegend=False,
            hovertemplate=(
                f"<b>Live Adj. Cost: ${last_live:.2f}</b><br>"
                f"P&L: {lpl_sign}${abs(lpl):.2f}/shr ({lpl_sign}{abs(lpl_pct):.1f}%)"
                "<extra></extra>"
            ),
        ))
        annot_items.append((
            last_live,
            f"<b>Live: ${last_live:.2f}</b><br>"
            f"P&L: {lpl_sign}${lpl:.2f}/shr ({lpl_sign}{lpl_pct:.1f}%)",
            lpl_color,
        ))

    annot_x = price_history.index[-1] + pd.Timedelta(days=7)

    # Strike price dashed line over option lifetime
    if open_options:
        for opt in open_options:
            strike = float(opt["strike"])
            open_ts = pd.Timestamp(opt["open_date"])
            try:
                m, d, y = opt["expiration"].split("/")
                exp_ts = pd.Timestamp(f"{y}-{m}-{d}")
            except Exception:
                exp_ts = price_history.index[-1]
            fig.add_trace(go.Scatter(
                x=[open_ts, exp_ts],
                y=[strike, strike],
                mode="lines",
                line=dict(color=sc["strike"], width=2.5, dash="dash"),
                name=f"Strike ${strike:.2f}",
                hovertemplate=f"Strike: ${strike:.2f} ({opt['qty']} {opt['opt_type']})<extra></extra>",
            ))
            annot_items.append((
                strike,
                f"<b>Strike: ${strike:.2f}</b><br>{opt['qty']} {opt['opt_type']} exp {exp_ts.strftime('%b %d, %Y')}",
                sc["strike"],
            ))

    if option_breakdown is not None:
        intrinsic  = option_breakdown["intrinsic"]
        time_value = option_breakdown["time_value"]
        if not intrinsic.empty:
            last_iv = float(intrinsic.iloc[-1])
            annot_items.append((
                last_iv,
                f"<b>Intrinsic: ${last_iv:.2f}/shr</b>",
                sc["intrinsic"],
            ))
        if not time_value.empty:
            last_tv = float(time_value.iloc[-1])
            tv_yield = last_tv / last_close * 100
            annot_items.append((
                last_tv,
                f"<b>Time Value: ${last_tv:.2f}/shr</b><br>"
                f"Closeout yield: {tv_yield:.1f}%",
                sc["time_value"],
            ))

    _place_annotations(fig, annot_items, annot_x, sc["label_bg"],
                       data_x=price_history.index[-1])

    # Option intrinsic + time value breakdown (secondary y-axis)
    if option_breakdown is not None:
        intrinsic  = option_breakdown["intrinsic"]
        time_value = option_breakdown["time_value"]
        fig.add_trace(go.Scatter(
            x=intrinsic.index, y=intrinsic.values,
            name="Intrinsic Value",
            line=dict(color=sc["intrinsic"], width=2),
            hovertemplate=(
                "<b>%{x|%b %d, %Y}</b><br>"
                "Intrinsic: $%{y:.2f}/shr"
                "<extra>Intrinsic Value</extra>"
            ),
        ))
        fig.add_trace(go.Scatter(
            x=time_value.index, y=time_value.values,
            name="Time Value",
            line=dict(color=sc["time_value"], width=2, dash="dot"),
            hovertemplate=(
                "<b>%{x|%b %d, %Y}</b><br>"
                "Time Value: $%{y:.2f}/shr"
                "<extra>Time Value</extra>"
            ),
        ))

    # Transaction annotation markers
    annot_df = pd.DataFrame([
        e for e in cost_basis_series if e.get("label") and e.get("affects")
    ])
    if not annot_df.empty:
        annot_df["date"] = pd.to_datetime(annot_df["date"])
        for affects, y_col, color in [
            ("fifo",     "fifo_cost",     sc["fifo"]),
            ("adjusted", "adjusted_cost", sc["adj"]),
        ]:
            sub = annot_df[annot_df["affects"] == affects]
            if sub.empty:
                continue
            y_vals = cb_daily[y_col].reindex(sub["date"], method="nearest")
            fig.add_trace(go.Scatter(
                x=sub["date"],
                y=y_vals.values,
                mode="markers",
                marker=dict(size=10, color=color, symbol="circle",
                            line=dict(width=1.5, color="white")),
                text=sub["label"],
                hovertemplate="%{text}<extra></extra>",
                showlegend=False,
            ))

    fig.update_layout(
        title=dict(
            text=f"<b>{symbol}</b> — Price, Cost Basis, Income, & Option Metrics",
            font_size=26,
        ),
        xaxis=dict(title="Date", title_font=dict(size=16), tickfont=dict(size=14),
                   range=[price_history.index[0], annot_x + pd.Timedelta(days=180)]),
        yaxis=dict(title="Price (USD)", title_font=dict(size=16), tickfont=dict(size=14),
                   rangemode="tozero"),
        hovermode="closest",
        hoverlabel=dict(font=dict(size=15), namelength=-1),
        template=sc["template"],
        paper_bgcolor=sc["paper_bg"],
        plot_bgcolor=sc["plot_bg"],
        font=dict(color=sc["font_color"]),
        legend=dict(orientation="v", yanchor="top", y=0.99,
                    xanchor="left", x=0.01, traceorder="normal",
                    font=dict(size=14), bgcolor=sc["label_bg"],
                    bordercolor=sc["font_color"], borderwidth=1),
        margin=dict(l=60, r=20, t=80, b=60),
        autosize=True,
    )

    html = fig.to_html(include_plotlyjs="cdn", full_html=True)
    # Make the chart fill the full browser viewport
    html = html.replace(
        "</head>",
        "<style>body{margin:0;overflow:hidden;}"
        ".plotly-graph-div{height:100vh!important;width:100vw!important;}</style></head>",
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html, encoding="utf-8")
    print(f"  Chart saved → {output_path}")

    if save_png:
        png_path = Path(output_path).with_suffix(".png")
        fig.write_image(str(png_path), width=1600, height=900, scale=2)
        print(f"  PNG saved   → {png_path}")
