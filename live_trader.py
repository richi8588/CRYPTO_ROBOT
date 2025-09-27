import asyncio
import time
import logging

from connectors.bybit_connector import BybitConnector
from connectors.okx_connector import OKXConnector
from config.settings import (
    ALL_PAIRS, TRIANGULAR_SETS, TRADE_AMOUNT_BASE_CURRENCY, 
    MIN_PROFIT_THRESHOLD, TRADING_FEES
)
from strategies.triangular_arbitrage_strategy import find_triangular_opportunity
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
    """Manages the latest prices for all required pairs on each exchange."""
    def __init__(self, pairs):
        self.prices = {
            'okx': {pair: None for pair in pairs},
            'bybit': {pair: None for pair in pairs}
        }
        log.info("Price Manager initialized for Triangular Arbitrage.")

    def update_price(self, exchange, pair, order_book_data):
        if exchange in self.prices and pair in self.prices[exchange]:
            # Store tuple of (order_book, timestamp)
            self.prices[exchange][pair] = (order_book_data, time.time())

    def get_books_for_triangle(self, exchange, triangle):
        """Fetches the three books required for a triangle, if they all exist."""
        p1, p2, p3 = triangle
        if self.prices[exchange][p1] and self.prices[exchange][p2] and self.prices[exchange][p3]:
            # For now, we ignore staleness for simplicity in the new strategy
            return {
                p1: self.prices[exchange][p1][0],
                p2: self.prices[exchange][p2][0],
                p3: self.prices[exchange][p3][0],
            }
        return None

# --- Global instances ---
price_manager = PriceManager(ALL_PAIRS)

# --- Event Handlers ---

async def handle_update(exchange, message):
    """Generic handler for all exchange messages."""
    try:
        if exchange == 'bybit':
            pair_symbol = message['topic'].split('.')[-1]
            pair = next((p for p in ALL_PAIRS if p.replace('/','') == pair_symbol), None)
            order_book = {'bids': message['data']['b'], 'asks': message['data']['a']}
        elif exchange == 'okx':
            pair_symbol = message['arg']['instId']
            pair = pair_symbol.replace('-', '/')
            order_book = {'bids': message['data'][0]['bids'], 'asks': message['data'][0]['asks']}
        else:
            return

        if pair not in ALL_PAIRS: return
        
        price_manager.update_price(exchange, pair, order_book)
        # Since an update to any pair can complete a triangle, we check all triangles
        await check_for_triangular_arbitrage(exchange)

    except (KeyError, IndexError, TypeError):
        log.warning(f"Malformed message from {exchange}: {message}")

async def check_for_triangular_arbitrage(exchange):
    """Checks for triangular arbitrage opportunities on a specific exchange."""
    for triangle in TRIANGULAR_SETS:
        books = price_manager.get_books_for_triangle(exchange, triangle)
        
        if books:
            log.debug(f"Checking triangle {triangle} on {exchange.upper()}")
            opportunity = find_triangular_opportunity(
                books,
                triangle,
                TRADE_AMOUNT_BASE_CURRENCY,
                TRADING_FEES[exchange]['taker_fee']
            )

            if opportunity and opportunity['profit_pct'] >= MIN_PROFIT_THRESHOLD:
                log_msg = f"TRIANGULAR ARB | Exchange: {exchange.upper()} | Path: {opportunity['path']} | Profit: {opportunity['profit_pct']*100:.4f}%"
                log.info(log_msg)
                paper_trade_log.info(log_msg)

async def periodic_status_update():
    while True:
        await asyncio.sleep(60)
        log.info("Heartbeat: Triangular Arbitrage Bot is running.")

async def main():
    log.info("--- Starting Triangular Arbitrage Bot ---")
    paper_trade_log.info("--- NEW TRIANGULAR ARBITRAGE SESSION ---")
    
    okx = OKXConnector()
    bybit = BybitConnector()

    # Subscribe to all necessary pairs on both exchanges
    log.info(f"Subscribing to pairs on both exchanges: {ALL_PAIRS}")
    tasks = [
        asyncio.create_task(okx.start(ALL_PAIRS, handle_update)),
        asyncio.create_task(bybit.start_public_stream(ALL_PAIRS, handle_update)),
        asyncio.create_task(periodic_status_update())
    ]

    log.info("Connectors running. Waiting for price updates. Press Ctrl+C to stop.")
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot stopped by user.")