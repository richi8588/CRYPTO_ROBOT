import time
import asyncio
import logging

from connectors.bybit_connector import BybitConnector
from strategies.market_maker_strategy import MarketMakerStrategy
from config.settings import MARKET_MAKER_PAIR, MARKET_MAKER_SPREAD, MARKET_MAKER_ORDER_SIZE, MARKET_MAKER_INVENTORY_LIMIT
from utils.logger import log

def setup_trade_logger():
    """Configures and returns a logger for market maker trades."""
    trade_logger = logging.getLogger("MarketMakerTrader")
    trade_logger.setLevel(logging.INFO)
    if trade_logger.hasHandlers():
        return trade_logger
    fh = logging.FileHandler('market_maker_trades.log', mode='a')
    fh.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    trade_logger.addHandler(fh)
    return trade_logger

async def run():
    """Main function to run the market maker bot."""
    log.info("Starting Market Maker Bot...")

    trade_logger = setup_trade_logger()

    # Initialize connector and strategy
    connector = BybitConnector()
    strategy = MarketMakerStrategy(
        connector=connector,
        pair=MARKET_MAKER_PAIR,
        spread=MARKET_MAKER_SPREAD,
        order_size=MARKET_MAKER_ORDER_SIZE,
        inventory_limit=MARKET_MAKER_INVENTORY_LIMIT,
        trade_logger=trade_logger
    )

    while True:
        try:
            # 1. Update inventory
            strategy.update_inventory()

            # 2. Calculate fair price
            fair_price = strategy.get_fair_price()
            if not fair_price:
                log.warning("Could not calculate fair price. Skipping this iteration.")
                await asyncio.sleep(5)
                continue

            # 3. Calculate bid and ask prices
            bid_price, ask_price = strategy.get_bid_ask_prices(fair_price)

            # 4. Place orders
            strategy.place_orders(bid_price, ask_price)

            log.info(f"Placed orders: Bid at {bid_price:.4f}, Ask at {ask_price:.4f}")

            # 5. Wait for the next iteration
            await asyncio.sleep(10) # Adjust the loop frequency as needed

        except Exception as e:
            log.error(f"An error occurred in the main loop: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(run())
