import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import itertools
import pandas as pd
import numpy as np
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint
import matplotlib.pyplot as plt
from pybit.unified_trading import HTTP

from utils.logger import log

# --- Configuration ---
# The assets we want to test for pair trading relationships.
# The script will test all unique combinations of these assets against USDT.
SYMBOLS_TO_TEST = ['DOGE', 'SHIB', 'MATIC', 'SOL', 'AVAX', 'DOT', 'ADA']

# Data parameters
TIMEFRAME = "D" # Daily candles
LIMIT = 200 # Number of candles to fetch

# Cointegration test significance level
P_VALUE_THRESHOLD = 0.05

# --- API Session ---
# We use an unauthenticated session as we only need public k-line data
session = HTTP()

def get_historical_prices(symbol):
    """Fetches historical k-line data for a given symbol from Bybit."""
    try:
        log.info(f"Fetching {LIMIT} days of historical data for {symbol}...")
        # SHIB is a special case, its main pair is 1000SHIB/USDT on many exchanges
        # We will try both SHIBUSDT and 1000SHIBUSDT if one fails
        symbol_to_fetch = f"{symbol}USDT"
        if symbol == 'SHIB':
            symbol_to_fetch = '1000SHIBUSDT' # Bybit uses this convention

        response = session.get_kline(
            category="spot",
            symbol=symbol_to_fetch,
            interval=TIMEFRAME,
            limit=LIMIT
        )

        # If the primary symbol fails, try the base symbol (for SHIB)
        if symbol == 'SHIB' and response['retCode'] != 0:
            log.warning("Could not fetch 1000SHIBUSDT, trying SHIBUSDT...")
            symbol_to_fetch = f"{symbol}USDT"
            response = session.get_kline(
                category="spot",
                symbol=symbol_to_fetch,
                interval=TIMEFRAME,
                limit=LIMIT
            )

        if response['retCode'] == 0 and response['result']['list']:
            data = response['result']['list']
            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
            # Fix for FutureWarning: explicitly cast to numeric before using unit='ms'
            df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms')
            df.set_index('timestamp', inplace=True)
            df['close'] = df['close'].astype(float)
            # Bybit returns data in reverse chronological order, so we reverse it back
            return df.iloc[::-1]['close']
        else:
            log.error(f"Could not fetch data for {symbol}: {response['retMsg']}")
            return None
    except Exception as e:
        log.error(f"An error occurred while fetching data for {symbol}: {e}")
        return None

def find_cointegrated_pairs(symbols):
    """Tests all pairs of symbols for cointegration and returns the best one."""
    log.info("--- Finding Cointegrated Pairs ---")
    pairs = list(itertools.combinations(symbols, 2))
    cointegration_results = []

    for pair in pairs:
        symbol1, symbol2 = pair
        
        series1 = get_historical_prices(symbol1)
        series2 = get_historical_prices(symbol2)

        if series1 is None or series2 is None or len(series1) < (LIMIT * 0.9) or len(series2) < (LIMIT * 0.9):
            log.warning(f"Skipping pair {symbol1}-{symbol2} due to insufficient or mismatched data.")
            continue

        # Ensure dataframes are aligned by timestamp
        aligned_series1, aligned_series2 = series1.align(series2, join='inner')

        if len(aligned_series1) < (LIMIT * 0.9):
            log.warning(f"Skipping pair {symbol1}-{symbol2} due to insufficient aligned data.")
            continue

        # Perform the Engle-Granger cointegration test
        score, p_value, _ = coint(aligned_series1, aligned_series2)
        cointegration_results.append({
            'pair': f"{symbol1}-{symbol2}",
            'p_value': p_value
        })
        log.info(f"Pair: {symbol1}-{symbol2}, P-value: {p_value:.4f}")

    if not cointegration_results:
        log.error("No pairs could be tested. Exiting.")
        return None

    # Find the pair with the lowest p-value
    best_pair_result = min(cointegration_results, key=lambda x: x['p_value'])
    
    log.info("--- Cointegration Test Results ---")
    if best_pair_result['p_value'] < P_VALUE_THRESHOLD:
        log.info(f"Best cointegrated pair found: {best_pair_result['pair']} with p-value {best_pair_result['p_value']:.4f}")
        return best_pair_result['pair']
    else:
        log.warning(f"No significantly cointegrated pair found. The best pair was {best_pair_result['pair']} with p-value {best_pair_result['p_value']:.4f}, which is above the threshold of {P_VALUE_THRESHOLD}.")
        return None

def analyze_and_plot_pair(pair_string):
    """Performs a detailed analysis of the best pair and generates plots."""
    log.info(f"--- Analyzing Best Pair: {pair_string} ---")
    symbol1, symbol2 = pair_string.split('-')

    series1 = get_historical_prices(symbol1)
    series2 = get_historical_prices(symbol2)

    if series1 is None or series2 is None:
        return
    
    # Align data before analysis
    series1, series2 = series1.align(series2, join='inner')

    # 1. Calculate spread using linear regression (OLS)
    y = series1
    x = sm.add_constant(series2)
    model = sm.OLS(y, x).fit()
    hedge_ratio = model.params[1]
    spread = series1 - hedge_ratio * series2

    log.info(f"Calculated hedge ratio: {hedge_ratio:.4f}")

    # 2. Calculate Z-score
    mean_spread = spread.mean()
    std_spread = spread.std()
    z_score = (spread - mean_spread) / std_spread

    # 3. Generate Plots
    plt.style.use('seaborn-v0_8-darkgrid')
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

    # Plot 1: Normalized Prices
    (series1 / series1.iloc[0]).plot(ax=ax1, label=symbol1, color='#FFC300')
    (series2 / series2.iloc[0]).plot(ax=ax1, label=symbol2, color='#581845')
    ax1.set_title(f'{symbol1} and {symbol2} Normalized Prices')
    ax1.set_ylabel('Normalized Price')
    ax1.legend()

    # Plot 2: Spread
    spread.plot(ax=ax2, label='Spread', color='#C70039')
    ax2.axhline(mean_spread, color='black', linestyle='--', label='Mean')
    ax2.axhline(mean_spread + std_spread, color='gray', linestyle=':', label='+1 STD')
    ax2.axhline(mean_spread - std_spread, color='gray', linestyle=':', label='-1 STD')
    ax2.axhline(mean_spread + 2 * std_spread, color='dimgray', linestyle=':', label='+2 STD')
    ax2.axhline(mean_spread - 2 * std_spread, color='dimgray', linestyle=':', label='-2 STD')
    ax2.set_title('Price Spread (Cointegration Residuals)')
    ax2.set_ylabel('Spread Value')
    ax2.legend()

    # Plot 3: Z-Score
    z_score.plot(ax=ax3, label='Z-Score', color='#900C3F')
    ax3.axhline(2.0, color='red', linestyle='--', label='Sell Signal (-2 STD)')
    ax3.axhline(-2.0, color='green', linestyle='--', label='Buy Signal (+2 STD)')
    ax3.set_title('Spread Z-Score')
    ax3.set_ylabel('Z-Score')
    ax3.legend()

    plt.tight_layout()
    plot_filename = f'analysis/statarb_analysis_{pair_string}.png'
    plt.savefig(plot_filename)
    log.info(f"Analysis plots saved to {plot_filename}")

if __name__ == "__main__":
    best_pair = find_cointegrated_pairs(SYMBOLS_TO_TEST)
    if best_pair:
        analyze_and_plot_pair(best_pair)
    else:
        log.info("Could not find a suitable pair for statistical arbitrage based on the given symbols and threshold.")