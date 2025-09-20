# backtester.py

import pandas as pd
import numpy as np
import glob
import os

from strategies.arbitrage_strategy import find_arbitrage_opportunity
from config.settings import TRADING_FEES, TRADING_PAIRS

# --- Simulation Parameters ---
INITIAL_BALANCE = 1000.0  # Initial balance in USDT
TRADE_SIZE_USDT = 100.0   # Fixed trade size for each arbitrage

def run_backtest(data_file, min_profit_threshold):
    """
    Runs a backtest simulation for a given data file and profit threshold.
    """
    try:
        df = pd.read_csv(data_file)
        if df.empty:
            return 0, 0.0
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return 0, 0.0

    trade_count = 0
    total_profit = 0.0

    for row in df.itertuples():
        okx_prices = {'bid': row.okx_bid, 'ask': row.okx_ask}
        bybit_prices = {'bid': row.bybit_bid, 'ask': row.bybit_ask}

        opportunity = find_arbitrage_opportunity(okx_prices, bybit_prices, TRADING_FEES)

        if opportunity and opportunity['profit_percentage'] >= min_profit_threshold:
            trade_count += 1
            profit_for_this_trade = TRADE_SIZE_USDT * opportunity['profit_percentage']
            total_profit += profit_for_this_trade

    return trade_count, total_profit

def optimize_for_pair(pair, data_file):
    """
    Runs the backtest across a range of profit thresholds for a single pair.
    """
    print(f"\n--- Optimizing for {pair} ---")
    print(f"Data file: {os.path.basename(data_file)}")
    print("-" * 50)
    print(f"{'Threshold':<12} | {'Trades':<10} | {'Total Profit (USDT)':<20}")
    print("-" * 50)

    thresholds_to_test = np.arange(0.002, 0.0001, -0.0001) # from 0.2% to 0.01%

    best_profit = -1
    best_threshold = 0
    found_any_trades = False

    for threshold in thresholds_to_test:
        trades, profit = run_backtest(data_file, threshold)
        if trades > 0:
            found_any_trades = True
            print(f"{threshold:<12.4f} | {trades:<10} | {profit:<20.4f}")
            if profit > best_profit:
                best_profit = profit
                best_threshold = threshold

    print("-" * 50)
    if best_profit > 0:
        print(f"Optimal Threshold for {pair}: {best_threshold:.4f} ({best_threshold*100:.4f}%) with {best_profit:.4f} USDT profit.")
    else:
        print(f"No profitable opportunities found for {pair} in the tested range.")
    print("-" * 50)

def run_full_optimization():
    """
    Finds the latest data file for each pair and runs optimization.
    """
    print("====== STARTING FULL STRATEGY OPTIMIZATION ======")
    for pair in TRADING_PAIRS:
        pair_filename_pattern = pair.replace('/', '-')
        search_pattern = f'data/price_log_{pair_filename_pattern}_*.csv'
        
        try:
            list_of_files = glob.glob(search_pattern)
            if not list_of_files:
                print(f"\nNo data file found for {pair}. Skipping.")
                continue
            
            latest_file = max(list_of_files, key=os.path.getctime)
            optimize_for_pair(pair, latest_file)

        except Exception as e:
            print(f"An error occurred while processing {pair}: {e}")

    print("\n====== OPTIMIZATION COMPLETE ======")

if __name__ == "__main__":
    run_full_optimization()
