"""Reusable Streamlit card components."""

from __future__ import annotations

from typing import Any

import streamlit as st


SIGNAL_COLORS = {
    "BUY": "#16a34a",
    "SELL": "#dc2626",
    "WAIT": "#ca8a04",
}


def render_metric_card(label: str, value: Any, help_text: str | None = None) -> None:
    """Render a compact metric card."""
    st.metric(label=label, value=value, help=help_text)


def render_signal_card(setup: dict[str, Any] | None) -> None:
    """Render the main signal card."""
    if setup is None:
        st.info("No signal generated yet. Choose a symbol/timeframe and click Generate Signal.")
        return

    signal = str(setup.get("signal", "WAIT"))
    color = SIGNAL_COLORS.get(signal, "#71717a")
    st.markdown(
        f"""
        <div style="border:1px solid #e5e7eb;border-radius:8px;padding:18px;background:#ffffff">
          <div style="font-size:14px;color:#64748b">Current Signal</div>
          <div style="font-size:42px;font-weight:800;color:{color};line-height:1">{signal}</div>
          <div style="margin-top:8px;color:#334155">
            Confidence: <strong>{float(setup.get("confidence", 0.0)):.2f}</strong>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_reasons(title: str, items: list[str]) -> None:
    """Render reasons or risk notes."""
    st.subheader(title)
    if not items:
        st.caption("No notes.")
        return
    for item in items:
        st.markdown(f"- {item}")
