# analysis/market_maker_analysis.py

import pandas as pd
import numpy as np
import glob
import os

def analyze_market_maker_logs():
    """Finds the latest market maker log and analyzes it."""
    try:
        # Find the latest log file for DOGE
        list_of_files = glob.glob('logs/mm_decisions_DOGE-USDT_*.csv')
        if not list_of_files:
            print("No log files found to analyze.")
            return
        
        latest_file = max(list_of_files, key=os.path.getctime)
        print(f"Analyzing latest log file: {latest_file}\n")
        df = pd.read_csv(latest_file)

    except FileNotFoundError:
        print(f"Error: Could not find the log file.")
        return
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return

    if df.empty:
        print("Log file is empty. No data to analyze.")
        return

    df['timestamp'] = pd.to_datetime(df['timestamp'])

    duration_seconds = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).total_seconds()
    total_ticks = len(df)
    
    place_orders_df = df[df['decision'] == 'PLACE_ORDERS'].copy()
    num_place_orders = len(place_orders_df)
    
    percent_tradeable = (num_place_orders / total_ticks) * 100 if total_ticks > 0 else 0
    
    # Market spread (as percentage of ask price)
    market_spread_pct = ((df['best_ask'] - df['best_bid']) / df['best_ask']) * 100
    avg_market_spread_pct = market_spread_pct.mean()

    # Our target spread (as percentage of our ask price)
    if num_place_orders > 0:
        our_spread_pct = ((place_orders_df['calculated_ask'] - place_orders_df['calculated_bid']) / place_orders_df['calculated_ask']) * 100
        avg_our_spread_pct = our_spread_pct.mean()
    else:
        avg_our_spread_pct = float('nan')
    
    print("--- Market Maker Log Analysis ---")
    print(f"Logging Duration: {duration_seconds / 60:.2f} minutes")
    print(f"Total Price Ticks: {total_ticks}")
    print("-" * 35)
    print(f"Tradeable Ticks ('PLACE_ORDERS'): {num_place_orders} ({percent_tradeable:.2f}%)")
    print(f"Non-Tradeable Ticks: {total_ticks - num_place_orders}")
    print("-" * 35)
    print(f"Average Market Spread: {avg_market_spread_pct:.4f}%" if not np.isnan(avg_market_spread_pct) else "Average Market Spread: N/A")
    print(f"Average Target Spread (Our Bot): {avg_our_spread_pct:.4f}%" if not np.isnan(avg_our_spread_pct) else "Average Target Spread (Our Bot): N/A")
    print("--- End of Analysis ---")

if __name__ == "__main__":
    analyze_market_maker_logs()
