import asyncio
import time
import logging

from connectors.bybit_connector import BybitConnector
from connectors.okx_connector import OKXConnector
from config.settings import TRADING_PAIRS
from utils.logger import log

# --- Market State Logger (Black Box) ---
def setup_market_state_logger():
    """Creates a logger to record the top-of-book state for every tick."""
    state_logger = logging.getLogger("MarketState")
    state_logger.setLevel(logging.INFO)
    # Prevent double logging
    if state_logger.hasHandlers():
        return state_logger
    
    file_handler = logging.FileHandler('market_state.log', mode='a')
    # Use a simple formatter for high-volume logging
    file_handler.setFormatter(logging.Formatter('%(asctime)s.%(msecs)03d | %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    state_logger.addHandler(file_handler)
    return state_logger

market_state_log = setup_market_state_logger()

class PriceManager:
    """Manages the latest prices and timestamps for all trading pairs."""
    def __init__(self, pairs):
        # Store a tuple of (order_book, timestamp)
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
        # Call the black box logger immediately
        await log_market_state(pair)

    except (KeyError, IndexError, TypeError):
        log.warning(f"Malformed message from {exchange}: {message}")

async def log_market_state(pair):
    """Black Box Logger: Records the top-of-book for every update."""
    price_data = price_manager.get_prices(pair)
    if not price_data or not price_data['okx'] or not price_data['bybit']:
        return

    okx_book, okx_ts = price_data['okx']
    bybit_book, bybit_ts = price_data['bybit']

    try:
        okx_ask = float(okx_book['asks'][0][0])
        okx_bid = float(okx_book['bids'][0][0])
        bybit_ask = float(bybit_book['asks'][0][0])
        bybit_bid = float(bybit_book['bids'][0][0])

        # Calculate the two potential spreads without fees
        spread_okx_bybit = bybit_bid - okx_ask # Sell Bybit - Buy OKX
        spread_bybit_okx = okx_bid - bybit_ask # Sell OKX - Buy Bybit

        log_msg = f"{pair} | OKX Ask: {okx_ask:<10} | Bybit Bid: {bybit_bid:<10} | Spread: {spread_okx_bybit:<12.5f} || Bybit Ask: {bybit_ask:<10} | OKX Bid: {okx_bid:<10} | Spread: {spread_bybit_okx:<12.5f}"
        market_state_log.info(log_msg)

    except (IndexError, KeyError):
        # This will happen if an order book is momentarily empty
        pass

async def periodic_status_update():
    while True:
        await asyncio.sleep(60)
        log.info("Heartbeat: Bot is running in Black Box Diagnostic Mode.")

async def main():
    log.info("--- Starting Live Paper Trading Bot (BLACK BOX DIAGNOSTIC MODE) ---")
    market_state_log.info("--- NEW BLACK BOX SESSION ---")
    
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