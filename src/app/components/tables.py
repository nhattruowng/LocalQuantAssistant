"""Dashboard table components."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render_dataframe_table(data: pd.DataFrame, empty_message: str) -> None:
    """Render a dataframe or a friendly empty state."""
    if data.empty:
        st.info(empty_message)
        return
    st.dataframe(data, use_container_width=True, hide_index=True)


def render_signal_history(history: pd.DataFrame) -> None:
    """Render signal history table."""
    render_dataframe_table(history, "No signal history yet. Generate a signal first.")
