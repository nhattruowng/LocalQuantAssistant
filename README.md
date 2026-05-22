# LocalQuant Assistant

LocalQuant Assistant là một hệ thống local-first dùng Python để thu thập dữ liệu thị trường, xây dựng feature kỹ thuật, nhận diện market regime, huấn luyện mô hình machine learning và tạo gợi ý setup giao dịch dạng `BUY`, `SELL`, hoặc `WAIT`.

Dự án được thiết kế như một production-ready MVP: kiến trúc rõ ràng, chạy local, dễ mở rộng thêm data source, model, strategy, dashboard, alert và paper trading trong tương lai.

Tài liệu cập nhật lần cuối: `2026-05-23`.

## Important Disclaimer

This system is for research and decision support only.

It does not provide financial advice.

It does not execute trades automatically.

Mọi tín hiệu từ hệ thống chỉ là gợi ý phân tích. Người dùng chịu trách nhiệm tự đánh giá rủi ro trước mọi quyết định giao dịch. Dự án không cam kết lợi nhuận, không thay thế tư vấn tài chính, và không được thiết kế để tự động giao dịch tiền thật.

## Key Features

- Real OHLCV data collection từ Binance qua `ccxt`.
- SQLite local database với cơ chế không lưu trùng candle.
- Technical indicator engineering bằng pandas vectorized operations.
- Price action, trend, momentum, volatility và volume features.
- Market regime detection: `UPTREND`, `DOWNTREND`, `SIDEWAY`, `BREAKOUT_UP`, `BREAKOUT_DOWN`, `HIGH_VOLATILITY`, `LOW_VOLATILITY`, `UNKNOWN`.
- Soft regime scoring và optional strategy ensemble để giảm phụ thuộc vào mapping cứng regime -> strategy.
- Strategy Memory Feedback để adaptive agents biết strategy/regime/direction nào đang thắng/thua gần đây.
- ML-based `BUY` / `SELL` / `WAIT` classification bằng XGBoost nếu có, fallback RandomForest.
- Versioned model registry với global model, regime-specific model, champion/candidate/archive lifecycle.
- TP/SL first-touch labeling để tránh label quá đơn giản.
- Chronological train/validation/test split, hỗ trợ walk-forward validation và purged CV, không shuffle time-series.
- Risk-aware setup recommendation với entry, stop loss, take profit, risk/reward, dynamic position sizing và safety filters.
- Mean Reversion Danger Filter, Breakout Fakeout Defense, RiskGuard và CircuitBreaker để giảm overtrading/setup nguy hiểm.
- Explainable AI cho tín hiệu bằng SHAP nếu khả dụng, fallback bằng model feature importance.
- Strategy layer: Trend Following, Breakout Confirmation, Mean Reversion.
- Backtesting engine có fee, slippage, cooldown, drawdown, winrate và profit factor.
- Streamlit dashboard local với chart, signal card, backtest report, model metadata và signal history.
- Telegram alert cho tín hiệu `BUY` / `SELL` đủ mạnh, có cooldown chống spam.
- Paper Trading Mode để mô phỏng mở/đóng lệnh giả lập và lưu lịch sử local.
- Docker + Docker Compose để chạy local nhanh hơn.

## Architecture

```text
Market Data
    -> Collector
    -> SQLite Database
    -> Feature Engineering
    -> Market Regime Detector
    -> ML Prediction
    -> Strategy Opinion Ensemble
    -> Strategy Memory Feedback
    -> Risk Manager
    -> Safety Filters / RiskGuard
    -> Signal Engine
    -> Backtest / Dashboard UI
```

Agent-based orchestration được triển khai theo kiểu deterministic service classes, không phải autonomous trading bot:

```text
MarketDataAgent
  -> FeatureEngineeringAgent
  -> MarketRegimeAgent
  -> PredictionAgent
  -> StrategyAgent
  -> RiskAgent
  -> SignalDecisionAgent
  -> ExplanationAgent
  -> TradingOrchestratorAgent
```

