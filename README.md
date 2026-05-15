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
