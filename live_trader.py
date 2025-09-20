# live_trader.py

import asyncio
from datetime import datetime

from connectors.bybit_connector import BybitConnector
from connectors.okx_connector import OKXConnector
from config.settings import TRADING_PAIRS, TRADING_FEES, MIN_PROFIT_THRESHOLD
from strategies.arbitrage_strategy import find_arbitrage_opportunity

class PriceManager:
    """Manages the latest prices for all trading pairs from all exchanges."""
    def __init__(self, pairs):
        self.prices = {pair: {'okx': None, 'bybit': None} for pair in pairs}
        print("Price Manager initialized.")

    def update_price(self, exchange, pair, price_data):
        if pair in self.prices:
            self.prices[pair][exchange] = price_data

    def get_prices(self, pair):
        return self.prices.get(pair)

class PaperTrader:
    """Logs profitable opportunities without executing real trades."""
    def __init__(self, log_file='paper_trades.log'):
        self.log_file = log_file
        with open(self.log_file, 'a') as f:
            f.write(f"--- NEW SESSION Started at {datetime.now().isoformat()} ---\n")
        print(f"Paper Trader initialized. Logging to {self.log_file}")

    def log_trade(self, opportunity):
        log_message = f"{datetime.now().isoformat()} | {opportunity['type']} | Profit: {opportunity['profit_percentage']*100:.4f}% | Buy: {opportunity['buy_price']}@{opportunity['buy_exchange']} | Sell: {opportunity['sell_price']}@{opportunity['sell_exchange']}\n"
        print(f"\n!!! PAPER TRADE !!!: {log_message.strip()}")
        with open(self.log_file, 'a') as f:
            f.write(log_message)

# --- Global instances ---
price_manager = PriceManager(TRADING_PAIRS)
paper_trader = PaperTrader()

# --- Exchange-specific Callback Handlers ---

async def handle_bybit_update(exchange, message):
    try:
        topic = message['topic'] # e.g., orderbook.1.SOLUSDT
        pair_symbol = topic.split('.')[-1]
        pair = next((p for p in TRADING_PAIRS if p.replace('/','') == pair_symbol), None)
        if not pair: return

        data = message['data']
        price_data = {'bid': float(data['b'][0][0]), 'ask': float(data['a'][0][0])}
        price_manager.update_price(exchange, pair, price_data)
        await check_for_arbitrage(pair)
    except (KeyError, IndexError): pass

async def handle_okx_update(exchange, message):
    try:
        arg = message['arg']
        pair_symbol = arg['instId'] # e.g., SOL-USDT
        pair = pair_symbol.replace('-', '/')
        if pair not in TRADING_PAIRS: return

        data = message['data'][0]
        price_data = {'bid': float(data['bids'][0][0]), 'ask': float(data['asks'][0][0])}
        price_manager.update_price(exchange, pair, price_data)
        await check_for_arbitrage(pair)
    except (KeyError, IndexError): pass

async def check_for_arbitrage(pair):
    """Checks for an arbitrage opportunity for a given pair."""
    latest_prices = price_manager.get_prices(pair)
    if not latest_prices or not latest_prices['okx'] or not latest_prices['bybit']:
        return

    opportunity = find_arbitrage_opportunity(latest_prices['okx'], latest_prices['bybit'], TRADING_FEES)

    if opportunity and opportunity['profit_percentage'] >= MIN_PROFIT_THRESHOLD:
        paper_trader.log_trade(opportunity)

async def periodic_status_update():
    """Prints a status update to the console periodically."""
    while True:
        await asyncio.sleep(10) # Print status every 10 seconds
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"\n[{now}] Heartbeat: Bot is running.")

        # Display latest prices for the first pair
        first_pair = TRADING_PAIRS[0]
        prices = price_manager.get_prices(first_pair)
        if prices:
            okx_price = prices['okx']['ask'] if prices.get('okx') and prices['okx'] else 'N/A'
            bybit_price = prices['bybit']['ask'] if prices.get('bybit') and prices['bybit'] else 'N/A'
            print(f"  - Last {first_pair}: OKX: {okx_price}, Bybit: {bybit_price}")

        # Also display prices for TON/USDT if it's not the first pair
        ton_pair = 'TON/USDT'
        if ton_pair in TRADING_PAIRS and ton_pair != first_pair:
            prices_ton = price_manager.get_prices(ton_pair)
            if prices_ton:
                okx_price_ton = prices_ton['okx']['ask'] if prices_ton.get('okx') and prices_ton['okx'] else 'N/A'
                bybit_price_ton = prices_ton['bybit']['ask'] if prices_ton.get('bybit') and prices_ton['bybit'] else 'N/A'
                print(f"  - Last {ton_pair}: OKX: {okx_price_ton}, Bybit: {bybit_price_ton}")

async def main():
    print("--- Starting Live Paper Trading Bot (Dual Exchange) ---")
    
    okx_connector = OKXConnector()
    bybit_connector = BybitConnector()

    # Create concurrent tasks for each connector and the status updater
    okx_task = asyncio.create_task(okx_connector.start(TRADING_PAIRS, handle_okx_update))
    bybit_task = asyncio.create_task(bybit_connector.start(TRADING_PAIRS, handle_bybit_update))
    status_task = asyncio.create_task(periodic_status_update())

    print("\nConnectors running. Waiting for price updates. Press Ctrl+C to stop.")
    await asyncio.gather(okx_task, bybit_task, status_task)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