Các agent chỉ điều phối pipeline phân tích và tạo `TradeSetup`. Không có agent nào đặt lệnh thật.

## Tech Stack

| Area | Technology |
| --- | --- |
| Language | Python 3.11+ |
| Data processing | pandas |
| Market data | ccxt |
| Database | SQLite |
| Machine learning | XGBoost optional, RandomForest fallback |
| Model persistence | joblib |
| Dashboard | Streamlit |
| REST API | FastAPI, Uvicorn |
| Charting | Plotly |
| Testing | pytest |
| Config | YAML + `.env` overrides |
| Containerization | Docker, Docker Compose |

## Folder Structure

```text
localquant-assistant/
├── data/
│   ├── raw/
│   ├── processed/
│   └── backtest/
├── docs/
├── models/
├── notebooks/
├── scripts/
│   ├── build_features.py
│   ├── collect_market_data.py
│   └── benchmark_pipeline.py
├── src/
│   ├── agents/
│   ├── api/
│   ├── app/
│   ├── backtest/
│   ├── collector/
│   ├── config/
│   ├── database/
│   ├── domain/
│   ├── features/
│   ├── labeling/
│   ├── ml/
│   ├── regime/
│   ├── risk/
│   ├── signal/
│   ├── strategy/
│   └── utils/
├── tests/
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── requirements.txt
├── README.md
└── main.py
```

## Installation

### Option 1: Local Python

```powershell
cd localquant-assistant
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
```

### Option 2: Docker

```powershell
cd localquant-assistant
cp .env.example .env
docker compose up --build
```

Dashboard mặc định chạy tại:

```text
http://localhost:8501
```

Docker volumes:

- `data/` lưu SQLite database, processed features và backtest output.
- `models/` lưu model artifacts và metadata.
- `logs/` lưu log local nếu được cấu hình.

## Configuration

Config chính nằm ở:

```text
src/config/settings.yaml
```

Các biến môi trường mẫu nằm ở:

```text
.env.example
```

Các biến thường dùng:

```env
LOCALQUANT_ENV=local
APP_CONFIG_PATH=src/config/settings.yaml
LOCALQUANT_DB_PATH=data/localquant.db
LOG_LEVEL=INFO
STREAMLIT_PORT=8501
API_PORT=8000
LOCALQUANT_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Ví dụ cấu hình collector:

```yaml
collector:
  exchange: binance
  symbols: [BTC/USDT, ETH/USDT]
  timeframes: [15m, 1h, 4h]
  candles_limit: 200
  retry_attempts: 3
  retry_delay_seconds: 1.0
```

Ví dụ cấu hình risk:

```yaml
risk:
  account_balance: 10000
  risk_per_trade_pct: 0.01
  dynamic_sizing_enabled: true
  max_risk_per_trade_pct: 1.0
  min_risk_reward: 2.0
  stop_loss_atr_multiplier: 1.5
  take_profit_1_atr_multiplier: 2.0
  take_profit_2_atr_multiplier: 3.0
```

Ví dụ cấu hình adaptive strategy memory và safety filters:

```yaml
adaptive_strategy:
  enabled: true
  base_threshold: 0.65
  min_opinion_score: 0.55
  conflict_margin: 0.12
  memory_lookback_trades: 30
  memory_lookback_bars: 200
  memory_min_trades_required: 10
  memory_max_score_penalty: 0.20
  memory_max_size_penalty: 0.50
  memory_block_after_consecutive_losses: true

safety_filters:
  mean_reversion_danger_enabled: true
  breakout_fakeout_defense_enabled: true
  extreme_volatility_block: true
  higher_timeframe_conflict_block: true
  mean_reversion_danger_threshold: 0.70
  breakout_fakeout_threshold: 0.55
```

Ví dụ cấu hình Telegram alert:

```yaml
notification:
  enabled: false
  min_confidence: 0.70
  min_risk_reward: 2.0
  cooldown_seconds: 900
  request_timeout_seconds: 5.0
