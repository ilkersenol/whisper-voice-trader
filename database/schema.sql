-- ============================================
-- WHISPER VOICE TRADER - DATABASE SCHEMA
-- SQLite 3
-- ============================================

-- ============================================
-- SETTINGS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO settings (key, value) VALUES
    ('app_version', '1.0.0'),
    ('language', 'tr'),
    ('whisper_model', 'base'),
    ('use_gpu', 'true'),
    ('wake_word', 'Whisper'),
    ('active_mode_duration', '15'),
    ('tts_enabled', 'true'),
    ('tts_language', 'turkish'),
    ('default_exchange', 'binance'),
    ('paper_trading', 'true'),
    ('paper_balance', '10000.0'),
    ('default_leverage', '10'),
    ('position_mode', 'one-way'),
    ('default_order_type', 'market'),
    ('max_positions', '5'),
    ('max_position_size_percent', '20.0'),
    ('daily_loss_limit', '500.0'),
    ('theme', 'dark');

CREATE TABLE IF NOT EXISTS exchanges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT 0,
    is_configured BOOLEAN DEFAULT 0,
    environment TEXT DEFAULT 'testnet',
    api_key TEXT,
    secret_key TEXT,
    passphrase TEXT,
    is_connected BOOLEAN DEFAULT 0,
    last_connection_test TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO exchanges (name, is_active) VALUES
    ('binance', 1),
    ('bybit', 0),
    ('kucoin', 0),
    ('mexc', 0),
    ('okx', 0);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    leverage INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    quantity REAL NOT NULL,
    position_value REAL NOT NULL,
    margin REAL NOT NULL,
    unrealized_pnl REAL DEFAULT 0.0,
    realized_pnl REAL DEFAULT 0.0,
    stop_loss REAL,
    take_profit REAL,
    status TEXT DEFAULT 'open',
    is_paper_trade BOOLEAN DEFAULT 1,
    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,
    UNIQUE(exchange, symbol, side, status)
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,
    exchange_order_id TEXT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    type TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL,
    stop_price REAL,
    leverage INTEGER,
    status TEXT DEFAULT 'pending',
    filled_quantity REAL DEFAULT 0.0,
    average_fill_price REAL,
    commission REAL DEFAULT 0.0,
    commission_asset TEXT DEFAULT 'USDT',
    position_id INTEGER,
    is_paper_trade BOOLEAN DEFAULT 1,
    voice_command TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (position_id) REFERENCES positions(id)
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,
    exchange_trade_id TEXT,
    order_id INTEGER NOT NULL,
    position_id INTEGER,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    commission REAL DEFAULT 0.0,
    commission_asset TEXT DEFAULT 'USDT',
    pnl REAL,
    is_paper_trade BOOLEAN DEFAULT 1,
    traded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (position_id) REFERENCES positions(id)
);

CREATE TABLE IF NOT EXISTS voice_commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    phrase TEXT NOT NULL,
    language TEXT DEFAULT 'tr',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO voice_commands (category, phrase, language) VALUES
    ('BUY', 'al', 'tr'),
    ('BUY', 'satin al', 'tr'),
    ('BUY', 'long', 'tr'),
    ('SELL', 'sat', 'tr'),
    ('SELL', 'short', 'tr'),
    ('STOP', 'durdur', 'tr'),
    ('STOP', 'iptal', 'tr');

CREATE TABLE IF NOT EXISTS command_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    keyword TEXT NOT NULL UNIQUE,
    language TEXT DEFAULT 'tr',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO command_keywords (category, keyword, language) VALUES
    ('buy', 'al', 'tr'),
    ('buy', 'satın al', 'tr'),
    ('buy', 'long', 'tr'),
    ('buy', 'longla', 'tr'),
    ('buy', 'aç', 'tr'),
    ('sell', 'sat', 'tr'),
    ('sell', 'short', 'tr'),
    ('sell', 'shortla', 'tr'),
    ('sell', 'kısa', 'tr'),
    ('close', 'kapat', 'tr'),
    ('close', 'çık', 'tr'),
    ('close', 'pozisyon kapat', 'tr'),
    ('stop', 'durdur', 'tr'),
    ('stop', 'iptal', 'tr'),
    ('stop', 'vazgeç', 'tr');

CREATE TABLE IF NOT EXISTS license_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_key TEXT UNIQUE,
    license_type TEXT,
    hardware_id TEXT NOT NULL,
    registered_to TEXT,
    start_date TIMESTAMP,
    expiry_date TIMESTAMP,
    is_active BOOLEAN DEFAULT 0,
    last_validation TIMESTAMP,
    validation_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE UNIQUE NOT NULL,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    total_pnl REAL DEFAULT 0.0,
    total_commission REAL DEFAULT 0.0,
    max_drawdown REAL DEFAULT 0.0,
    is_paper_trading BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_traded_at ON trades(traded_at);
CREATE INDEX IF NOT EXISTS idx_voice_commands_executed_at ON voice_commands(executed_at);
CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats(date);

CREATE TRIGGER IF NOT EXISTS update_settings_timestamp 
    AFTER UPDATE ON settings
BEGIN
    UPDATE settings SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_exchanges_timestamp 
    AFTER UPDATE ON exchanges
BEGIN
    UPDATE exchanges SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_orders_timestamp 
    AFTER UPDATE ON orders
BEGIN
    UPDATE orders SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
