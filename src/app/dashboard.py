"""Streamlit dashboard for LocalQuant Assistant."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pandas as pd
import streamlit as st

from app.components.cards import render_metric_card, render_reasons, render_signal_card
from app.components.charts import candlestick_chart, equity_curve_chart, rsi_chart
from app.components.tables import render_dataframe_table, render_signal_history
from app.services.dashboard_service import DashboardService
from backtest.models import BacktestReport
from config.loader import load_settings
from utils.logger import setup_logger


st.set_page_config(
    page_title="LocalQuant Assistant",
    page_icon="LQ",
    layout="wide",
)


@st.cache_resource
def get_service() -> DashboardService:
    """Create dashboard service once per Streamlit session."""
    settings = load_settings()
    logger = setup_logger(settings.logging)
    return DashboardService(settings=settings, logger=logger)


@st.cache_data(show_spinner=False)
def load_features(symbol: str, timeframe: str) -> pd.DataFrame:
    """Cached feature dataset loader."""
    return get_service().load_features(symbol, timeframe)


@st.cache_data(show_spinner=False)
def load_model_metadata(symbol: str, timeframe: str) -> dict[str, object] | None:
    """Cached latest model metadata loader."""
    return get_service().latest_model_metadata(symbol, timeframe)


@st.cache_data(show_spinner=False)
def load_history() -> pd.DataFrame:
    """Cached signal history loader."""
    return get_service().load_signal_history()


def main() -> None:
    """Render the dashboard."""
    service = get_service()
    _inject_style()
    st.title("LocalQuant Assistant")
    st.caption("Local ML-assisted setup recommendations. Suggestions only, no auto trading.")

    with st.sidebar:
        st.header("Control Panel")
        symbol = st.selectbox("Symbol", service.symbols)
        timeframe = st.selectbox("Timeframe", service.timeframes)
        account_balance = st.number_input(
            "Account Balance",
            min_value=0.0,
            value=float(service.settings.risk.account_balance),
            step=100.0,
        )
        risk_percent_display = st.number_input(
            "Risk Percent",
            min_value=0.0,
            max_value=100.0,
            value=float(service.settings.risk.risk_per_trade_pct * 100),
            step=0.1,
        )
        risk_percent = risk_percent_display / 100.0

        if st.button("Update Data", use_container_width=True):
            _clear_caches()
            with st.spinner("Downloading latest candles..."):
                try:
                    inserted = service.update_data(symbol, timeframe)
                    st.success(f"Saved {inserted} new candles.")
                    _clear_caches()
                except Exception as error:
                    st.error(f"Update failed: {error}")

        if st.button("Generate Signal", use_container_width=True):
            _clear_caches()
            with st.spinner("Generating setup..."):
                try:
                    st.session_state["latest_setup"] = service.generate_signal(
                        symbol=symbol,
                        timeframe=timeframe,
                        account_balance=account_balance,
                        risk_percent=risk_percent,
                    ).to_dict()
                    st.success("Signal generated.")
                    _clear_caches()
                except Exception as error:
                    st.error(str(error))

        if st.button("Run Backtest", use_container_width=True):
            _clear_caches()
            with st.spinner("Running backtest..."):
                try:
                    st.session_state["backtest_reports"] = service.run_backtest(
                        symbol=symbol,
                        timeframe=timeframe,
                        account_balance=account_balance,
                        risk_percent=risk_percent,
                    )
                    st.success("Backtest completed.")
                except Exception as error:
                    st.error(str(error))

    try:
        features = load_features(symbol, timeframe)
    except Exception:
        features = pd.DataFrame()

    market_tab, signal_tab, backtest_tab, model_tab, history_tab = st.tabs(
        ["Market", "Signal", "Backtest", "Model", "History"]
    )
    with market_tab:
        _render_market_tab(features)
    with signal_tab:
        _render_signal_tab(st.session_state.get("latest_setup"))
    with backtest_tab:
        _render_backtest_tab(st.session_state.get("backtest_reports"))
    with model_tab:
        _render_model_tab(load_model_metadata(symbol, timeframe))
    with history_tab:
        _render_history_tab(load_history())


def _render_market_tab(features: pd.DataFrame) -> None:
    """Render market chart tab."""
    if features.empty:
        st.info("No data found. Please update market data first.")
        return
    latest = features.dropna().tail(1)
    cols = st.columns(4)
    if not latest.empty:
        row = latest.iloc[0]
        cols[0].metric("Close", f"{row['close']:.2f}")
        cols[1].metric("Regime", str(row.get("market_regime", "UNKNOWN")))
        cols[2].metric("ATR %", f"{float(row.get('atr_percent', 0.0)):.2%}")
        cols[3].metric("Volume Ratio", f"{float(row.get('volume_ratio', 0.0)):.2f}")
    st.plotly_chart(candlestick_chart(features), use_container_width=True)
    if "rsi_14" in features:
        st.plotly_chart(rsi_chart(features), use_container_width=True)


def _render_signal_tab(setup: dict[str, object] | None) -> None:
    """Render latest signal tab."""
    render_signal_card(setup)
    if setup is None:
        return
    cols = st.columns(4)
    cols[0].metric("Market Regime", setup.get("market_regime", "UNKNOWN"))
    cols[1].metric("Strategy", setup.get("strategy", "NONE"))
    cols[2].metric("Risk/Reward", _fmt(setup.get("risk_reward")))
    cols[3].metric("Position Size", _fmt(setup.get("position_size")))

    levels = st.columns(4)
    levels[0].metric("Entry", _fmt(setup.get("entry")))
    levels[1].metric("Stop Loss", _fmt(setup.get("stop_loss")))
    levels[2].metric("Take Profit 1", _fmt(setup.get("take_profit_1")))
    levels[3].metric("Take Profit 2", _fmt(setup.get("take_profit_2")))
    render_reasons("Reasons", list(setup.get("reasons", [])))
    render_reasons("Risk Notes", list(setup.get("risk_notes", [])))


def _render_backtest_tab(reports: dict[str, BacktestReport] | None) -> None:
    """Render backtest tab."""
    if not reports:
        st.info("No backtest report yet. Click Run Backtest from the sidebar.")
        return
    mode = st.radio("Report", list(reports.keys()), horizontal=True)
    report = reports[mode]
    cols = st.columns(6)
    cols[0].metric("Total Trades", report.total_trades)
    cols[1].metric("Winrate", f"{report.winrate:.2%}")
    cols[2].metric("Net Profit", f"{report.net_profit:.2f}")
    cols[3].metric("Profit Factor", _fmt(report.profit_factor))
    cols[4].metric("Max Drawdown", f"{report.max_drawdown:.2f}")
    cols[5].metric("Expectancy", f"{report.expectancy:.2f}")
    trades = pd.DataFrame([trade.to_dict() for trade in report.trades])
    st.plotly_chart(equity_curve_chart(trades), use_container_width=True)
    render_dataframe_table(trades, "No trades were generated in this backtest.")


def _render_model_tab(metadata: dict[str, object] | None) -> None:
    """Render model metadata tab."""
    if metadata is None:
        st.info("No model found. Please train a model first.")
        return
    cols = st.columns(3)
    cols[0].metric("Model Type", metadata.get("model_type", "UNKNOWN"))
    cols[1].metric("Trained At", metadata.get("trained_at", "-"))
    cols[2].metric("Feature Count", len(metadata.get("feature_columns", [])))
    st.subheader("Metrics")
    st.json(metadata.get("metrics", {}), expanded=False)
    importance = (
        metadata.get("metrics", {}).get("feature_importance", {})
        if isinstance(metadata.get("metrics"), dict)
        else {}
    )
    if importance:
        st.subheader("Feature Importance")
        importance_df = pd.DataFrame(
            [{"feature": key, "importance": value} for key, value in importance.items()]
        ).head(30)
        st.bar_chart(importance_df.set_index("feature"))


def _render_history_tab(history: pd.DataFrame) -> None:
    """Render signal history tab."""
    if history.empty:
        render_signal_history(history)
        return
    filters = st.columns(3)
    signal_values = ["ALL", *sorted(history["signal"].dropna().unique().tolist())]
    strategy_values = ["ALL", *sorted(history["strategy"].dropna().unique().tolist())]
    selected_signal = filters[0].selectbox("Signal", signal_values)
    selected_strategy = filters[1].selectbox("Strategy", strategy_values)
    selected_date = filters[2].text_input("From Date", placeholder="YYYY-MM-DD")
    filtered = history.copy()
    if selected_signal != "ALL":
        filtered = filtered[filtered["signal"] == selected_signal]
    if selected_strategy != "ALL":
        filtered = filtered[filtered["strategy"] == selected_strategy]
    if selected_date and "recorded_at" in filtered:
        recorded_at = pd.to_datetime(filtered["recorded_at"], errors="coerce")
        from_date = pd.to_datetime(selected_date, errors="coerce")
        if pd.notna(from_date):
            filtered = filtered[recorded_at.dt.date >= from_date.date()]
    render_signal_history(filtered)


def _clear_caches() -> None:
    """Clear cached dashboard data."""
    load_features.clear()
    load_model_metadata.clear()
    load_history.clear()


def _fmt(value: object) -> str:
    """Format optional numeric values."""
    if value is None:
        return "-"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def _inject_style() -> None:
    """Add small, restrained UI polish."""
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.5rem;}
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 12px 14px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