```

Ví dụ cấu hình Paper Trading:

```yaml
paper_trading:
  enabled: false
  initial_balance: 10000.0
```

Telegram token và chat id chỉ đặt trong `.env`, không commit secret:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

## How To Run

### 1. Collect Data

```powershell
python scripts/collect_market_data.py --symbol BTC/USDT --timeframe 15m
```

Docker:

```powershell
docker compose run --rm localquant python scripts/collect_market_data.py --symbol BTC/USDT --timeframe 15m
```

Make:

```powershell
make collect SYMBOL=BTC/USDT TIMEFRAME=15m
```

### 2. Build Features

```powershell
python scripts/build_features.py --symbol BTC/USDT --timeframe 15m
```

Docker:

```powershell
docker compose run --rm localquant python scripts/build_features.py --symbol BTC/USDT --timeframe 15m
```

Make:

```powershell
make features SYMBOL=BTC/USDT TIMEFRAME=15m
```

### 3. Train Model

```powershell
python main.py train --symbol BTC/USDT --timeframe 15m
```

Docker:

```powershell
docker compose run --rm localquant python main.py train --symbol BTC/USDT --timeframe 15m
```

Make:

```powershell
make train SYMBOL=BTC/USDT TIMEFRAME=15m
```

Training pipeline:

1. Load candles từ SQLite.
2. Build technical features.
3. Generate TP/SL first-touch labels.
4. Split theo thời gian: train 70%, validation 15%, test 15% theo mặc định.
5. Nếu `training.validation.method = walk_forward`, chạy walk-forward validation với purge size mặc định bằng `labeling.lookahead_bars`.
6. Train XGBoost nếu khả dụng, nếu không fallback RandomForest.
7. Calibrate probability bằng validation set nếu `training.calibration.enabled = true`.
8. Save model vào versioned registry trong `models/{symbol}/{timeframe}/...`.
9. Nếu `training.regime_specific.enabled = true`, train thêm model theo từng market regime đủ sample.

Walk-forward config:

```yaml
training:
  validation:
    method: walk_forward
    n_splits: 5
    train_window_bars: 500
    validation_window_bars: 100
    expanding_window: true
    embargo_size: 0
```

Metadata model lưu thêm `validation_method`, `fold_metrics`, `purge_size`, `embargo_size`, `dataset_start`, `dataset_end` và summary như `mean_accuracy`, `std_accuracy`, `mean_f1`, `worst_fold_metric`.

Model registry layout:

```text
models/
  BTC_USDT/
    15m/
      global/
        v001/
          model.joblib
          metadata.json
      regime/
        UPTREND/
          v001/
            model.joblib
            metadata.json
```

Registry metadata gồm `model_id`, `model_version`, `model_scope`, `regime`, `symbol`, `timeframe`, `trained_at`, `dataset_start`, `dataset_end`, `feature_columns`, `label_distribution`, `validation_metrics`, `calibration_metrics` và `status`.

Probability calibration config:

```yaml
training:
  calibration:
    enabled: true
    method: sigmoid   # sigmoid hoặc isotonic
    cv: prefit

signal:
  use_calibrated_probability: true
```

Khi bật calibration, trainer train base model trên train set, fit calibrator trên validation set, sau đó lưu wrapper model. Metadata có `calibration_enabled`, `calibration_method`, `brier_score_before`, `brier_score_after`, `log_loss_before`, `log_loss_after`, reliability curve data, per-class Brier score và probability histogram. Nếu calibration không khả dụng, hệ thống fallback về raw probability và ghi rõ trong metadata/UI.

Regime-specific model config:

```yaml
training:
  regime_specific:
    enabled: true
    min_samples_per_regime: 200
    allowed_regimes: [UPTREND, DOWNTREND, SIDEWAY, BREAKOUT_UP, BREAKOUT_DOWN]
    min_validation_accuracy: 0.0
  registry:
    auto_promote_champion: true
