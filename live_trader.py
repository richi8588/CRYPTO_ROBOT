import asyncio
import time
import logging
import pandas as pd
import numpy as np
import statsmodels.api as sm
from pybit.unified_trading import HTTP

from utils.logger import log
from config.settings import (
    PAIR, EXCHANGE, Z_SCORE_WINDOW, TIMEFRAME, ENTRY_Z_SCORE, 
    EXIT_Z_SCORE, STOP_LOSS_Z_SCORE, TRADE_CAPITAL_USD, TAKER_FEE
)

# --- Logger for Trades ---
def setup_paper_trade_logger():
    trade_logger = logging.getLogger("PaperTrader")
    trade_logger.setLevel(logging.INFO)
    if trade_logger.hasHandlers(): return trade_logger
    fh = logging.FileHandler('paper_trades.log', mode='a')
    fh.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    trade_logger.addHandler(fh)
    return trade_logger

paper_trade_log = setup_paper_trade_logger()

# --- Data and Strategy Calculation ---
class StrategyManager:
    def __init__(self, s1, s2, window, timeframe):
        self.s1 = s1
        self.s2 = s2
        self.window = window
        self.timeframe = timeframe
        self.history_df = pd.DataFrame(columns=[self.s1, self.s2])
        self.hedge_ratio = 1.0
        self.latest_z_score = 0.0
        self.api_session = HTTP()

    def get_historical_prices(self, symbol):
        log.info(f"Fetching {self.window} candles of {self.timeframe} data for {symbol}...")
        
        # --- Attempt 1: Primary Symbol (e.g., 1000PEPEUSDT) ---
        symbol_to_fetch = f"{symbol}USDT"
        if symbol in ['PEPE', 'SHIB']: # Add other special tickers here if needed
            symbol_to_fetch = f"1000{symbol}USDT"
        
        try:
            response = self.api_session.get_kline(
                category="spot", symbol=symbol_to_fetch, interval=self.timeframe, limit=self.window)
            if response['retCode'] == 0 and response['result']['list']:
                data = response['result']['list']
                df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
                df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms')
                df.set_index('timestamp', inplace=True)
                df['close'] = df['close'].astype(float)
                if '1000' in symbol_to_fetch:
                    df['close'] = df['close'] / 1000
                return df.iloc[::-1]['close']
        except Exception as e:
            log.warning(f"Attempt 1 failed for {symbol_to_fetch}: {e}")

        # --- Attempt 2: Fallback Symbol (e.g., PEPEUSDT) ---
        if symbol in ['PEPE', 'SHIB']:
            log.info(f"Falling back to base symbol for {symbol}...")
            symbol_to_fetch = f"{symbol}USDT"
            try:
                response = self.api_session.get_kline(
                    category="spot", symbol=symbol_to_fetch, interval=self.timeframe, limit=self.window)
                if response['retCode'] == 0 and response['result']['list']:
                    data = response['result']['list']
                    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms')
                    df.set_index('timestamp', inplace=True)
                    df['close'] = df['close'].astype(float)
                    return df.iloc[::-1]['close']
            except Exception as e:
                log.error(f"Attempt 2 also failed for {symbol_to_fetch}: {e}")
                return None

        log.error(f"Could not fetch data for {symbol} after all attempts.")
        return None

    def initialize(self):
        log.info("Initializing Strategy Manager with historical data...")
        series1 = self.get_historical_prices(self.s1)
        series2 = self.get_historical_prices(self.s2)
        if series1 is None or series2 is None: 
            log.error("Failed to initialize with historical data.")
            return False
        self.history_df = pd.DataFrame({self.s1: series1, self.s2: series2}).dropna()
        self.recalculate_metrics()
        log.info(f"Initialization complete. Initial Hedge Ratio: {self.hedge_ratio:.4f}, Z-Score: {self.latest_z_score:.4f}")
        return True

    def recalculate_metrics(self):
        y = self.history_df[self.s1]
        x = sm.add_constant(self.history_df[self.s2])
        model = sm.OLS(y, x).fit()
        self.hedge_ratio = model.params.iloc[1]
        spread = self.history_df[self.s1] - self.hedge_ratio * self.history_df[self.s2]
        self.latest_z_score = (spread.iloc[-1] - spread.mean()) / spread.std()

    def update(self, symbol, price):
        # This is a simplified update. A robust implementation would use a proper time series index.
        # For this paper trader, we append and trim, which is sufficient.
        now = pd.to_datetime('now', utc=True)
        if symbol in self.history_df.columns:
            self.history_df.loc[now, symbol] = price
            self.history_df = self.history_df.ffill().iloc[-(self.window*24):] # Keep a buffer
            self.recalculate_metrics()
        return self.latest_z_score

