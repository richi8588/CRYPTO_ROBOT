
import sys
import os
import pandas as pd
import numpy as np
import statsmodels.api as sm
import matplotlib.pyplot as plt

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from analysis.pair_finder import get_historical_prices # Reuse the data fetching function
from utils.logger import log

# --- Configuration ---
# The pair we found in Phase 1
SYMBOL_1 = 'ADA'
SYMBOL_2 = 'LDO'

# Strategy Parameters
ENTRY_Z_SCORE = 2.0
EXIT_Z_SCORE = 0.5
STOP_LOSS_Z_SCORE = 3.0

# --- Backtester --- 

def run_backtest():
    """Runs a backtest for the given pair and strategy parameters."""
    log.info(f"--- Starting Backtest for {SYMBOL_1}-{SYMBOL_2} ---")

    # 1. Load Data
    series1 = get_historical_prices(SYMBOL_1)
    series2 = get_historical_prices(SYMBOL_2)

    if series1 is None or series2 is None:
        log.error("Could not load data for backtest. Exiting.")
        return

    df = pd.DataFrame({SYMBOL_1: series1, SYMBOL_2: series2})
    df.dropna(inplace=True)

    # 2. Calculate Spread and Z-Score
    y = df[SYMBOL_1]
    x = sm.add_constant(df[SYMBOL_2])
    model = sm.OLS(y, x).fit()
    hedge_ratio = model.params[1]
    df['spread'] = df[SYMBOL_1] - hedge_ratio * df[SYMBOL_2]
    df['z_score'] = (df['spread'] - df['spread'].mean()) / df['spread'].std()

    log.info(f"Hedge Ratio: {hedge_ratio:.4f}")

    # 3. Run Trading Simulation
    position = 0 # 0: flat, 1: long spread (long S1, short S2), -1: short spread (short S1, long S2)
    trades = []
    current_pnl = 0
    total_pnl = 0

    for i in range(1, len(df)):
        prev_z = df['z_score'].iloc[i-1]
        curr_z = df['z_score'].iloc[i]

        # Entry Logic
        if position == 0:
            if prev_z < -ENTRY_Z_SCORE and curr_z >= -ENTRY_Z_SCORE:
                position = 1 # Long the spread
                entry_price_s1 = df[SYMBOL_1].iloc[i]
                entry_price_s2 = df[SYMBOL_2].iloc[i]
                trades.append({'type': 'long', 'entry_date': df.index[i], 'entry_price_s1': entry_price_s1, 'entry_price_s2': entry_price_s2})
                log.info(f"{df.index[i].date()}: ENTER LONG SPREAD (Long {SYMBOL_1}, Short {SYMBOL_2}) at Z-Score {curr_z:.2f}")
            elif prev_z > ENTRY_Z_SCORE and curr_z <= ENTRY_Z_SCORE:
                position = -1 # Short the spread
                entry_price_s1 = df[SYMBOL_1].iloc[i]
                entry_price_s2 = df[SYMBOL_2].iloc[i]
                trades.append({'type': 'short', 'entry_date': df.index[i], 'entry_price_s1': entry_price_s1, 'entry_price_s2': entry_price_s2})
                log.info(f"{df.index[i].date()}: ENTER SHORT SPREAD (Short {SYMBOL_1}, Long {SYMBOL_2}) at Z-Score {curr_z:.2f}")
        
        # Exit & Stop-Loss Logic
        elif position == 1: # Currently long the spread
            pnl_s1 = df[SYMBOL_1].iloc[i] - entry_price_s1
            pnl_s2 = -(df[SYMBOL_2].iloc[i] - entry_price_s2) * hedge_ratio
            current_pnl = pnl_s1 + pnl_s2

            if curr_z >= -EXIT_Z_SCORE or curr_z < -STOP_LOSS_Z_SCORE:
                log.info(f"{df.index[i].date()}: EXIT LONG SPREAD at Z-Score {curr_z:.2f}, PnL: {current_pnl:.4f}")
                total_pnl += current_pnl
                trades[-1].update({'exit_date': df.index[i], 'pnl': current_pnl})
                position = 0
                current_pnl = 0

        elif position == -1: # Currently short the spread
            pnl_s1 = -(df[SYMBOL_1].iloc[i] - entry_price_s1)
            pnl_s2 = (df[SYMBOL_2].iloc[i] - entry_price_s2) * hedge_ratio
            current_pnl = pnl_s1 + pnl_s2

            if curr_z <= EXIT_Z_SCORE or curr_z > STOP_LOSS_Z_SCORE:
                log.info(f"{df.index[i].date()}: EXIT SHORT SPREAD at Z-Score {curr_z:.2f}, PnL: {current_pnl:.4f}")
                total_pnl += current_pnl
                trades[-1].update({'exit_date': df.index[i], 'pnl': current_pnl})
                position = 0
                current_pnl = 0

    # 4. Report Performance
    log.info("--- Backtest Performance Report ---")
    if not trades:
        log.warning("No trades were executed during the backtest period.")
        return

    trade_df = pd.DataFrame(trades)
    wins = trade_df[trade_df['pnl'] > 0]
    losses = trade_df[trade_df['pnl'] <= 0]

    log.info(f"Total Net PnL: {trade_df['pnl'].sum():.4f}")
    log.info(f"Total Trades: {len(trade_df)}")
    log.info(f"Win Rate: {len(wins) / len(trade_df) * 100:.2f}%" if len(trade_df) > 0 else "Win Rate: 0.00%")
    log.info(f"Average Win: {wins['pnl'].mean():.4f}" if len(wins) > 0 else "Average Win: 0.0000")
    log.info(f"Average Loss: {losses['pnl'].mean():.4f}" if len(losses) > 0 else "Average Loss: 0.0000")
    log.info(f"Profit Factor: {abs(wins['pnl'].sum() / losses['pnl'].sum()):.2f}" if len(losses) > 0 and losses['pnl'].sum() != 0 else "Profit Factor: inf")

    # 5. Plotting
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    df['z_score'].plot(ax=ax1, label='Z-Score')
    ax1.axhline(ENTRY_Z_SCORE, color='red', linestyle='--')
    ax1.axhline(-ENTRY_Z_SCORE, color='green', linestyle='--')
    ax1.axhline(EXIT_Z_SCORE, color='orange', linestyle=':')
    ax1.axhline(-EXIT_Z_SCORE, color='orange', linestyle=':')
    ax1.set_title(f'{SYMBOL_1}-{SYMBOL_2} Z-Score')

    # Plot trades
    for trade in trades:
        if trade['type'] == 'long':
            ax1.axvline(trade['entry_date'], color='green', linestyle='-', alpha=0.5)
            if 'exit_date' in trade: ax1.axvline(trade['exit_date'], color='black', linestyle='-', alpha=0.5)
        elif trade['type'] == 'short':
            ax1.axvline(trade['entry_date'], color='red', linestyle='-', alpha=0.5)
            if 'exit_date' in trade: ax1.axvline(trade['exit_date'], color='black', linestyle='-', alpha=0.5)

    # Plot equity curve
    trade_df['cumulative_pnl'] = trade_df['pnl'].cumsum()
    trade_df.set_index('exit_date', inplace=True)
    trade_df['cumulative_pnl'].plot(ax=ax2, label='Equity Curve')
    ax2.set_title('Portfolio Equity Curve')
    ax2.set_ylabel('PnL')

    plt.tight_layout()
    plot_filename = f'analysis/backtest_report_{SYMBOL_1}-{SYMBOL_2}.png'
    plt.savefig(plot_filename)
    log.info(f"Backtest report plot saved to {plot_filename}")

if __name__ == "__main__":
    run_backtest()
