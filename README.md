# LocalQuant Assistant

LocalQuant Assistant is a local-first Python project for recommending trading setups with machine learning. It only returns `BUY`, `SELL`, or `WAIT` suggestions and does not place trades.

## Goals

- Keep domain logic isolated from infrastructure.
- Run locally with SQLite by default.
- Keep configuration in YAML.
- Make data sources, models, strategies, and databases easy to extend later.

## Requirements

- Python 3.11+
- pip

## Setup

```powershell
cd localquant-assistant
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy `.env.example` to `.env` if you want to override defaults.

## Run

```powershell
python main.py
```

The default command loads `src/config/settings.yaml`, initializes a local SQLite database, and prints a sample recommendation.

## Run Market Data Collector

The collector downloads OHLCV candles from Binance through `ccxt` and stores them in local SQLite. Configure defaults in `src/config/settings.yaml`:

```yaml
collector:
  exchange: binance
  symbols: [BTC/USDT, ETH/USDT]
  timeframes: [15m, 1h, 4h]
  candles_limit: 200
  retry_attempts: 3
  retry_delay_seconds: 1.0
```

Install dependencies, then run:

```powershell
python scripts/collect_market_data.py
```

Run one symbol/timeframe:

```powershell
python scripts/collect_market_data.py --symbol BTC/USDT --timeframe 1h
```

Candles are saved to the `candles` table with a unique key on `(symbol, timeframe, timestamp)`, so reruns do not duplicate rows.

## Build Features

After candles are collected, build technical features from SQLite and export them to `data/processed`:

```powershell
python scripts/build_features.py --symbol BTC/USDT --timeframe 1h
```

Use a custom CSV target:

```powershell
python scripts/build_features.py --symbol BTC/USDT --timeframe 1h --output data/processed/btc_1h_features.csv
```

By default, warmup rows with rolling-indicator NaNs are dropped. Keep them for inspection:

```powershell
python scripts/build_features.py --symbol BTC/USDT --timeframe 1h --keep-warmup
```

Feature groups can be enabled or disabled in `src/config/settings.yaml`:

```yaml
feature_toggles:
  price_action: true
  trend: true
  momentum: true
  volatility: true
  volume: true
```

## Train Model

Training uses TP/SL first-touch labels and chronological splits to avoid time-series leakage:

- train: first 70%
- validation: next 15%
- test: final 15%
- no shuffle

Run training from stored candles:

```powershell
python main.py train --symbol BTC/USDT --timeframe 15m
```

The training command:

1. Loads candles from SQLite.
2. Builds features without future data.
3. Generates labels where only the label logic looks ahead.
4. Drops censored tail rows that do not have the full configured lookahead horizon.
5. Trains `XGBoostClassifier` when available, otherwise falls back to `RandomForestClassifier`.
6. Saves the model as `.joblib` and metadata as `.metadata.json` under `models/`.

Label settings live in `src/config/settings.yaml`:

```yaml
labeling:
  lookahead_bars: 10
  stop_loss_atr_multiplier: 1.5
  take_profit_atr_multiplier: 3.0
```

Training settings:

```yaml
training:
  train_ratio: 0.70
  validation_ratio: 0.15
  test_ratio: 0.15
  random_state: 42
  n_estimators: 300
  max_depth: null
  model_dir: models