```

Khi prediction, `PredictionService` ưu tiên regime-specific champion nếu tồn tại và đạt quality threshold. Nếu không có model phù hợp, hệ thống fallback về global champion và trả `fallback_reason`.

### 4. Backtest

```powershell
python main.py backtest --symbol BTC/USDT --timeframe 15m --model models/model.joblib
```

Rule-only backtest hoặc override execution cost model:

```powershell
python main.py backtest --symbol BTC/USDT --timeframe 15m --cost-model stress
python main.py backtest-stress --symbol BTC/USDT --timeframe 15m
```

Nếu metadata không nằm cạnh model:

```powershell
python main.py backtest --symbol BTC/USDT --timeframe 15m --model models/model.joblib --metadata models/model.metadata.json
```

Docker:

```powershell
docker compose run --rm localquant python main.py backtest --symbol BTC/USDT --timeframe 15m --model models/model.joblib
```

Make:

```powershell
make backtest SYMBOL=BTC/USDT TIMEFRAME=15m MODEL=models/model.joblib
```

### 5. Dashboard

```powershell
streamlit run src/app/dashboard.py
```

Docker:

```powershell
docker compose up --build
```

Make:

```powershell
make dashboard
make docker-up
```

### 6. REST API

FastAPI app chạy tách khỏi Streamlit để frontend React hoặc client khác có thể dùng trading engine qua HTTP.

```powershell
uvicorn src.api.main:app --reload
```

Make:

```powershell
make api
```

Health check:

```text
GET http://localhost:8000/api/health
```

OpenAPI docs:

```text
http://localhost:8000/docs
```

Main endpoints:

```text
GET  /api/symbols
GET  /api/timeframes
GET  /api/candles?symbol=BTC/USDT&timeframe=15m&limit=500
POST /api/data/update
POST /api/features/build
POST /api/signals/generate
GET  /api/signals/history?symbol=BTC/USDT&timeframe=15m
POST /api/backtest/run
GET  /api/backtest/latest?symbol=BTC/USDT&timeframe=15m
GET  /api/model/info
GET  /api/model/calibration
GET  /api/model/registry
GET  /api/model/registry/BTC_USDT/15m
POST /api/model/promote
POST /api/model/archive
POST /api/model/train
GET  /api/risk/status
GET  /api/paper/analytics
GET  /api/paper/drawdown
GET  /api/paper/regime-performance
GET  /api/strategy-memory
GET  /api/strategy-memory/{symbol}/{timeframe}
```

Example signal request:

```json
{
  "symbol": "BTC/USDT",
  "timeframe": "15m",
  "account_balance": 1000,
  "risk_percent": 1
}
```

## Make Commands

```powershell
make install
make collect SYMBOL=BTC/USDT TIMEFRAME=15m
make features SYMBOL=BTC/USDT TIMEFRAME=15m
make train SYMBOL=BTC/USDT TIMEFRAME=15m
make backtest SYMBOL=BTC/USDT TIMEFRAME=15m MODEL=models/model.joblib
make dashboard
make api
make test
make docker-up
make docker-down
```

Docker one-off commands:

```powershell
make docker-collect SYMBOL=BTC/USDT TIMEFRAME=15m
make docker-features SYMBOL=BTC/USDT TIMEFRAME=15m
make docker-train SYMBOL=BTC/USDT TIMEFRAME=15m
make docker-backtest SYMBOL=BTC/USDT TIMEFRAME=15m MODEL=models/model.joblib
make docker-api
make docker-test
```

## Example Signal Output

Strategy selection mặc định vẫn dùng mapping cũ để backward-compatible:

- `UPTREND` / `DOWNTREND` -> `TREND_FOLLOWING`
- `BREAKOUT_UP` / `BREAKOUT_DOWN` -> `BREAKOUT_CONFIRMATION`
- `SIDEWAY` -> `MEAN_REVERSION`

Có thể bật strategy ensemble trong `settings.yaml`:

```yaml
adaptive_strategy:
  enabled: true
  base_threshold: 0.65
  min_opinion_score: 0.55
  conflict_margin: 0.12
