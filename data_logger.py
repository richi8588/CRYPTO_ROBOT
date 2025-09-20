# data_logger.py

import asyncio
import csv
from datetime import datetime

from connectors.okx_connector import OKXConnector
from connectors.bybit_connector import BybitConnector
from config.settings import TRADING_PAIRS

async def main():
    """Logs price data from exchanges for multiple pairs to separate CSV files."""
    print("--- Starting Multi-Pair Data Logger ---")
    print(f"Logging data for: {", ".join(TRADING_PAIRS)}")

    okx = OKXConnector()
    bybit = BybitConnector()

    # Prepare CSV files and writers for each pair
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_handlers = {}
    csv_writers = {}

    for pair in TRADING_PAIRS:
        pair_filename = pair.replace('/', '-')
        file_path = f'data/price_log_{pair_filename}_{run_timestamp}.csv'
        f = open(file_path, 'w', newline='')
        file_handlers[pair] = f
        writer = csv.writer(f)
        writer.writerow(["timestamp", "okx_bid", "okx_ask", "bybit_bid", "bybit_ask"])
        csv_writers[pair] = writer
        print(f"- Logging {pair} to {file_path}")

    print("Press Ctrl+C to stop.")

    try:
        while True:
            # Create a list of tasks to fetch all data concurrently
            tasks = []
            for pair in TRADING_PAIRS:
                tasks.append(okx.get_order_book(pair))
                tasks.append(bybit.get_order_book(pair))
            
            # Run all tasks in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for i, pair in enumerate(TRADING_PAIRS):
                okx_result_index = i * 2
                bybit_result_index = i * 2 + 1

                okx_prices = results[okx_result_index]
                bybit_prices = results[bybit_result_index]

                if isinstance(okx_prices, dict) and isinstance(bybit_prices, dict):
                    csv_writers[pair].writerow([
                        datetime.now().isoformat(),
                        okx_prices['bid'],
                        okx_prices['ask'],
                        bybit_prices['bid'],
                        bybit_prices['ask']
                    ])
                else:
                    # Handle potential errors for a specific pair
                    print(f"Error fetching data for {pair}. OKX: {okx_prices}, Bybit: {bybit_prices}")
            
            print(f"Logged all pairs at {datetime.now().strftime('%H:%M:%S')}", end='\r')

            # Wait for the next interval
            await asyncio.sleep(5)  # Increased sleep time for multiple pairs

    except KeyboardInterrupt:
        print("\nStopping data logger.")
    finally:
        # Clean up and close all file handlers
        for f in file_handlers.values():
            f.close()
        print("All log files closed.")

if __name__ == "__main__":
    asyncio.run(main())
