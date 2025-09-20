# main.py - Entry point for the crypto arbitrage bot

import asyncio
from connectors.okx_connector import OKXConnector
from connectors.bybit_connector import BybitConnector
from config.settings import TRADING_PAIR, TRADING_FEES, MIN_PROFIT_THRESHOLD
from strategies.arbitrage_strategy import find_arbitrage_opportunity

async def main():
    """Main function to fetch, analyze, and display arbitrage opportunities."""
    print(f"Starting Crypto Arbitrage Bot...")
    print(f"Fetching data for trading pair: {TRADING_PAIR}")

    # Initialize connectors
    okx = OKXConnector()
    bybit = BybitConnector()

    # Fetch order books concurrently
    results = await asyncio.gather(
        okx.get_order_book(TRADING_PAIR),
        bybit.get_order_book(TRADING_PAIR)
    )

    okx_prices = results[0]
    bybit_prices = results[1]

    print("--- Data Fetch Complete ---")
    if okx_prices:
        print(f"OKX:     Bid: {okx_prices['bid']:<10} | Ask: {okx_prices['ask']:<10}")
    else:
        print("OKX:     Failed to fetch data.")

    if bybit_prices:
        print(f"Bybit:   Bid: {bybit_prices['bid']:<10} | Ask: {bybit_prices['ask']:<10}")
    else:
        print("Bybit:   Failed to fetch data.")

    print("--- Arbitrage Analysis ---")
    opportunity = find_arbitrage_opportunity(okx_prices, bybit_prices, TRADING_FEES)

    if opportunity and opportunity['profit_percentage'] >= MIN_PROFIT_THRESHOLD:
        profit_pct = opportunity['profit_percentage'] * 100
        print(f"\n!!! PROFITABLE OPPORTUNITY FOUND !!!")
        print(f"  Action: {opportunity['type']}")
        print(f"  Buy at {opportunity['buy_exchange']} for {opportunity['buy_price']}")
        print(f"  Sell at {opportunity['sell_exchange']} for {opportunity['sell_price']}")
        print(f"  Estimated Profit: {profit_pct:.4f}%")
    else:
        print("No profitable arbitrage opportunity found at the moment.")


if __name__ == "__main__":
    asyncio.run(main())