```

Khi adaptive strategy được bật, SignalEngine gọi nhiều `StrategyOpinionAgent`, chọn opinion tốt nhất bằng `AdaptiveDecisionEngine`, trả `WAIT` nếu BUY/SELL conflict với margin thấp, tăng threshold khi regime mập mờ/volatility cao, và áp dụng Strategy Memory Feedback nếu một strategy đang thua gần đây.

Dynamic sizing:

```text
final_position_size =
  base_position_size
  * setup_quality_multiplier
  * regime_confidence_multiplier
  * volatility_multiplier
  * memory_performance_multiplier
  * drawdown_multiplier
```

```json
{
  "symbol": "BTC/USDT",
  "timeframe": "15m",
  "timestamp": "2026-01-01T00:00:00+00:00",
  "market_regime": "UPTREND",
  "signal": "BUY",
  "strategy": "TREND_FOLLOWING",
  "confidence": 0.72,
  "probability_source": "calibrated",
  "model_scope_used": "regime_specific",
  "model_version": "v003",
  "fallback_reason": null,
  "raw_probabilities": {
    "BUY": 0.68,
    "SELL": 0.12,
    "WAIT": 0.20
  },
  "calibrated_probabilities": {
    "BUY": 0.72,
    "SELL": 0.10,
    "WAIT": 0.18
  },
  "entry": 65000.0,
  "stop_loss": 64200.0,
  "take_profit_1": 66600.0,
  "take_profit_2": 67400.0,
  "risk_reward": 2.0,
  "base_position_size": 0.024,
  "final_position_size": 0.012,
  "position_size": 0.012,
  "size_multiplier": 0.5,
  "risk_adjustments": [
    {"name": "setup_quality_multiplier", "multiplier": 0.5},
    {"name": "regime_confidence_multiplier", "multiplier": 1.0},
    {"name": "volatility_multiplier", "multiplier": 1.0},
    {"name": "memory_performance_multiplier", "multiplier": 1.0},
    {"name": "drawdown_multiplier", "multiplier": 1.0}
  ],
  "safety_filters": [],
  "blocked_by_risk_guard": false,
  "reasons": [
    "Model BUY probability passed threshold.",
    "Market regime supports trend-following setup.",
    "Risk/reward passed minimum requirement."
  ],
  "risk_notes": []
}
```

`explanation_v2` bổ sung các trường để UI/API giải thích rõ vì sao giảm size hoặc block setup:

- `strategy.memory_adjustments`
- `risk.risk_adjustments`
- `risk.safety_filters`
- `risk.mean_reversion_danger_score`
- `risk.breakout_fakeout_score`
- `risk.final_risk_decision`

## Backtest Metrics

Backtesting chạy theo từng candle và không mở nhiều lệnh cùng lúc trong MVP.

Các giả định chính:

- Signal được tạo tại candle close.
- Mô phỏng entry/exit từ candle tiếp theo.
- Nếu cùng một candle chạm cả TP và SL, conservative mode tính SL trước.
- Fee/slippage/spread được mô phỏng qua execution cost model trong `settings.yaml`.
- Sau một lệnh thua, hệ thống chờ cooldown trước khi vào lệnh mới.

Metrics:

| Metric | Meaning |
| --- | --- |
| `total_trades` | Tổng số lệnh đã đóng trong backtest. |
| `winrate` | Tỷ lệ lệnh thắng trên tổng số lệnh. |
| `gross_profit` | Tổng PnL dương trước khi trừ tổng loss. |
| `gross_loss` | Tổng giá trị tuyệt đối của các lệnh thua. |
| `net_profit` | Tổng PnL sau fee. |
| `profit_factor` | `gross_profit / gross_loss`. |
| `max_drawdown` | Mức sụt giảm lớn nhất của equity curve theo trade PnL. |
| `average_win` | PnL trung bình của lệnh thắng. |
| `average_loss` | Loss trung bình của lệnh thua. |
| `expectancy` | PnL kỳ vọng trung bình trên mỗi lệnh. |
| `average_risk_reward` | Risk/reward trung bình của các setup đã vào lệnh. |
| `longest_win_streak` | Chuỗi thắng dài nhất. |
| `longest_loss_streak` | Chuỗi thua dài nhất. |

Outputs:

- Trades CSV trong `data/backtest/`.
- Summary JSON trong `data/backtest/`.
- Full JSON và HTML report trong `data/backtest/`.
- `BacktestReport` object dùng cho dashboard.

Execution cost config:

```yaml
backtest:
  execution_cost:
    model: fixed  # fixed | volatility_adjusted | spread_aware | stress
    fee_rate: 0.001
    base_slippage_rate: 0.0005
    stress_multiplier: 3.0
    max_slippage_rate: 0.01
