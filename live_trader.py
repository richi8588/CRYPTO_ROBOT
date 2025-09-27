
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
        self.prices = {pair: {'okx': None, 'bybit': None} for pair in pairs}
        log.info("Price Manager initialized.")

    def update_price(self, exchange, pair, order_book_data):
        if pair in self.prices:
            self.prices[pair][exchange] = (order_book_data, time.time())

    def get_prices(self, pair):
        return self.prices.get(pair)

# --- Global instances ---
price_manager = PriceManager(TRADING_PAIRS)

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
    """Diagnostic Mode: Finds and logs every potential opportunity, regardless of profitability."""
    price_data = price_manager.get_prices(pair)
    if not price_data or not price_data['okx'] or not price_data['bybit']:
        return

    # --- Staleness Check ---
    okx_book, okx_ts = price_data['okx']
    bybit_book, bybit_ts = price_data['bybit']

    if abs(okx_ts - bybit_ts) > MAX_DATA_STALENESS_SECONDS:
        return # Skip stale data silently in diagnostic mode

    # --- Quick check for any crossed market ---
    try:
        okx_best_ask = float(okx_book['asks'][0][0])
        bybit_best_bid = float(bybit_book['bids'][0][0])
        bybit_best_ask = float(bybit_book['asks'][0][0])
        okx_best_bid = float(okx_book['bids'][0][0])

        is_crossed = (okx_best_ask < bybit_best_bid) or (bybit_best_ask < okx_best_bid)
        if not is_crossed:
            return
            
    except (IndexError, KeyError):
        return

    # --- Log every crossed market opportunity ---
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

        profit_usd = opportunity['quote_asset_revenue'] - opportunity['quote_asset_cost']
        trade_info = f"{opportunity['pair']} | Profit: ${profit_usd:.4f} ({opportunity['profit_percentage']*100:.4f}%) | Buy {opportunity['buy_exchange']}@~{opportunity['buy_price']:.4f} / Sell {opportunity['sell_exchange']}@~{opportunity['sell_price']:.4f}"

        # Log all found opportunities to the trade log
        paper_trade_log.info(f"MARKET_SCAN | {trade_info}")
        
        # Also log to main console for real-time view
        if opportunity['profit_percentage'] > 0:
            log.info(f"Profitable opportunity found: {trade_info}")
        else:
            log.debug(f"Unprofitable opportunity found: {trade_info}")

async def periodic_status_update():
    while True:
        await asyncio.sleep(60)
        log.info("Heartbeat: Bot is running in Diagnostic Mode.")

async def main():
    log.info("--- Starting Live Paper Trading Bot (DIAGNOSTIC MODE) ---")
    paper_trade_log.info("--- NEW DIAGNOSTIC SESSION ---")
    
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
