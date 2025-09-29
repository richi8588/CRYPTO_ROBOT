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

def run_backtest(params, plot=False):
    """Runs a backtest for the given pair and strategy parameters."""
    
    SYMBOL_1 = params['symbol_1']
    SYMBOL_2 = params['symbol_2']
    TIMEFRAME = params['timeframe']
    HISTORY_LIMIT = params['history_limit']
    REGRESSION_WINDOW = params['regression_window']
    USE_LOG_SPREAD = params['use_log_spread']
    ENTRY_Z_SCORE = params['entry_z_score']
    EXIT_Z_SCORE = params['exit_z_score']
    USE_RISK_BASED_SIZING = params['use_risk_based_sizing']
    MAX_HOLDING_PERIOD = params['max_holding_period']
    STOP_LOSS_Z_SCORE = params['stop_loss_z_score']
    SLIPPAGE_PERCENT = params['slippage_percent']
    INITIAL_CAPITAL = params['initial_capital']
    FEES_PER_TRADE_LEG = params['fees_per_trade_leg']

    log.info(f"--- Starting Advanced Backtest for {SYMBOL_1}-{SYMBOL_2} ---")

    # 1. Load Data
    df1 = get_historical_prices(SYMBOL_1, TIMEFRAME, HISTORY_LIMIT)
    df2 = get_historical_prices(SYMBOL_2, TIMEFRAME, HISTORY_LIMIT)
    if df1 is None or df2 is None: 
        log.error("Could not load data for one or both symbols. Exiting backtest.")
        return 0

    df = pd.DataFrame({SYMBOL_1: df1['close'], SYMBOL_2: df2['close']}).dropna()

    # 2. Initialize columns
    df['z_score'] = np.nan

    # 3. Run Simulation Loop
    position = 0
    trades = []
    capital = INITIAL_CAPITAL
    equity_curve = []

    for i in range(REGRESSION_WINDOW, len(df)):
        window = df.iloc[i - REGRESSION_WINDOW : i]
        
        s1_prices = window[SYMBOL_1]
        s2_prices = window[SYMBOL_2]
        
        if USE_LOG_SPREAD:
            s1_prices = np.log(s1_prices)
            s2_prices = np.log(s2_prices)

        y = s1_prices
        x = sm.add_constant(s2_prices)
        model = sm.OLS(y, x).fit()
        hedge_ratio = model.params.iloc[1]
        
        current_spread = (np.log(df[SYMBOL_1].iloc[i]) if USE_LOG_SPREAD else df[SYMBOL_1].iloc[i]) - \
                         hedge_ratio * (np.log(df[SYMBOL_2].iloc[i]) if USE_LOG_SPREAD else df[SYMBOL_2].iloc[i])
        
        hist_spread = s1_prices - hedge_ratio * s2_prices
        spread_mean = hist_spread.mean()
        spread_std = hist_spread.std()
        
        if spread_std == 0: 
            equity_curve.append(capital)
            continue

        current_z_score = (current_spread - spread_mean) / spread_std
        df.loc[df.index[i], 'z_score'] = current_z_score

        # Entry Logic
        if position == 0:
            if current_z_score < -ENTRY_Z_SCORE:
                position = 1 # Long Spread
                size_multiplier = min(abs(current_z_score) / ENTRY_Z_SCORE, 1.0) if USE_RISK_BASED_SIZING else 1.0
                capital_for_trade = capital * size_multiplier
                qty_s1 = (capital_for_trade / 2) / df[SYMBOL_1].iloc[i]
                qty_s2 = qty_s1 * hedge_ratio
                trades.append({'type': 'long', 'entry_date': df.index[i], 'entry_index': i, 'qty_s1': qty_s1, 'qty_s2': qty_s2})
                log.info(f"{df.index[i].date()}: ENTER LONG at Z={current_z_score:.2f} (Size: {size_multiplier*100:.0f}%)")
            elif current_z_score > ENTRY_Z_SCORE:
                position = -1 # Short Spread
                size_multiplier = min(abs(current_z_score) / ENTRY_Z_SCORE, 1.0) if USE_RISK_BASED_SIZING else 1.0
                capital_for_trade = capital * size_multiplier
                qty_s1 = (capital_for_trade / 2) / df[SYMBOL_1].iloc[i]
                qty_s2 = qty_s1 * hedge_ratio
                trades.append({'type': 'short', 'entry_date': df.index[i], 'entry_index': i, 'qty_s1': qty_s1, 'qty_s2': qty_s2})
                log.info(f"{df.index[i].date()}: ENTER SHORT at Z={current_z_score:.2f} (Size: {size_multiplier*100:.0f}%)")
        
        # Exit Logic
        elif (position == 1 and (current_z_score >= -EXIT_Z_SCORE or current_z_score < -STOP_LOSS_Z_SCORE or (i - trades[-1]['entry_index']) > MAX_HOLDING_PERIOD)) or \
             (position == -1 and (current_z_score <= EXIT_Z_SCORE or current_z_score > STOP_LOSS_Z_SCORE or (i - trades[-1]['entry_index']) > MAX_HOLDING_PERIOD)):
            
            trade = trades[-1]
            entry_price_s1 = df[SYMBOL_1].iloc[trade['entry_index']]
            entry_price_s2 = df[SYMBOL_2].iloc[trade['entry_index']]
            exit_price_s1 = df[SYMBOL_1].iloc[i]
            exit_price_s2 = df[SYMBOL_2].iloc[i]

            # Apply slippage to exit prices
            exit_price_s1_adj = exit_price_s1 * (1 - SLIPPAGE_PERCENT) if position == 1 else exit_price_s1 * (1 + SLIPPAGE_PERCENT)
            exit_price_s2_adj = exit_price_s2 * (1 + SLIPPAGE_PERCENT) if position == 1 else exit_price_s2 * (1 - SLIPPAGE_PERCENT)

            qty_s1 = trade['qty_s1']
            qty_s2 = trade['qty_s2']

            if position == 1: # Long Spread
                pnl_s1 = (exit_price_s1_adj - entry_price_s1) * qty_s1
                pnl_s2 = (entry_price_s2 - exit_price_s2_adj) * qty_s2
            else: # Short Spread
                pnl_s1 = (entry_price_s1 - exit_price_s1_adj) * qty_s1
                pnl_s2 = (exit_price_s2_adj - entry_price_s2) * qty_s2

            fees = (qty_s1 * entry_price_s1 + qty_s2 * entry_price_s2 + qty_s1 * exit_price_s1 + qty_s2 * exit_price_s2) * FEES_PER_TRADE_LEG
            net_pnl = pnl_s1 + pnl_s2 - fees
            
            capital += net_pnl
            trade.update({'exit_date': df.index[i], 'pnl': net_pnl})
            log.info(f"{df.index[i].date()}: EXIT at Z={current_z_score:.2f}, PnL: {net_pnl:.2f} USD. New Capital: {capital:.2f}")
            position = 0

        equity_curve.append(capital)

    # 4. Report Performance & Plotting
    log.info("--- Advanced Backtest Performance Report ---")
    if not any('pnl' in t for t in trades):
        log.warning("No trades were completed during the backtest period.")
        return 0

    trade_df = pd.DataFrame([t for t in trades if 'pnl' in t])
    wins = trade_df[trade_df['pnl'] > 0]
    losses = trade_df[trade_df['pnl'] <= 0]

    total_net_pnl = trade_df['pnl'].sum()

    log.info(f"Final Capital: {capital:.2f} USD")
    log.info(f"Total Net PnL: {total_net_pnl:.2f} USD")
    log.info(f"Total Trades: {len(trade_df)}")
    log.info(f"Win Rate: {len(wins) / len(trade_df) * 100:.2f}%" if len(trade_df) > 0 else "0.00%")
    log.info(f"Average Win: {wins['pnl'].mean():.2f} USD" if len(wins) > 0 else "0.00")
    log.info(f"Average Loss: {losses['pnl'].mean():.2f} USD" if len(losses) > 0 else "0.00")
    log.info(f"Profit Factor: {abs(wins['pnl'].sum() / losses['pnl'].sum()):.2f}" if len(losses) > 0 and losses['pnl'].sum() != 0 else "inf")

    if plot:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
        df['z_score'].plot(ax=ax1, label='Z-Score')
        ax1.set_title(f'{SYMBOL_1}-{SYMBOL_2} Z-Score and Trades')
        for trade in trade_df.itertuples():
            color = 'green' if trade.pnl > 0 else 'red'
            ax1.axvline(trade.entry_date, color=color, linestyle='--', alpha=0.7)
            ax1.axvline(trade.exit_date, color='black', linestyle=':', alpha=0.7)
        
        equity_df = pd.Series(equity_curve, index=df.index[REGRESSION_WINDOW:])
        equity_df.plot(ax=ax2, label='Equity Curve')
        ax2.set_title('Portfolio Equity Curve')
        ax2.set_ylabel('Capital (USD)')

        plt.tight_layout()
        plot_filename = f'analysis/advanced_backtest_report_{SYMBOL_1}-{SYMBOL_2}.png'
        plt.savefig(plot_filename)
        log.info(f"Backtest report plot saved to {plot_filename}")

    return total_net_pnl

if __name__ == "__main__":
    default_params = {
        'symbol_1': 'DOT',
        'symbol_2': 'DOGE',
        'timeframe': "60",
        'history_limit': 8760,
        'regression_window': 79,
        'use_log_spread': True,
        'entry_z_score': 1.9827451877131854,
        'exit_z_score': -0.14951875191643782,
        'use_risk_based_sizing': True,
        'max_holding_period': 88,
        'stop_loss_z_score': 3.3309970130195627,
        'slippage_percent': 0.0005,
        'initial_capital': 1000.0,
        'fees_per_trade_leg': 0.001
    }
    run_backtest(default_params, plot=True)