```

## Dashboard

Streamlit dashboard gồm các tab:

- `Market`: candlestick chart, EMA, volume, RSI, market regime.
- `Signal`: signal card, confidence, entry, stop loss, take profit, risk/reward, position size, reasons, và top positive/negative model factors khi có model explainability.
- `Signal`: hiển thị thêm adaptive threshold, setup quality, memory adjustments, safety filters và final risk decision khi có `explanation_v2`.
- `Backtest`: metrics cards, equity curve, trade history.
- `Model`: model type, trained time, feature count, calibration metrics, feature importance và explainability notes.
- `History`: lịch sử signal local với filter.
- `Paper Trading`: balance, equity, open positions, closed trades và equity curve mô phỏng.
- `Paper Trading`: analytics theo regime/strategy, drawdown curve và dữ liệu strategy memory dùng cho adaptive decisions.

Empty states được xử lý rõ ràng:

```text
No data found. Please update market data first.
No model found. Please train a model first.
```

### React Frontend

Ngoài Streamlit dashboard, dự án có frontend React + TypeScript trong `frontend/` để dùng với FastAPI backend.

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Default URLs:

- FastAPI backend: `http://localhost:8000`
- React frontend: `http://localhost:5173`

Nếu backend chạy ở host/port khác, cập nhật `VITE_API_BASE_URL` trong `frontend/.env`.

## Screenshots

> Placeholder for GitHub screenshots.

Recommended screenshots:

- Dashboard Market tab.
- Signal card with BUY/SELL/WAIT setup.
- Backtest report and equity curve.
- Model metadata and metrics.

## Testing

```powershell
pytest
```

Test coverage tập trung vào:

- Candle validation và SQLite de-duplication.
- Feature engineering không mutate input và không leak future data.
- Market regime detection.
- TP/SL first-touch labeling.
- Risk manager.
- Dynamic position sizing, safety filters, RiskGuard và Strategy Memory Feedback.
- Signal engine.
- Backtester TP/SL, fee, slippage, drawdown, winrate và no-overlap position.

## Performance Notes

Các tối ưu hiện tại giữ ở mức đơn giản, dễ maintain:

- SQLite indexes cho `symbol`, `timeframe`, `timestamp`, và `(symbol, timeframe, timestamp)`.
- Batch insert candles bằng `executemany` với `INSERT OR IGNORE`.
- Feature cache dựa trên `symbol`, `timeframe`, row count và latest timestamp.
- Dashboard cache qua Streamlit và service-level cache.
- Backtester precompute probabilities và dùng batch `predict_proba` khi provider hỗ trợ.
- Log summary timing thay vì log từng candle trong loop lớn.

## Explainable AI

Khi dashboard tạo signal bằng model ML đã train, hệ thống cố gắng giải thích prediction theo thứ tự:

1. Dùng SHAP `TreeExplainer` nếu package `shap` được cài và model tương thích.
2. Nếu SHAP không khả dụng hoặc lỗi, fallback sang `feature_importances_` của model.
3. Nếu model không expose feature importance, dashboard hiển thị empty state thay vì crash.

Output explainability gồm:

