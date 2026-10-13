from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
TEXT_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
AXIS = "#c3c2b7"

SERIES = ("#2a78d6", "#eb6834", "#1baf7a")
SEQUENTIAL_BLUE = ("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b")

FONT_FAMILY = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def _style(fig: go.Figure, height: int, legend: bool = False) -> go.Figure:
    fig.update_layout(
        height=height,
        margin={"l": 8, "r": 16, "t": 16, "b": 8},
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font={"family": FONT_FAMILY, "color": TEXT_SECONDARY, "size": 13},
        showlegend=legend,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "x": 0,
            "title": None,
            "traceorder": "normal",
        },
        hoverlabel={"bgcolor": SURFACE, "font": {"family": FONT_FAMILY, "color": TEXT_PRIMARY}},
        barcornerradius=4,
    )
    fig.update_xaxes(
        showgrid=False, linecolor=AXIS, tickcolor=AXIS, tickfont={"color": TEXT_MUTED}, title=None
    )
    fig.update_yaxes(gridcolor=GRIDLINE, zeroline=False, tickfont={"color": TEXT_MUTED}, title=None)
    return fig


def columns(
    data: pd.DataFrame,
    x: str,
    y: str,
    *,
    value_format: str,
    value_prefix: str = "",
    height: int = 300,
    x_is_month: bool = True,
) -> go.Figure:
    """Single-series vertical bars; the chart title names the series, so there is no legend."""
    hover_x = "%{x|%b %Y}" if x_is_month else "%{x}"
    fig = go.Figure(
        go.Bar(
            x=data[x],
            y=data[y],
            marker_color=SERIES[0],
            hovertemplate=f"{hover_x}<br><b>{value_prefix}%{{y:{value_format}}}</b><extra></extra>",
        )
    )
    fig.update_layout(bargap=0.5)
    fig.update_yaxes(tickprefix=value_prefix, tickformat=_axis_format(value_format))
    if x_is_month:
        fig.update_xaxes(dtick="M1", tickformat="%b<br>%Y")
    return _style(fig, height)


def bars(
    data: pd.DataFrame,
    category: str,
    value: str,
    *,
    value_format: str,
    value_prefix: str = "",
    height: int | None = None,
) -> go.Figure:
    """Single-series horizontal bars, largest at the top, with the value at each bar tip."""
    ordered = data.iloc[::-1]
    fig = go.Figure(
        go.Bar(
            x=ordered[value],
            y=ordered[category],
            orientation="h",
            marker_color=SERIES[0],
            text=ordered[value],
            texttemplate=f"{value_prefix}%{{x:{value_format}}}",
            textposition="outside",
            textfont={"color": TEXT_SECONDARY},
            cliponaxis=False,
            hovertemplate=f"%{{y}}<br><b>{value_prefix}%{{x:{value_format}}}</b><extra></extra>",
        )
    )
    fig.update_layout(bargap=0.45)
    fig = _style(fig, height or 60 + 30 * len(ordered))
    fig.update_layout(margin={"r": 72})
    fig.update_xaxes(
        showgrid=True, gridcolor=GRIDLINE, showticklabels=False, showline=False, ticks=""
    )
    fig.update_yaxes(showgrid=False, tickfont={"color": TEXT_SECONDARY})
    return fig


def line(
    data: pd.DataFrame,
    x: str,
    y: str,
    *,
    value_format: str,
    value_prefix: str = "",
    height: int = 300,
) -> go.Figure:
    """Single-series line with a light area wash."""
    fig = go.Figure(
        go.Scatter(
            x=data[x],
            y=data[y],
            mode="lines",
            line={"color": SERIES[0], "width": 2, "shape": "linear"},
            fill="tozeroy",
            fillcolor="rgba(42, 120, 214, 0.10)",
            hovertemplate=f"%{{x|%d %b %Y}}<br><b>{value_prefix}%{{y:{value_format}}}</b>"
            "<extra></extra>",
        )
    )
    fig.update_layout(hovermode="x")
    fig.update_yaxes(
        tickprefix=value_prefix, tickformat=_axis_format(value_format), rangemode="tozero"
    )
    fig.update_xaxes(showspikes=True, spikecolor=AXIS, spikethickness=1, spikedash="solid")
    return _style(fig, height)


def stacked_columns(
    data: pd.DataFrame,
    x: str,
    y: str,
    series: str,
    order: dict[str, str],
    *,
    value_format: str,
    value_prefix: str = "",
    height: int = 320,
) -> go.Figure:
    """Stacked vertical bars. ``order`` maps each series value to its legend label."""
    fig = go.Figure()
    for colour, (key, label) in zip(SERIES, order.items(), strict=False):
        subset = data[data[series] == key]
        fig.add_bar(
            x=subset[x],
            y=subset[y],
            name=label,
            marker={"color": colour, "line": {"color": SURFACE, "width": 2}},
            hovertemplate=f"{label}: <b>{value_prefix}%{{y:{value_format}}}</b><extra></extra>",
        )
    fig.update_layout(barmode="stack", bargap=0.5, hovermode="x unified")
    fig.update_yaxes(tickprefix=value_prefix, tickformat=_axis_format(value_format))
    fig.update_xaxes(dtick="M1", tickformat="%b<br>%Y")
    return _style(fig, height, legend=True)


def retention_heatmap(matrix: pd.DataFrame, height: int = 420) -> go.Figure:
    """Cohort retention heatmap on a single-hue sequential ramp. Unobserved cells stay blank."""
    scale = [
        [index / (len(SEQUENTIAL_BLUE) - 1), colour] for index, colour in enumerate(SEQUENTIAL_BLUE)
    ]
    fig = go.Figure(
        go.Heatmap(
            z=matrix.to_numpy(),
            x=[f"M{period}" for period in matrix.columns],
            y=[month.strftime("%b %Y") for month in matrix.index],
            colorscale=scale,
            zmin=0,
            texttemplate="%{z:.0%}",
            xgap=2,
            ygap=2,
            hoverongaps=False,
            colorbar={"tickformat": ".0%", "thickness": 10, "outlinewidth": 0, "len": 0.8},
            hovertemplate="Cohort %{y}<br>%{x} after first purchase<br><b>%{z:.1%} active</b>"
            "<extra></extra>",
        )
    )
    fig = _style(fig, height)
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont={"color": TEXT_SECONDARY})
    fig.update_xaxes(side="top", showline=False, ticks="")
    return fig


def _axis_format(value_format: str) -> str:
    return value_format if "%" in value_format else "~s"
