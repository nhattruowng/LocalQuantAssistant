"""Tests for FastAPI route wiring."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.dependencies import get_service
from api.main import app


class FakeApiService:
    """Small fake service used to test route contracts without side effects."""

    def symbols(self) -> list[str]:
        return ["BTC/USDT", "ETH/USDT"]

    def timeframes(self) -> list[str]:
        return ["15m", "1h"]

    def candles(self, symbol: str, timeframe: str, limit: int) -> list[dict[str, object]]:
        return [
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "timestamp": "2026-01-01T00:00:00+00:00",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10.0,
            }
        ][:limit]

    def update_data(self, symbol: str, timeframe: str, limit: int | None = None) -> int:
        return int(limit or 1)

    def build_features(self, symbol: str, timeframe: str) -> dict[str, object]:
        return {"rows": 10, "columns": ["timestamp", "close", "ema_20"]}

    def generate_signal(
        self,
        symbol: str,
        timeframe: str,
        account_balance: float,
        risk_percent: float,
        multi_timeframe: bool | None = None,
    ) -> dict[str, object]:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "signal": "WAIT",
            "confidence": 0.5,
            "entry": None,
            "stop_loss": None,
            "take_profit_1": None,
            "take_profit_2": None,
            "risk_reward": None,
            "reasons": ["test"],
            "explanation_v2": {"multi_timeframe": {"enabled": bool(multi_timeframe)}},
        }

    def run_backtest(
        self,
        symbol: str,
        timeframe: str,
        initial_balance: float,
        risk_percent: float,
    ) -> dict[str, object]:
        return {"rule_only": {"symbol": symbol, "timeframe": timeframe, "total_trades": 0}}

    def latest_backtest(self, symbol: str, timeframe: str) -> dict[str, object] | None:
        return {"symbol": symbol, "timeframe": timeframe, "total_trades": 0}

    def model_info(self, symbol: str | None = None, timeframe: str | None = None) -> dict[str, object]:
        return {"model_type": "RandomForestClassifier", "feature_columns": ["ema_20"]}

    def model_calibration(self, symbol: str | None = None, timeframe: str | None = None) -> dict[str, object]:
        return {
            "calibration_enabled": True,
            "calibration_method": "sigmoid",
            "brier_score_before": 0.2,
            "brier_score_after": 0.18,
            "report": {},
        }

    def train_model(self, symbol: str, timeframe: str) -> dict[str, object]:
        return {
            "model_path": "models/model.joblib",
            "metadata_path": "models/model.metadata.json",
            "model_type": "RandomForestClassifier",
            "metrics": {},
            "feature_columns": ["ema_20"],
        }

    def model_registry(self, symbol: str | None = None, timeframe: str | None = None) -> dict[str, object]:
        return {"models": [{"model_id": "BTC_USDT_15m_global_v001"}], "total": 1}

    def promote_model(self, model_id: str) -> dict[str, object]:
        return {"model_id": model_id, "status": "champion"}

    def archive_model(self, model_id: str) -> dict[str, object]:
        return {"model_id": model_id, "status": "archived"}

    def signal_history(self, symbol: str | None = None, timeframe: str | None = None) -> list[dict[str, object]]:
        return [{"symbol": symbol or "BTC/USDT", "timeframe": timeframe or "15m", "signal": "WAIT"}]


def test_api_health():
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_market_routes_return_symbols_timeframes_and_candles():
    client = _client()

    assert client.get("/api/symbols").json()["items"] == ["BTC/USDT", "ETH/USDT"]
    assert client.get("/api/timeframes").json()["items"] == ["15m", "1h"]
    candles = client.get("/api/candles?symbol=BTC/USDT&timeframe=15m&limit=1").json()

    assert candles[0]["symbol"] == "BTC/USDT"
    assert candles[0]["close"] == 100.5


def test_generate_signal_route():
    client = _client()

    response = client.post(
        "/api/signals/generate",
        json={
            "symbol": "BTC/USDT",
            "timeframe": "15m",
            "account_balance": 1000,
            "risk_percent": 1,
            "multi_timeframe": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["signal"] == "WAIT"
    assert response.json()["explanation_v2"]["multi_timeframe"]["enabled"] is True


def test_backtest_and_model_routes():
    client = _client()

    backtest = client.post(
        "/api/backtest/run",
        json={
            "symbol": "BTC/USDT",
            "timeframe": "15m",
            "initial_balance": 1000,
            "risk_percent": 1,
        },
    )
    model_info = client.get("/api/model/info")
    calibration = client.get("/api/model/calibration")
    registry = client.get("/api/model/registry")
    promote = client.post(
        "/api/model/promote",
        json={"model_id": "BTC_USDT_15m_global_v001"},
    )

    assert backtest.status_code == 200
    assert backtest.json()["rule_only"]["total_trades"] == 0
    assert model_info.status_code == 200
    assert model_info.json()["model_type"] == "RandomForestClassifier"
    assert calibration.status_code == 200
    assert calibration.json()["calibration_method"] == "sigmoid"
    assert registry.json()["total"] == 1
    assert promote.json()["status"] == "champion"


def _client() -> TestClient:
    """Return a TestClient with API service mocked."""
    app.dependency_overrides[get_service] = lambda: FakeApiService()
    return TestClient(app)
