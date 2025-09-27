import os

# --- API Key Configuration ---
# It is strongly recommended to use environment variables
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

# --- Triangular Arbitrage Strategy Settings ---

# Define the sets of three pairs that form a triangle.
# The bot will look for opportunities within each of these sets on each exchange.
TRIANGULAR_SETS = [
    # Classic BTC-ETH-USDT Triangle
    ('BTC/USDT', 'ETH/BTC', 'ETH/USDT'),
    # Add other potential triangles here, for example:
    # ('LTC/USDT', 'LTC/BTC', 'BTC/USDT'),
    # ('XRP/USDT', 'XRP/BTC', 'BTC/USDT'),
]

# Automatically create a list of all unique pairs to subscribe to
ALL_PAIRS = list(set(pair for triangle in TRIANGULAR_SETS for pair in triangle))

# The starting amount in the base currency (e.g., USDT) for each arbitrage attempt.
# This is a fixed size for simplicity.
TRADE_AMOUNT_BASE_CURRENCY = 100.0

# Minimum profit percentage to log the opportunity. 
# Set to 0.0 to log any trade that breaks even or is profitable.
MIN_PROFIT_THRESHOLD = 0.0


# --- Exchange Fee Configuration ---
# Taker fees are used as we assume we are taking liquidity from the book.
TRADING_FEES = {
    'okx': {
        'taker_fee': 0.001,  # 0.1%
    },
    'bybit': {
        'taker_fee': 0.001,  # 0.1%
    }
}