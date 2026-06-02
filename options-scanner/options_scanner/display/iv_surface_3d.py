"""Interactive 3D volatility surface for the Single Ticker tab.

The third "View" option on the Volatility surface chart (alongside
"Single expiration" and "All expirations"). Renders the whole chain as
a 3D shape — strike (x) × days-to-expiration (y) × IV % (z) — with:

- a translucent fitted-IV mesh (`go.Surface`) over a strike × DTE grid,
  clipped to the fit-supported strike range so we don't draw the
  spurious far-OTM/ITM extrapolation humps; and
- the raw per-contract IV as dots (`go.Scatter3d`) floating above/below
  the mesh, colored by IV+pp on the same red→gray→green diverging scale
  the 2D chart uses (green = IV-rich, red = IV-cheap in sell mode).

Drag-to-rotate / zoom / pan are built into Plotly. Mirrors the 2D
chart's "dots vs. fitted line" language in three dimensions.

`frame` must already carry the `_prep` display columns (FittedIV%, IV%,
IV+pp) plus strike / expiration / dte — i.e. the same frame the "All
expirations" branch builds in `iv_chart.show_iv_chart`.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render_iv_surface_3d(frame: pd.DataFrame, spot: float, ticker: str,
                         mode: str, buy: bool = False,
                         fit_range: tuple[float, float] | None = None,
                         delta_range: tuple[float, float] | None = None) -> None:
    """Render the 3D IV surface. No-op when there's no data to show.

    When `delta_range` is given and the frame has a `delta` column, an
    in-chart button group (next to the title) toggles between the delta
    band (default) and the full fitted chain — client-side, no rerun.
    """
    frame = frame.dropna(subset=["IV%", "strike", "dte"]).copy()
    if frame.empty:
        st.info("No chain data to render in 3D for this scan.")
        return
    frame = frame.sort_values(["expiration", "strike"])

    # Diverging IV+pp color scale, matching the 2D chart (sell: green rich /
    # red cheap; buy flips). Computed from the FULL frame so colors don't
    # shift when toggling the delta band.
    if buy:
        ivpp_scale = [[0.0, "#22c55e"], [0.5, "#cbd5e1"], [1.0, "#ef4444"]]
    else:
        ivpp_scale = [[0.0, "#ef4444"], [0.5, "#cbd5e1"], [1.0, "#22c55e"]]
    excess_max = float(max(abs(frame["IV+pp"].min()),
                           abs(frame["IV+pp"].max()), 1.0))

    has_delta = (delta_range is not None and "delta" in frame.columns)
    if has_delta:
        _dlo, _dhi = delta_range
        filtered = frame[frame["delta"].abs().between(_dlo, _dhi)]
        if filtered.empty:        # band excludes everything → no toggle
            has_delta = False

    hover = (
        "Strike $%{x:,.0f}<br>DTE %{y}d<br>%{customdata[1]}"
        "<br>IV %{z:.1f}%  ·  IV+pp %{customdata[0]:+.1f}"
        "<br>Delta %{customdata[2]:.2f}"
        "<br>Bid $%{customdata[3]:.2f}  Ask $%{customdata[4]:.2f}"
        "<br>Mid $%{customdata[5]:.2f}  Last %{customdata[6]}"
        "<br>OI %{customdata[7]:,}  Vol %{customdata[8]:,}<extra></extra>"
    )

    def _chain_traces(sub: pd.DataFrame, visible: bool):
        """Build (mesh? + dots) traces for one frame; returns (list, mesh_ok)."""
        traces = []
        n_exp = sub["expiration"].nunique()
        n_strk = sub["strike"].nunique()
        mesh_ok = n_exp >= 2 and n_strk >= 3 and "FittedIV%" in sub.columns
        if mesh_ok:
            mesh_src = sub.dropna(subset=["FittedIV%"])
            if fit_range is not None:
                lo, hi = fit_range
                mesh_src = mesh_src[mesh_src["strike"].between(lo, hi)]
            grid = mesh_src.pivot_table(index="dte", columns="strike",
                                        values="FittedIV%", aggfunc="mean")
            if grid.shape[0] >= 2 and grid.shape[1] >= 3:
                grid = grid.interpolate(axis=1, limit_area="inside")
                traces.append(go.Surface(
                    x=grid.columns.values, y=grid.index.values, z=grid.values,
                    opacity=0.6, showscale=False, colorscale="Blugrn",
                    hoverinfo="skip", name="Fitted surface", visible=visible,
                ))
            else:
                mesh_ok = False

        def _col(name):
            return (sub[name] if name in sub.columns
                    else pd.Series([float("nan")] * len(sub), index=sub.index))

        exp_str = sub["expiration"].apply(
            lambda d: datetime.strptime(d, "%Y-%m-%d").strftime("%b %d '%y"))
        last_str = _col("last").apply(
            lambda v: f"${v:.2f}" if pd.notna(v) and v > 0 else "—")
        traces.append(go.Scatter3d(
            x=sub["strike"], y=sub["dte"], z=sub["IV%"], mode="markers",
            marker=dict(
                size=4, color=sub["IV+pp"], colorscale=ivpp_scale,
                cmin=-excess_max, cmax=excess_max,
                colorbar=dict(title="IV+pp", thickness=12, len=0.6),
                line=dict(width=0.5, color="#0f172a"),
            ),
            customdata=np.stack([
                sub["IV+pp"], exp_str, _col("delta"), _col("bid"), _col("ask"),
                _col("mid"), last_str, _col("open_interest"), _col("volume"),
            ], axis=-1),
            hovertemplate=hover, name="Contracts", visible=visible,
        ))
        return traces, mesh_ok

    fig = go.Figure()

    # Build the chain trace set(s). With a delta band, build both (band default
    # visible, full hidden) so the in-chart button can swap them instantly.
    if has_delta:
        band_traces, mesh_ok = _chain_traces(filtered, visible=True)
        full_traces, _ = _chain_traces(frame, visible=False)
        for t in band_traces + full_traces:
            fig.add_trace(t)
        n_band, n_full = len(band_traces), len(full_traces)
    else:
        band_traces, mesh_ok = _chain_traces(frame, visible=True)
        for t in band_traces:
            fig.add_trace(t)
        n_band, n_full = len(band_traces), 0

    # ── Spot reference: a translucent vertical plane at x = spot ──────────────
    # A constant-x surface spanning the DTE (y) and IV (z) extents, with a
    # floating label denoting the spot price on the chart.
    spot_shown = spot and np.isfinite(spot)
    if spot_shown:
        y_lo, y_hi = float(frame["dte"].min()), float(frame["dte"].max())
        z_lo, z_hi = float(frame["IV%"].min()), float(frame["IV%"].max())
        yy = np.array([[y_lo, y_lo], [y_hi, y_hi]])
        zz = np.array([[z_lo, z_hi], [z_lo, z_hi]])
        xx = np.full((2, 2), float(spot))
        fig.add_trace(go.Surface(
            x=xx, y=yy, z=zz,
            showscale=False, opacity=0.18,
            colorscale=[[0, "#0f172a"], [1, "#0f172a"]],
            hoverinfo="skip", name="Spot",
        ))
        # Label anchored to the top edge of the plane (near strike, max IV).
        fig.add_trace(go.Scatter3d(
            x=[float(spot)], y=[y_hi], z=[z_hi],
            mode="text", text=[f"Spot ${spot:,.2f}"],
            textposition="top center",
            textfont=dict(color="#0f172a", size=12),
            hoverinfo="skip", name="Spot label",
        ))

    n_spot = 2 if spot_shown else 0

    # In-chart toggle between the delta band and the full chain. Buttons set
    # the `visible` array across all traces (spot traces stay on for both).
    updatemenus = []
    if has_delta:
        band_vis = [True] * n_band + [False] * n_full + [True] * n_spot
        full_vis = [False] * n_band + [True] * n_full + [True] * n_spot
        updatemenus = [dict(
            type="buttons", direction="right",
            x=0.99, xanchor="right", y=1.0, yanchor="top",
            pad=dict(t=2, r=2), showactive=True,
            bgcolor="rgba(255,255,255,0.85)", bordercolor="#cbd5e1",
            font=dict(size=11),
            buttons=[
                dict(label=f"Δ {_dlo:.2f}–{_dhi:.2f}", method="update",
                     args=[{"visible": band_vis}]),
                dict(label="Full chain", method="update",
                     args=[{"visible": full_vis}]),
            ],
        )]

    type_word = {"call": "calls", "put": "puts", "both": "options"}[mode]
    subj = f"{ticker} {type_word}" if ticker else type_word
    fig.update_layout(
        height=560,
        margin=dict(l=0, r=0, t=24, b=0),
        title=dict(text=f"{subj} — IV surface (3D)", x=0.01,
                   y=0.98, yanchor="top", font=dict(size=16)),
        scene=dict(
            domain=dict(y=[0.0, 1.0]),
            xaxis_title="Strike",
            yaxis_title="DTE",
            zaxis_title="IV (%)",
            camera=dict(eye=dict(x=1.6, y=-1.6, z=0.8)),
        ),
        showlegend=False,
        updatemenus=updatemenus,
    )
    st.plotly_chart(fig, use_container_width=True)

    note = ("Strike × DTE × IV. Dots are actual contract IV (colored by "
            "IV+pp — green rich, red cheap); ")
    note += ("the translucent mesh is the fitted surface. "
             if mesh_ok else
             "the fitted mesh is hidden (needs ≥2 expirations and ≥3 "
             "strikes). ")
    if spot_shown:
        note += f"Vertical plane = spot (${spot:,.2f}). "
    note += "Drag to rotate, scroll to zoom."
    st.caption(note)
