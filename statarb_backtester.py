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
ENTRY_Z_SCORE = 1.5
EXIT_Z_SCORE = 0.5
STOP_LOSS_Z_SCORE = 3.0

# Financial Parameters
TRADE_CAPITAL_USD = 1000.0 # Capital allocated per trade
FEES_PER_TRADE_LEG = 0.001 # 0.1% fee per leg (buy or sell)

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
    hedge_ratio = model.params.iloc[1] # Fix for FutureWarning
    df['spread'] = df[SYMBOL_1] - hedge_ratio * df[SYMBOL_2]
    df['z_score'] = (df['spread'] - df['spread'].mean()) / df['spread'].std()

    log.info(f"Hedge Ratio: {hedge_ratio:.4f}")

    # 3. Run Trading Simulation
    position = 0 # 0: flat, 1: long spread (long S1, short S2), -1: short spread (short S1, long S2)
    trades = []
    
    # Track capital for equity curve
    capital_history = [TRADE_CAPITAL_USD]
    current_capital = TRADE_CAPITAL_USD

    for i in range(1, len(df)):
        prev_z = df['z_score'].iloc[i-1]
        curr_z = df['z_score'].iloc[i]

        # Entry Logic
        if position == 0:
            if prev_z < -ENTRY_Z_SCORE and curr_z >= -ENTRY_Z_SCORE: # Long the spread
                position = 1 
                entry_price_s1 = df[SYMBOL_1].iloc[i]
                entry_price_s2 = df[SYMBOL_2].iloc[i]
                
                # Calculate quantities based on half capital for each leg
                qty_s1 = (current_capital / 2) / entry_price_s1
                qty_s2 = ((current_capital / 2) / entry_price_s2) * hedge_ratio # Hedged quantity

                trades.append({'type': 'long', 'entry_date': df.index[i], 
                               'entry_price_s1': entry_price_s1, 'entry_price_s2': entry_price_s2,
                               'qty_s1': qty_s1, 'qty_s2': qty_s2})
                log.info(f"{df.index[i].date()}: ENTER LONG SPREAD (Long {SYMBOL_1}, Short {SYMBOL_2}) at Z-Score {curr_z:.2f}")
            elif prev_z > ENTRY_Z_SCORE and curr_z <= ENTRY_Z_SCORE: # Short the spread
                position = -1 
                entry_price_s1 = df[SYMBOL_1].iloc[i]
                entry_price_s2 = df[SYMBOL_2].iloc[i]

                # Calculate quantities based on half capital for each leg
                qty_s1 = (current_capital / 2) / entry_price_s1
                qty_s2 = ((current_capital / 2) / entry_price_s2) * hedge_ratio # Hedged quantity

                trades.append({'type': 'short', 'entry_date': df.index[i], 
                               'entry_price_s1': entry_price_s1, 'entry_price_s2': entry_price_s2,
                               'qty_s1': qty_s1, 'qty_s2': qty_s2})
                log.info(f"{df.index[i].date()}: ENTER SHORT SPREAD (Short {SYMBOL_1}, Long {SYMBOL_2}) at Z-Score {curr_z:.2f}")
        
        # Exit & Stop-Loss Logic
        elif position == 1: # Currently long the spread
            # Calculate PnL in USD
            exit_price_s1 = df[SYMBOL_1].iloc[i]
            exit_price_s2 = df[SYMBOL_2].iloc[i]
            qty_s1 = trades[-1]['qty_s1']
            qty_s2 = trades[-1]['qty_s2']

            pnl_s1_usd = (exit_price_s1 - trades[-1]['entry_price_s1']) * qty_s1
            pnl_s2_usd = (trades[-1]['entry_price_s2'] - exit_price_s2) * qty_s2 # Short position PnL
            
            # Subtract fees for both entry and exit legs (4 fees total)
            fees_usd = (qty_s1 * trades[-1]['entry_price_s1'] * FEES_PER_TRADE_LEG) + \
                       (qty_s2 * trades[-1]['entry_price_s2'] * FEES_PER_TRADE_LEG) + \
                       (qty_s1 * exit_price_s1 * FEES_PER_TRADE_LEG) + \
                       (qty_s2 * exit_price_s2 * FEES_PER_TRADE_LEG)

            trade_pnl = pnl_s1_usd + pnl_s2_usd - fees_usd

            if curr_z >= -EXIT_Z_SCORE or curr_z < -STOP_LOSS_Z_SCORE:
                current_capital += trade_pnl
                log.info(f"{df.index[i].date()}: EXIT LONG SPREAD at Z-Score {curr_z:.2f}, PnL: {trade_pnl:.4f} USD. New Capital: {current_capital:.4f}")
                trades[-1].update({'exit_date': df.index[i], 'pnl': trade_pnl, 'exit_price_s1': exit_price_s1, 'exit_price_s2': exit_price_s2})
                position = 0

        elif position == -1: # Currently short the spread
            # Calculate PnL in USD
            exit_price_s1 = df[SYMBOL_1].iloc[i]
            exit_price_s2 = df[SYMBOL_2].iloc[i]
            qty_s1 = trades[-1]['qty_s1']
            qty_s2 = trades[-1]['qty_s2']

            pnl_s1_usd = (trades[-1]['entry_price_s1'] - exit_price_s1) * qty_s1 # Short position PnL
            pnl_s2_usd = (exit_price_s2 - trades[-1]['entry_price_s2']) * qty_s2

            # Subtract fees for both entry and exit legs (4 fees total)
            fees_usd = (qty_s1 * trades[-1]['entry_price_s1'] * FEES_PER_TRADE_LEG) + \
                       (qty_s2 * trades[-1]['entry_price_s2'] * FEES_PER_TRADE_LEG) + \
                       (qty_s1 * exit_price_s1 * FEES_PER_TRADE_LEG) + \
                       (qty_s2 * exit_price_s2 * FEES_PER_TRADE_LEG)

            trade_pnl = pnl_s1_usd + pnl_s2_usd - fees_usd

            if curr_z <= EXIT_Z_SCORE or curr_z > STOP_LOSS_Z_SCORE:
                current_capital += trade_pnl
                log.info(f"{df.index[i].date()}: EXIT SHORT SPREAD at Z-Score {curr_z:.2f}, PnL: {trade_pnl:.4f} USD. New Capital: {current_capital:.4f}")
                trades[-1].update({'exit_date': df.index[i], 'pnl': trade_pnl, 'exit_price_s1': exit_price_s1, 'exit_price_s2': exit_price_s2})
                position = 0
        
        capital_history.append(current_capital)

    # 4. Report Performance
    log.info("--- Backtest Performance Report ---")
    if not trades:
        log.warning("No trades were executed during the backtest period.")
        return

    trade_df = pd.DataFrame(trades)
    wins = trade_df[trade_df['pnl'] > 0]
    losses = trade_df[trade_df['pnl'] <= 0]

    log.info(f"Final Capital: {current_capital:.4f} USD")
    log.info(f"Total Net PnL: {trade_df['pnl'].sum():.4f} USD")
    log.info(f"Total Trades: {len(trade_df)}")
    log.info(f"Win Rate: {len(wins) / len(trade_df) * 100:.2f}%" if len(trade_df) > 0 else "Win Rate: 0.00%")
    log.info(f"Average Win: {wins['pnl'].mean():.4f} USD" if len(wins) > 0 else "Average Win: 0.0000 USD")
    log.info(f"Average Loss: {losses['pnl'].mean():.4f} USD" if len(losses) > 0 else "Average Loss: 0.0000 USD")
    log.info(f"Profit Factor: {abs(wins['pnl'].sum() / losses['pnl'].sum()):.2f}" if len(losses) > 0 and losses['pnl'].sum() != 0 else "Profit Factor: inf")

    # 5. Plotting
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    df['z_score'].plot(ax=ax1, label='Z-Score')
    ax1.axhline(ENTRY_Z_SCORE, color='red', linestyle='--')
    ax1.axhline(-ENTRY_Z_SCORE, color='green', linestyle='--')
    ax1.axhline(EXIT_Z_SCORE, color='orange', linestyle=':')
    ax1.axhline(-EXIT_Z_SCORE, color='orange', linestyle=':')
    ax1.set_title(f'{SYMBOL_1}-{SYMBOL_2} Z-Score')
    ax1.autoscale(enable=True, axis='x', tight=True) # Fix UserWarning

    # Plot trades
    for trade in trades:
        if trade['type'] == 'long':
            ax1.axvline(trade['entry_date'], color='green', linestyle='-', alpha=0.5)
            if 'exit_date' in trade: ax1.axvline(trade['exit_date'], color='black', linestyle='-', alpha=0.5)
        elif trade['type'] == 'short':
            ax1.axvline(trade['entry_date'], color='red', linestyle='-', alpha=0.5)
            if 'exit_date' in trade: ax1.axvline(trade['exit_date'], color='black', linestyle='-', alpha=0.5)

    # Plot equity curve
    pd.Series(capital_history, index=df.index).plot(ax=ax2, label='Equity Curve', color='blue')
    ax2.set_title('Portfolio Equity Curve')
    ax2.set_ylabel('Capital (USD)')
    ax2.autoscale(enable=True, axis='x', tight=True) # Fix UserWarning

    plt.tight_layout()
    fig.autofmt_xdate() # Fix UserWarning
    plot_filename = f'analysis/backtest_report_{SYMBOL_1}-{SYMBOL_2}.png'
    plt.savefig(plot_filename)
    log.info(f"Backtest report plot saved to {plot_filename}")

if __name__ == "__main__":
    run_backtest()