- `top_positive_factors`: các feature hỗ trợ mạnh nhất cho class đang xét.
- `top_negative_factors`: các feature có tác động ngược chiều.
- `summary`: giải thích ngắn, dễ đọc cho dashboard.

SHAP là dependency optional để tránh làm Docker image và setup local nặng hơn mức cần thiết.

## Telegram Alerts

Telegram alert là optional và mặc định tắt trong `src/config/settings.yaml`.

Alert chỉ được gửi khi:

- Signal là `BUY` hoặc `SELL`.
- `confidence` lớn hơn hoặc bằng `notification.min_confidence`.
- `risk_reward` lớn hơn hoặc bằng `notification.min_risk_reward`.
- Symbol/timeframe không nằm trong cooldown.

Message gồm symbol, timeframe, signal, confidence, strategy, entry, stop loss, take profit, risk/reward và reasons. Nếu Telegram API lỗi hoặc thiếu token/chat id, app chỉ ghi log warning và tiếp tục chạy.

## Paper Trading Mode

Paper Trading Mode là mô phỏng local, không gửi lệnh thật tới exchange hoặc broker.

Khi bật `paper_trading.enabled`, dashboard sẽ:

1. Generate signal bằng pipeline hiện tại.
2. Nếu signal là `BUY` hoặc `SELL`, risk hợp lệ, và chưa có vị thế mở, hệ thống mở một paper trade.
3. Với candle mới, engine kiểm tra conservative TP/SL và đóng paper trade nếu chạm.
4. Lưu lịch sử vào SQLite trong `paper_trades`.
5. Lưu account snapshots vào `paper_account_snapshots`.

Dashboard tab `Paper Trading` hiển thị:

- Balance.
- Equity.
- Realized PnL.
- Unrealized PnL.
- Drawdown.
- Open positions.
- Closed trades.
- Paper equity curve.

Sau khi một paper trade đóng, hệ thống cập nhật Strategy Memory snapshot trong local JSON store.
Memory được nhóm theo `symbol`, `timeframe`, `strategy_type`, `regime`, `direction` và gồm:

- `recent_trades_count`
- `recent_winrate`
- `recent_profit_factor`
- `recent_expectancy`
- `recent_drawdown`
- `consecutive_losses`
- `average_r_multiple`
- `fakeout_count`
- `timeout_count`

AdaptiveDecisionEngine dùng memory này để giảm strategy score, tăng threshold, giảm size hoặc block strategy khi hiệu suất gần đây xấu. Memory chỉ can thiệp sau `adaptive_strategy.memory_min_trades_required` để tránh overfit quá nhanh.

Paper mode chỉ phục vụ kiểm thử workflow realtime và quản trị rủi ro giả lập. Nó không đặt lệnh thật và không nên được hiểu là paper broker đầy đủ.

Benchmark synthetic:

```powershell
python scripts/benchmark_pipeline.py --rows 5000
```

## Roadmap

- Advanced SHAP visualizations.
- Telegram alert templates and richer notification channels.
- Paper trading controls, reset/account management and richer strategy memory analytics.
- Portfolio mode.
- More data sources: Yahoo Finance, MT5, CSV.
- PostgreSQL support.
- Experiment tracking.

## CV Bullets

- Built a local-first quantitative research assistant in Python that collects OHLCV data, engineers technical indicators, detects market regimes, trains ML classifiers, and generates risk-aware BUY/SELL/WAIT trade setup recommendations.
- Designed a modular architecture with SQLite persistence, pandas feature pipelines, ML training, strategy memory feedback, backtesting, Streamlit dashboard, Docker deployment, and pytest coverage for core trading logic.
- Implemented conservative backtesting with fees, slippage, cooldown, TP/SL simulation, drawdown metrics, and safeguards to avoid automated real-money trading.
- Added adaptive risk controls with dynamic position sizing, mean-reversion danger filters, breakout fakeout defense, RiskGuard, and circuit breaker logic.

## License

MIT License. See [LICENSE](LICENSE).
