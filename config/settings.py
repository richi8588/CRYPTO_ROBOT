# config/settings.py

import os

# It is strongly recommended to use environment variables
# instead of hardcoding keys here.

API_KEYS = {
    'okx': {
        'api_key': os.getenv('OKX_API_KEY', 'YOUR_OKX_API_KEY'),
        'secret_key': os.getenv('OKX_SECRET_KEY', 'YOUR_OKX_SECRET_KEY'),
        'passphrase': os.getenv('OKX_PASSPHRASE', 'YOUR_OKX_PASSPHRASE'),
    },
    'bybit': {
        'api_key': os.getenv('BYBIT_API_KEY', 'YOUR_BYBIT_API_KEY'),
        'secret_key': os.getenv('BYBIT_API_SECRET', 'YOUR_BYBIT_API_SECRET'),
    }
}

# Trading pairs for arbitrage
TRADING_PAIRS = ['SOL/USDT', 'MATIC/USDT', 'DOGE/USDT', 'TON/USDT', 'TAC/USDT']

# Arbitrage settings
MIN_PROFIT_THRESHOLD = 0.0005  # Minimum profit percentage (e.g., 0.05%) to trigger a trade
TRADE_SIZE_USDT = 100.0 # The amount in USDT to use for each trade calculation

# --- Market Maker Settings ---
MM_SPREAD_PERCENTAGE = 0.08 # Target spread percentage (e.g., 0.08%) to capture

# Exchange Fees (Taker fees are typically used for market orders in arbitrage)
TRADING_FEES = {
    'okx': {
        'taker_fee': 0.001,  # 0.1%
        'maker_fee': 0.0008  # 0.08%
    },
    'bybit': {
        'taker_fee': 0.001,  # 0.1%
        'maker_fee': 0.001   # 0.1%
    }
}

# Dynamic Threshold Settings
DYNAMIC_THRESHOLD_ENABLED = True
VOLATILITY_LOOKBACK_PERIOD = 60 # seconds
VOLATILITY_MULTIPLIER = 2.0 # Multiplier for volatility to add to min profit threshold

# Rebalancing Settings (for simulation)
REBALANCE_THRESHOLD_PERCENTAGE = 0.20 # If an asset balance deviates by more than 20% from ideal, trigger rebalance
REBALANCE_AMOUNT_PERCENTAGE = 0.50 # Move 50% of the excess amount during rebalance

# Data Staleness Settings
MAX_DATA_STALENESS_SECONDS = 0.5 # Maximum time difference between two order books to be considered valid

