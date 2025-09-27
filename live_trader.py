
import asyncio
import time
from datetime import datetime
from collections import defaultdict, deque
import logging
import numpy as np

from connectors.bybit_connector import BybitConnector
from connectors.okx_connector import OKXConnector
from config.settings import (
    TRADING_PAIRS, TRADING_FEES, MIN_PROFIT_THRESHOLD, TRADE_SIZE_USDT,
    DYNAMIC_THRESHOLD_ENABLED, VOLATILITY_LOOKBACK_PERIOD, VOLATILITY_MULTIPLIER,
    REBALANCE_THRESHOLD_PERCENTAGE, REBALANCE_AMOUNT_PERCENTAGE, MAX_DATA_STALENESS_SECONDS
)
from strategies.arbitrage_strategy import find_depth_aware_opportunity
from utils.logger import log

# --- File-specific logger for paper trades ---
def setup_paper_trade_logger():
    trade_logger = logging.getLogger("PaperTrader")
    trade_logger.setLevel(logging.INFO)
    if trade_logger.hasHandlers():
        return trade_logger
    
    file_handler = logging.FileHandler('paper_trades.log', mode='a')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    trade_logger.addHandler(file_handler)
    return trade_logger

paper_trade_log = setup_paper_trade_logger()

class PriceManager:
    """Manages the latest prices and timestamps for all trading pairs."""
    def __init__(self, pairs):
        # Store a tuple of (order_book, timestamp)
        self.prices = {pair: {'okx': None, 'bybit': None} for pair in pairs}
        self.price_history = {pair: deque(maxlen=VOLATILITY_LOOKBACK_PERIOD) for pair in pairs}
        log.info("Price Manager initialized.")

    def update_price(self, exchange, pair, order_book_data):
        if pair in self.prices:
            self.prices[pair][exchange] = (order_book_data, time.time())
            # Update price history with mid-price for volatility calculation
            if order_book_data.get('bids') and order_book_data.get('asks'):
                best_bid = float(order_book_data['bids'][0][0])
                best_ask = float(order_book_data['asks'][0][0])
                mid_price = (best_bid + best_ask) / 2
                self.price_history[pair].append(mid_price)

    def get_prices(self, pair):
        return self.prices.get(pair)

    def calculate_volatility(self, pair):
        if len(self.price_history[pair]) < 2:
            return 0.0
        prices_arr = np.array(list(self.price_history[pair]))
        if len(prices_arr) < 2: return 0.0
        # Use percentage change for volatility
        returns = np.diff(prices_arr) / prices_arr[:-1]
        return np.std(returns) if len(returns) > 0 else 0.0

class PortfolioSimulator:
    """Simulates asset balances on multiple exchanges."""
    def __init__(self, pairs, initial_usdt=1000.0):
        self.balances = {'okx': defaultdict(float), 'bybit': defaultdict(float)}
        self.pairs = pairs # Store pairs for rebalancing
        for exchange in self.balances.keys():
            self.balances[exchange]['USDT'] = initial_usdt
            for pair in pairs:
                self.balances[exchange][pair.split('/')[0]] = 0.0
        log.info("Portfolio Simulator initialized.")
        self.log_balances()

    def check_and_update_balances(self, opp):
        buy_ex = opp['buy_exchange'].lower()
        sell_ex = opp['sell_exchange'].lower()
        base_asset, quote_asset = opp['pair'].split('/')

        if self.balances[buy_ex][quote_asset] < opp['quote_asset_cost']:
            return False
        if self.balances[sell_ex][base_asset] < opp['base_asset_amount']:
            return False

        self.balances[buy_ex][quote_asset] -= opp['quote_asset_cost']
        self.balances[buy_ex][base_asset] += opp['base_asset_amount']
        self.balances[sell_ex][base_asset] -= opp['base_asset_amount']
        self.balances[sell_ex][quote_asset] += opp['quote_asset_revenue']
        return True

    def log_balances(self):
        log.info("--- Simulated Balances ---")
        for ex, assets in self.balances.items():
            assets_str = ", ".join([f"{amt:.4f} {asset}" for asset, amt in sorted(assets.items())])
            log.info(f"  - {ex.upper()}: {assets_str}")

    def check_and_perform_rebalance(self):
        log.info("Checking for rebalancing opportunities...")
        exchanges = list(self.balances.keys())

        # Rebalance USDT
        total_usdt = sum(self.balances[ex]['USDT'] for ex in exchanges)
        if total_usdt > 0:
            ideal_usdt = total_usdt / len(exchanges)
            if abs(self.balances['okx']['USDT'] - self.balances['bybit']['USDT']) / total_usdt > REBALANCE_THRESHOLD_PERCENTAGE:
                if self.balances['okx']['USDT'] > ideal_usdt:
                    from_ex, to_ex = 'okx', 'bybit'
                else:
                    from_ex, to_ex = 'bybit', 'okx'
                amount_to_move = abs(self.balances[from_ex]['USDT'] - ideal_usdt) * REBALANCE_AMOUNT_PERCENTAGE
                self.balances[from_ex]['USDT'] -= amount_to_move
                self.balances[to_ex]['USDT'] += amount_to_move
                log.info(f"REBALANCE: Moved {amount_to_move:.4f} USDT from {from_ex.upper()} to {to_ex.upper()}")

        # Rebalance Base Assets
        for pair in self.pairs:
            base_asset = pair.split('/')[0]
            total_base = sum(self.balances[ex][base_asset] for ex in exchanges)
            if total_base > 0:
                ideal_base = total_base / len(exchanges)
                if abs(self.balances['okx'][base_asset] - self.balances['bybit'][base_asset]) / total_base > REBALANCE_THRESHOLD_PERCENTAGE:
                    if self.balances['okx'][base_asset] > ideal_base:
                        from_ex, to_ex = 'okx', 'bybit'
                    else:
                        from_ex, to_ex = 'bybit', 'okx'
                    amount_to_move = abs(self.balances[from_ex][base_asset] - ideal_base) * REBALANCE_AMOUNT_PERCENTAGE
                    self.balances[from_ex][base_asset] -= amount_to_move
                    self.balances[to_ex][base_asset] += amount_to_move
                    log.info(f"REBALANCE: Moved {amount_to_move:.4f} {base_asset} from {from_ex.upper()} to {to_ex.upper()}")