# --- Portfolio and Trade Execution Simulation ---
class PortfolioSimulator:
    def __init__(self, s1, s2, initial_capital):
        self.s1 = s1
        self.s2 = s2
        self.capital = initial_capital
        self.position = 0 # 0: flat, 1: long spread, -1: short spread
        self.entry_prices = {}
        self.quantities = {}
        log.info(f"Portfolio Simulator initialized with {self.capital} USD.")

    def execute_trade(self, trade_type, price_s1, price_s2, hedge_ratio):
        if self.position != 0: return
        self.position = 1 if trade_type == 'long' else -1
        self.entry_prices = {'s1': price_s1, 's2': price_s2}
        
        capital_for_s1 = self.capital / 2
        self.quantities['s1'] = capital_for_s1 / price_s1
        self.quantities['s2'] = self.quantities['s1'] * hedge_ratio

        log_msg = f"EXECUTE PAPER TRADE: ENTER {'LONG' if trade_type == 'long' else 'SHORT'} SPREAD. Long {self.quantities['s1'] if self.position == 1 else self.quantities['s2']:.4f} / Short {self.quantities['s2'] if self.position == 1 else self.quantities['s1']:.4f}"
        log.info(log_msg)
        paper_trade_log.info(log_msg)

    def close_position(self, price_s1, price_s2):
        if self.position == 0: return

        if self.position == 1: # Was long spread (long s1, short s2)
            pnl_s1 = (price_s1 - self.entry_prices['s1']) * self.quantities['s1']
            pnl_s2 = (self.entry_prices['s2'] - price_s2) * self.quantities['s2']
        else: # Was short spread (short s1, long s2)
            pnl_s1 = (self.entry_prices['s1'] - price_s1) * self.quantities['s1']
            pnl_s2 = (price_s2 - self.entry_prices['s2']) * self.quantities['s2']

        # 4 legs of fees: enter s1, enter s2, exit s1, exit s2
        fees = (self.quantities['s1'] * self.entry_prices['s1'] * TAKER_FEE) + \
               (self.quantities['s2'] * self.entry_prices['s2'] * TAKER_FEE) + \
               (self.quantities['s1'] * price_s1 * TAKER_FEE) + \
               (self.quantities['s2'] * price_s2 * TAKER_FEE)

        net_pnl = pnl_s1 + pnl_s2 - fees
        self.capital += net_pnl

        log_msg = f"EXECUTE PAPER TRADE: CLOSE POSITION. PnL: {net_pnl:.2f} USD. New Capital: {self.capital:.2f} USD"
        log.info(log_msg)
        paper_trade_log.info(log_msg)

        self.position = 0
        self.entry_prices = {}
        self.quantities = {}

# --- Main Application ---

class LiveTrader:
    def __init__(self):
        self.s1 = PAIR['symbol_1']
        self.s2 = PAIR['symbol_2']
        self.strategy = StrategyManager(self.s1, self.s2, Z_SCORE_WINDOW, TIMEFRAME)
        self.portfolio = PortfolioSimulator(self.s1, self.s2, TRADE_CAPITAL_USD)
        self.latest_prices = {self.s1: None, self.s2: None}
        self.prev_z_score = 0

    async def handle_update(self, message):
        try:
            data = message['data'][0]
            symbol_usdt = data['s']
            price = float(data['p'])
            
            symbol = symbol_usdt.replace('USDT', '').replace('1000','')
            if symbol == 'PEPE': price = price / 1000

            if symbol not in [self.s1, self.s2]: return

            self.latest_prices[symbol] = price
            if not all(self.latest_prices.values()): return

            curr_z = self.strategy.update(symbol, price)
            log.debug(f"New tick for {symbol}. Z-Score: {curr_z:.4f}")

            if self.portfolio.position == 0:
                if self.prev_z_score < -ENTRY_Z_SCORE and curr_z >= -ENTRY_Z_SCORE:
                    self.portfolio.execute_trade('long', self.latest_prices[self.s1], self.latest_prices[self.s2], self.strategy.hedge_ratio)
                elif self.prev_z_score > ENTRY_Z_SCORE and curr_z <= ENTRY_Z_SCORE:
                    self.portfolio.execute_trade('short', self.latest_prices[self.s1], self.latest_prices[self.s2], self.strategy.hedge_ratio)
            
            elif self.portfolio.position == 1:
                if curr_z >= -EXIT_Z_SCORE or curr_z < -STOP_LOSS_Z_SCORE:
                    self.portfolio.close_position(self.latest_prices[self.s1], self.latest_prices[self.s2])
            
            elif self.portfolio.position == -1:
                if curr_z <= EXIT_Z_SCORE or curr_z > STOP_LOSS_Z_SCORE:
                    self.portfolio.close_position(self.latest_prices[self.s1], self.latest_prices[self.s2])

            self.prev_z_score = curr_z

        except (KeyError, IndexError, TypeError) as e:
            log.warning(f"Error processing message: {e} | Message: {message}")

    async def run(self):
        if not self.strategy.initialize(): return

        from connectors.bybit_connector import BybitConnector
        connector = BybitConnector()
        
        s1_usdt = f"{self.s1}USDT"
        s2_usdt = f"{self.s2}USDT"
        if self.s2 == 'PEPE': s2_usdt = '1000PEPEUSDT'

        symbols_to_subscribe = [s1_usdt, s2_usdt]
        
        log.info(f"Subscribing to public trade stream for {symbols_to_subscribe}")
        await connector.start_public_stream(symbols_to_subscribe, self.handle_update, stream_type="trade")

if __name__ == "__main__":
    trader = LiveTrader()
    try:
        asyncio.run(trader.run())
    except KeyboardInterrupt:
        log.info("Bot stopped by user.")