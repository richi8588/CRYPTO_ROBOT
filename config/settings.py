
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
    'symbol_1': 'ADA',
    'symbol_2': 'LDO'
}

# The exchange to trade on
EXCHANGE = "bybit"

# Number of historical data points to use for calculating the rolling Z-score
Z_SCORE_WINDOW = 200

# Strategy Parameters - Tuned based on Phase 2 backtesting
ENTRY_Z_SCORE = 1.0 # Enter when Z-score crosses this threshold
EXIT_Z_SCORE = 0.0  # Exit when Z-score crosses back towards zero
STOP_LOSS_Z_SCORE = 3.0 # Exit if spread diverges too far

# Financial Parameters
TRADE_CAPITAL_USD = 1000.0 # Total capital to use for the strategy

# Exchange Fee Configuration
TAKER_FEE = 0.001  # 0.1% fee per leg (buy or sell)
