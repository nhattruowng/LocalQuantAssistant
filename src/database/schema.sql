CREATE TABLE IF NOT EXISTS setup_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,
    confidence REAL NOT NULL,
    rationale TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, timeframe, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_candles_symbol
ON candles(symbol);

CREATE INDEX IF NOT EXISTS idx_candles_timeframe
ON candles(timeframe);

CREATE INDEX IF NOT EXISTS idx_candles_timestamp
ON candles(timestamp);

CREATE INDEX IF NOT EXISTS idx_candles_symbol_timeframe_timestamp
ON candles(symbol, timeframe, timestamp);

CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    direction TEXT NOT NULL,
    strategy TEXT NOT NULL,
    status TEXT NOT NULL,
    opened_at DATETIME NOT NULL,
    closed_at DATETIME,
    entry REAL NOT NULL,
    stop_loss REAL NOT NULL,
    take_profit_1 REAL NOT NULL,
    take_profit_2 REAL NOT NULL,
    position_size REAL NOT NULL,
    confidence REAL NOT NULL,
    market_regime TEXT DEFAULT 'UNKNOWN',
    exit_price REAL,
    pnl REAL DEFAULT 0,
    result TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_paper_trades_status
ON paper_trades(status);

CREATE INDEX IF NOT EXISTS idx_paper_trades_symbol_timeframe_status
ON paper_trades(symbol, timeframe, status);

CREATE TABLE IF NOT EXISTS paper_account_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    initial_balance REAL NOT NULL,
    current_balance REAL NOT NULL,
    realized_pnl REAL NOT NULL,
    unrealized_pnl REAL NOT NULL,
    equity REAL NOT NULL,
    drawdown REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_paper_account_snapshots_timestamp
ON paper_account_snapshots(timestamp);

CREATE TABLE IF NOT EXISTS risk_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    state TEXT NOT NULL,
    reason TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_risk_events_symbol_timeframe_timestamp
ON risk_events(symbol, timeframe, timestamp);
