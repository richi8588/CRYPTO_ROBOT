import pandas as pd
import numpy as np
from decimal import Decimal

from analysis.pair_finder import get_historical_prices
from config.settings import MARKET_MAKER_PAIR, MARKET_MAKER_ORDER_SIZE, MARKET_MAKER_INVENTORY_LIMIT, TAKER_FEE
from utils.logger import log

def run_market_maker_backtest(spread):
    """Runs a backtest for the market making strategy."""
    log.info(f"--- Starting Market Maker Backtest for {MARKET_MAKER_PAIR} with spread {spread} ---")

    # 1. Load Data
    pair_base = MARKET_MAKER_PAIR.split('-')[0]
    df = get_historical_prices(pair_base, "60", 8760)
    if df is None or df.empty:
        log.error("Could not load historical data. Exiting backtest.")
        return 0

    # 2. Initialize portfolio and strategy parameters
    initial_capital = 1000.0
    capital = initial_capital
    inventory = 0.0
    avg_entry_price = 0.0
    trades = []
    pnl_history = []

    # 3. Run Simulation Loop
    for i in range(1, len(df)):
        fair_price = Decimal(df['close'].iloc[i-1])
        
        # Calculate bid and ask prices
        bid_price = fair_price * (Decimal(1) - Decimal(spread))
        ask_price = fair_price * (Decimal(1) + Decimal(spread))

        # Simulate order fills
        # Check if buy order was filled
        if df['low'].iloc[i] < float(bid_price) and inventory < MARKET_MAKER_INVENTORY_LIMIT:
            # Update average entry price
            if inventory >= 0:
                avg_entry_price = (avg_entry_price * inventory + float(bid_price) * MARKET_MAKER_ORDER_SIZE) / (inventory + MARKET_MAKER_ORDER_SIZE)
            inventory += MARKET_MAKER_ORDER_SIZE
            capital -= MARKET_MAKER_ORDER_SIZE * float(bid_price) * (1 + TAKER_FEE)
            trades.append({'type': 'buy', 'price': float(bid_price), 'size': MARKET_MAKER_ORDER_SIZE})
            log.info(f"{df.index[i].date()}: BUY order filled at {bid_price:.2f}")

        # Check if sell order was filled
        if df['high'].iloc[i] > float(ask_price) and inventory > 0:
            pnl = (float(ask_price) - avg_entry_price) * MARKET_MAKER_ORDER_SIZE
            inventory -= MARKET_MAKER_ORDER_SIZE
            capital += MARKET_MAKER_ORDER_SIZE * float(ask_price) * (1 - TAKER_FEE)
            trades.append({'type': 'sell', 'price': float(ask_price), 'size': MARKET_MAKER_ORDER_SIZE, 'pnl': pnl})
            pnl_history.append(pnl)
            log.info(f"{df.index[i].date()}: SELL order filled at {ask_price:.2f}, PnL: {pnl:.2f}")
            # Reset avg_entry_price if inventory is flat
            if inventory == 0:
                avg_entry_price = 0

    # 4. Mark-to-market the final inventory
    last_price = df['close'].iloc[-1]
    final_equity = capital + inventory * last_price
    total_pnl = final_equity - initial_capital

    # 5. Report Performance
    log.info("--- Market Maker Backtest Performance Report ---")
    if not trades:
        log.warning("No trades were executed during the backtest period.")
        return 0

    trade_df = pd.DataFrame(trades)
    buy_trades = trade_df[trade_df['type'] == 'buy']
    sell_trades = trade_df[trade_df['type'] == 'sell']

    log.info(f"Final Equity: {final_equity:.2f} USD")
    log.info(f"Total Net PnL: {total_pnl:.2f} USD")
    log.info(f"Total Trades: {len(trade_df)}")
    log.info(f"Buy Trades: {len(buy_trades)}")
    log.info(f"Sell Trades: {len(sell_trades)}")

    return total_pnl

if __name__ == "__main__":
    from config.settings import MARKET_MAKER_SPREAD
    run_market_maker_backtest(MARKET_MAKER_SPREAD)
