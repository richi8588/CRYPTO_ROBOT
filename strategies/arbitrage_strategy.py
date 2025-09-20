# strategies/arbitrage_strategy.py

def find_arbitrage_opportunity(okx_prices, bybit_prices, fees):
    """
    Analyzes prices from two exchanges to find an arbitrage opportunity.

    Args:
        okx_prices (dict): A dict with 'bid' and 'ask' keys for OKX.
        bybit_prices (dict): A dict with 'bid' and 'ask' keys for Bybit.
        fees (dict): A dict containing fee information for both exchanges.

    Returns:
        A dictionary describing the opportunity, or None.
    """
    if not okx_prices or not bybit_prices:
        return None

    # Scenario 1: Buy on OKX, Sell on Bybit
    # We buy at OKX's ask price and sell at Bybit's bid price.
    cost_on_okx = okx_prices['ask'] * (1 + fees['okx']['taker_fee'])
    revenue_on_bybit = bybit_prices['bid'] * (1 - fees['bybit']['taker_fee'])
    profit_pct_1 = (revenue_on_bybit / cost_on_okx) - 1

    if profit_pct_1 > 0:
        return {
            "type": "Buy OKX, Sell Bybit",
            "buy_exchange": "OKX",
            "sell_exchange": "Bybit",
            "buy_price": okx_prices['ask'],
            "sell_price": bybit_prices['bid'],
            "profit_percentage": profit_pct_1
        }

    # Scenario 2: Buy on Bybit, Sell on OKX
    # We buy at Bybit's ask price and sell at OKX's bid price.
    cost_on_bybit = bybit_prices['ask'] * (1 + fees['bybit']['taker_fee'])
    revenue_on_okx = okx_prices['bid'] * (1 - fees['okx']['taker_fee'])
    profit_pct_2 = (revenue_on_okx / cost_on_bybit) - 1

    if profit_pct_2 > 0:
        return {
            "type": "Buy Bybit, Sell OKX",
            "buy_exchange": "Bybit",
            "sell_exchange": "OKX",
            "buy_price": bybit_prices['ask'],
            "sell_price": okx_prices['bid'],
            "profit_percentage": profit_pct_2
        }

    return None
