# config/settings.py

# It is strongly recommended to use environment variables
# instead of hardcoding keys here.

API_KEYS = {
    'okx': {
        'api_key': 'YOUR_OKX_API_KEY',
        'secret_key': 'YOUR_OKX_SECRET_KEY',
        'passphrase': 'YOUR_OKX_PASSPHRASE',
    },
    'bybit': {
        'api_key': 'YOUR_BYBIT_API_KEY',
        'secret_key': 'YOUR_BYBIT_SECRET_KEY',
    }
}

# Trading pairs for arbitrage
TRADING_PAIRS = ['SOL/USDT', 'MATIC/USDT', 'DOGE/USDT', 'TON/USDT', 'TAC/USDT']

# Arbitrage settings
MIN_PROFIT_THRESHOLD = 0.001  # Minimum profit percentage (e.g., 0.1%) to trigger a trade

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
