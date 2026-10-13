from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

CURRENCY = "£"


def money(value: float, decimals: int | None = None) -> str:
    """Format a currency amount, compacting millions and thousands unless decimals are set."""
    if value is None or math.isnan(value):
        return "n/a"
    if decimals is not None:
        return f"{CURRENCY}{value:,.{decimals}f}"
    if abs(value) >= 1_000_000:
        return f"{CURRENCY}{value / 1_000_000:.2f}M"
    if abs(value) >= 10_000:
        return f"{CURRENCY}{value / 1_000:.0f}K"
    return f"{CURRENCY}{value:,.0f}"


def percent(value: float, decimals: int = 1) -> str:
    if value is None or math.isnan(value):
        return "n/a"
    return f"{value:.{decimals}%}"


def metric_row(metrics: list[tuple[str, str, str]]) -> None:
    for column, (label, value, help_text) in zip(st.columns(len(metrics)), metrics, strict=True):
        column.metric(label, value, help=help_text, border=True)


def chart_card(title: str, figure: go.Figure, table: pd.DataFrame, note: str | None = None) -> None:
    """Render a titled chart with an optional note and the underlying data as a table view."""
    st.subheader(title)
    if note:
        st.caption(note)
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
    with st.expander("View data"):
        st.dataframe(table, hide_index=True, width="stretch")