```

Metadata includes symbol, timeframe, trained timestamp, selected feature columns, model type, metrics, confusion matrix, classification report, and feature importance.

## Test

```powershell
pytest
```

## Project Structure

```text
localquant-assistant/
├── data/                  # Local raw, processed, backtest data
├── models/                # Trained model artifacts
├── notebooks/             # Research notebooks
├── src/
│   ├── app/               # Application services and CLI UI
│   ├── agents/            # Deterministic orchestration agents
│   ├── domain/            # Core business entities and rules
│   ├── config/            # YAML config loader and typed settings
│   ├── database/          # Database connections and repositories
│   ├── collector/         # Market data source interfaces
│   ├── features/          # Feature engineering
│   ├── labeling/          # Label generation
│   ├── ml/                # Model interfaces and predictors
│   ├── regime/            # Market regime detection
│   ├── risk/              # Risk checks and sizing helpers
│   ├── signal/            # Signal generation
│   ├── strategy/          # Strategy composition
│   ├── backtest/          # Backtesting components
│   └── utils/             # Shared utilities
└── tests/
```

## Architecture

The code follows a layered style:

- `domain`: business concepts such as `TradingAction`, `MarketSnapshot`, and `SetupRecommendation`.
- `application`: orchestration in `RecommendationService`.
- `infrastructure`: YAML config, logging, SQLite connection, repositories, market data collectors.
- `UI`: CLI entrypoint in `src/app/cli.py` and `main.py`.

SQLite is the default database. PostgreSQL can be added later by implementing the same database/repository interfaces and selecting it from YAML config.

## Data Collector Architecture

Market data collection is interface-based:

- `BaseMarketDataCollector`: collector contract for OHLCV sources.
- `BinanceCollector`: `ccxt` implementation for Binance.
- `CandleRepository`: SQLite persistence with deduplication.
- `MarketDataUpdateService`: coordinates latest timestamp lookup, download, validation, and insert.

The design leaves room for future `YahooFinanceCollector`, `MT5Collector`, or `CsvCollector` implementations without changing downstream services.

## Agent Architecture

LocalQuant Assistant uses deterministic service-style agents. These are plain Python classes with clear responsibilities, not autonomous trading bots. They never place real orders.

Pipeline:

```text
MarketDataAgent
  -> FeatureEngineeringAgent
  -> MarketRegimeAgent
  -> PredictionAgent
  -> StrategyAgent
  -> RiskAgent
  -> SignalDecisionAgent
  -> ExplanationAgent
```

`TradingOrchestratorAgent` coordinates the pipeline and returns a `TradeSetup` object. `AgentContext` carries data between agents, while thresholds and risk parameters come from `src/config/settings.yaml`.

Agents:

- `MarketDataAgent`: validates OHLCV data and calls a local fallback collector when data is missing.
- `FeatureEngineeringAgent`: builds moving average, volatility, breakout, and price action features.
- `MarketRegimeAgent`: classifies `UPTREND`, `DOWNTREND`, `SIDEWAY`, `BREAKOUT_UP`, `BREAKOUT_DOWN`, or `HIGH_VOLATILITY`.
- `PredictionAgent`: loads a configured local model and calls `predict_proba`; without a model, it uses configured fallback probabilities.
- `StrategyAgent`: selects Trend Following, Breakout, or Mean Reversion from the detected regime.
- `RiskAgent`: calculates entry, stop loss, take profit, risk/reward, and position size.
- `SignalDecisionAgent`: approves only `BUY` or `SELL` setups that satisfy confidence and risk/reward thresholds.
- `BacktestAgent`: produces a basic local metric report.
- `ExplanationAgent`: creates a template-based explanation, designed to be replaceable by a local LLM later.

The orchestrator is intentionally conservative: if an agent raises a pipeline error, the final setup becomes `WAIT`.

## Feature Engineering

The feature module is vectorized with pandas and avoids future-data leakage by using trailing `rolling`, `shift`, `diff`, `pct_change`, and `ewm` calculations.

Files:

- `features/price_action.py`: returns, candle body, range, and wick features.
- `features/indicators.py`: EMA, RSI, MACD, ATR, Bollinger, and volume features.
- `features/feature_builder.py`: composes enabled feature groups.
- `features/feature_service.py`: reads candles from SQLite and exports processed CSV files.

## Market Regime Detection

`MarketRegimeDetector` adds market state columns to the feature dataset:

- `market_regime`
- `trend_score`
- `volatility_score`
- `breakout_score`
- `rolling_high_20`
- `rolling_low_20`
- `regime_reason`

Regime logic is rule-based and configurable in `src/config/settings.yaml`:

- `UPTREND`: `ema_20 > ema_50`, `close > ema_20`, and positive `ema_20_slope`.
- `DOWNTREND`: `ema_20 < ema_50`, `close < ema_20`, and negative `ema_20_slope`.
- `SIDEWAY`: narrow EMA spread, low Bollinger width, and low/medium ATR percent.
- `BREAKOUT_UP`: close breaks trailing resistance with volume and ATR confirmation.
- `BREAKOUT_DOWN`: close breaks trailing support with volume and ATR confirmation.
- `HIGH_VOLATILITY`: ATR percent is above the configured trailing percentile.
- `LOW_VOLATILITY`: ATR percent is below the configured trailing percentile.
- `UNKNOWN`: required indicators are missing or no rule matches.

The detector is designed as a signal filter. It helps prevent ML predictions from being used blindly when the market structure does not support the setup.
