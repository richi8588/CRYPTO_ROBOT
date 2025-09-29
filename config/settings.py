import os

# --- API Key Configuration ---
API_KEYS = {
    'bybit': {
        'api_key': os.getenv('BYBIT_API_KEY', 'YOUR_BYBIT_API_KEY'),
        'secret_key': os.getenv('BYBIT_API_SECRET', 'YOUR_BYBIT_API_SECRET'),
    }
}

# --- Statistical Arbitrage Strategy Settings ---

# The pair to trade, identified in Phase 1
PAIR = {
    'symbol_1': 'DOT',
    'symbol_2': 'DOGE'
}

# The exchange to trade on
EXCHANGE = "bybit"

# Number of historical data points (candles) to use for calculating the rolling Z-score
Z_SCORE_WINDOW = 79
TIMEFRAME = "60" # 1-hour candles. Must match the timeframe used in analysis

# Strategy Parameters - Start with a standard baseline
ENTRY_Z_SCORE = 1.9827451877131854 # Enter when Z-score crosses this threshold
EXIT_Z_SCORE = -0.14951875191643782  # Exit when Z-score crosses back towards zero
STOP_LOSS_Z_SCORE = 3.3309970130195627 # Exit if spread diverges too far

# Financial Parameters
TRADE_CAPITAL_USD = 1000.0 # Total capital to use for the strategy

# Exchange Fee Configuration
TAKER_FEE = 0.001  # 0.1% fee per leg (buy or sell)

# --- Market Maker Strategy Settings ---
MARKET_MAKER_PAIR = 'BTC-USDT'
MARKET_MAKER_SPREAD = 0.005983751863027161 # The desired spread (0.6%)
MARKET_MAKER_ORDER_SIZE = 0.01 # The size of the buy and sell orders
MARKET_MAKER_INVENTORY_LIMIT = 0.1 # The maximum inventory of the base asset to hold