# --- Global instances ---
price_manager = PriceManager(TRADING_PAIRS)
portfolio_simulator = PortfolioSimulator(TRADING_PAIRS, initial_usdt=1000.0)

# --- Event Handlers ---

async def handle_update(exchange, message):
    try:
        if exchange == 'bybit':
            pair_symbol = message['topic'].split('.')[-1]
            pair = next((p for p in TRADING_PAIRS if p.replace('/','') == pair_symbol), None)
            order_book = {'bids': message['data']['b'], 'asks': message['data']['a']}
        elif exchange == 'okx':
            pair_symbol = message['arg']['instId']
            pair = pair_symbol.replace('-', '/')
            order_book = {'bids': message['data'][0]['bids'], 'asks': message['data'][0]['asks']}
        else:
            return

        if pair not in TRADING_PAIRS: return
        
        price_manager.update_price(exchange, pair, order_book)
        await check_for_arbitrage(pair)

    except (KeyError, IndexError, TypeError):
        log.warning(f"Malformed message from {exchange}: {message}")

async def check_for_arbitrage(pair):
    price_data = price_manager.get_prices(pair)
    if not price_data or not price_data['okx'] or not price_data['bybit']:
        return

    # --- Staleness Check ---
    okx_book, okx_ts = price_data['okx']
    bybit_book, bybit_ts = price_data['bybit']

    if abs(okx_ts - bybit_ts) > MAX_DATA_STALENESS_SECONDS:
        log.debug(f"Stale data for {pair}, skipping. OKX: {okx_ts:.2f}, Bybit: {bybit_ts:.2f}")
        return

    # --- Performance Optimization: Quick check on top-of-book prices ---
    try:
        okx_best_ask = float(okx_book['asks'][0][0])
        bybit_best_bid = float(bybit_book['bids'][0][0])
        bybit_best_ask = float(bybit_book['asks'][0][0])
        okx_best_bid = float(okx_book['bids'][0][0])

        if not ((okx_best_ask < bybit_best_bid) or (bybit_best_ask < okx_best_bid)):
            return
            
    except (IndexError, KeyError):
        return

    log.debug(f"Potential opportunity for {pair}, running full analysis...")
    opportunity = find_depth_aware_opportunity(
        okx_book, bybit_book, TRADE_SIZE_USDT, TRADING_FEES
    )

    if opportunity:
        if opportunity['buy_exchange'] == 'A':
            opportunity['buy_exchange'] = 'OKX'
            opportunity['sell_exchange'] = 'Bybit'
        else:
            opportunity['buy_exchange'] = 'Bybit'
            opportunity['sell_exchange'] = 'OKX'
        opportunity['pair'] = pair

        current_profit_threshold = MIN_PROFIT_THRESHOLD
        if DYNAMIC_THRESHOLD_ENABLED:
            volatility = price_manager.calculate_volatility(pair)
            if volatility > 0:
                dynamic_threshold_adjustment = volatility * VOLATILITY_MULTIPLIER
                current_profit_threshold = max(MIN_PROFIT_THRESHOLD, MIN_PROFIT_THRESHOLD + dynamic_threshold_adjustment)
                log.debug(f"Dynamic threshold for {pair}: {current_profit_threshold:.6f} (Volatility: {volatility:.6f})")
            else:
                log.debug(f"Volatility for {pair} is zero or insufficient data, using static threshold.")

        if opportunity['profit_percentage'] >= current_profit_threshold:
            profit_usd = opportunity['quote_asset_revenue'] - opportunity['quote_asset_cost']
            trade_info = f"{opportunity['pair']} | Profit: ${profit_usd:.4f} ({opportunity['profit_percentage']*100:.4f}%) | Buy {opportunity['buy_exchange']} / Sell {opportunity['sell_exchange']}"

            if portfolio_simulator.check_and_update_balances(opportunity):
                log.info(f"PAPER TRADE: {trade_info}")
                paper_trade_log.info(f"SUCCESS | {trade_info}")
            else:
                log.warning(f"SKIPPED TRADE (Insufficient Funds): {trade_info}")
                paper_trade_log.warning(f"SKIPPED | {trade_info}")

async def periodic_status_update():
    while True:
        await asyncio.sleep(30)
        log.info("Heartbeat: Bot is running.")
        portfolio_simulator.log_balances()
        portfolio_simulator.check_and_perform_rebalance()

async def main():
    log.info("--- Starting Live Paper Trading Bot (with Portfolio Simulation) ---")
    paper_trade_log.info("--- NEW SESSION ---")
    
    okx = OKXConnector()
    bybit = BybitConnector()

    tasks = [
        asyncio.create_task(okx.start(TRADING_PAIRS, handle_update)),
        asyncio.create_task(bybit.start_public_stream(TRADING_PAIRS, handle_update)),
        asyncio.create_task(periodic_status_update())
    ]

    log.info("Connectors running. Waiting for price updates. Press Ctrl+C to stop.")
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot stopped by user.")
