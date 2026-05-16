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


def render_explainability(explainability: dict[str, Any] | None) -> None:
    """Render model explanation factors for a setup."""
    st.subheader("Model Explanation")
    if not explainability:
        st.info("No model explanation available. Train a model first or install SHAP for richer explanations.")
        return

    st.caption(str(explainability.get("summary", "")))
    positive = list(explainability.get("top_positive_factors", []))
    negative = list(explainability.get("top_negative_factors", []))
    cols = st.columns(2)
    with cols[0]:
        st.markdown("**Top positive factors**")
        _render_factor_list(positive, empty_text="No positive factors.")
    with cols[1]:
        st.markdown("**Top negative factors**")
        _render_factor_list(negative, empty_text="No negative factors.")


def _render_factor_list(items: list[Any], empty_text: str) -> None:
    """Render feature contribution rows."""
    if not items:
        st.caption(empty_text)
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        feature = item.get("feature", "-")
        impact = float(item.get("impact", 0.0))
        st.markdown(f"- `{feature}`: `{impact:.4f}`")
