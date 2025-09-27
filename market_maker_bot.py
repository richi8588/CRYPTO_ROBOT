# market_maker_bot.py

import asyncio
import csv
from datetime import datetime
import os

from connectors.bybit_connector import BybitConnector
from strategies.market_maker_strategy import calculate_mm_orders
from config.settings import TRADE_SIZE_USDT, MM_SPREAD_PERCENTAGE

# For this test, we will focus on a single pair
TEST_PAIR = "DOGE/USDT"

# --- Placeholder Balances ---
current_balances = {
    "USDT": 1000.0,
    "DOGE": 5000.0
}

class MarketMakerLogger:
    """Logs the bot's decisions and market state to a CSV file."""
    def __init__(self, pair):
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pair_filename = pair.replace('/', '-')
        self.log_file = f'{log_dir}/mm_decisions_{pair_filename}_{run_timestamp}.csv'
        
        self.fieldnames = [
            'timestamp', 'best_bid', 'best_ask', 'calculated_bid', 'calculated_ask', 'decision'
        ]
        
        with open(self.log_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            writer.writeheader()
        print(f"Logger initialized. Logging decisions to {self.log_file}")

    def log_decision(self, data):
        with open(self.log_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            writer.writerow(data)

# --- Global instances ---
logger = MarketMakerLogger(TEST_PAIR)

async def handle_price_update(exchange, message):
    """Callback function to handle incoming order book updates."""
    try:
        topic = message['topic']
        if TEST_PAIR.replace('/','') not in topic:
            return

        order_book = {'bids': message['data']['b'], 'asks': message['data']['a']}
        best_bid = float(order_book['bids'][0][0])
        best_ask = float(order_book['asks'][0][0])

        orders = calculate_mm_orders(
            order_book,
            current_balances["USDT"],
            current_balances["DOGE"],
            TRADE_SIZE_USDT,
            MM_SPREAD_PERCENTAGE
        )

        log_data = {
            'timestamp': datetime.now().isoformat(),
            'best_bid': best_bid,
            'best_ask': best_ask,
        }

        if orders and 'buy' in orders and 'sell' in orders:
            log_data['calculated_bid'] = orders['buy']['price']
            log_data['calculated_ask'] = orders['sell']['price']
            log_data['decision'] = "PLACE_ORDERS"
            print(f"DECISION: PLACE_ORDERS -> BUY @ {orders['buy']['price']}, SELL @ {orders['sell']['price']}")
        else:
            log_data['calculated_bid'] = None
            log_data['calculated_ask'] = None
            log_data['decision'] = "SPREAD_TOO_TIGHT"
            # To avoid spamming, we can print this less often, but for now it's fine
            # print(f"DECISION: SPREAD_TOO_TIGHT")

        logger.log_decision(log_data)

    except (KeyError, IndexError):
        pass # Ignore malformed messages

async def main():
    print(f"--- Starting Market Maker Bot Simulation for {TEST_PAIR} ---")
    print(f"Target Spread: {MM_SPREAD_PERCENTAGE}% | Trade Size: {TRADE_SIZE_USDT} USDT")
    
    bybit_connector = BybitConnector()
    
    task = asyncio.create_task(
        bybit_connector.start_public_stream([TEST_PAIR], handle_price_update)
    )

    print("\nConnector running. Logging decisions. Press Ctrl+C to stop.")
    await task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
