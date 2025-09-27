# strategies/arbitrage_strategy.py

def calculate_execution_details(order_book_side, trade_amount, is_buy_side):
    """
    Calculates the execution details (VWAP, total cost/revenue) for a trade against an order book.

    :param order_book_side: A list of [price, volume] lists (bids or asks).
    :param trade_amount: The amount of asset to buy or sell.
    :param is_buy_side: True if we are buying (iterating asks), False if selling (iterating bids).
    :return: A dict with {'avg_price', 'total_other_asset', 'amount_filled'}.
    """
    total_cost = 0
    amount_to_fill = trade_amount
    filled_amount = 0

    for level in order_book_side:
        price = float(level[0])
        volume = float(level[1])

        if amount_to_fill <= 0:
            break

        # How much can we trade at this level?
        trade_volume = min(amount_to_fill, volume)

        total_cost += trade_volume * price
        filled_amount += trade_volume
        amount_to_fill -= trade_volume

    if filled_amount == 0:
        return None

    avg_price = total_cost / filled_amount
    return {
        'avg_price': avg_price,
        'total_other_asset': total_cost,
        'amount_filled': filled_amount
    }


def find_depth_aware_opportunity(order_book_a, order_book_b, trade_size_usdt, fees):
    """
    Analyzes full order books to find a realistic arbitrage opportunity considering trade size.
    Now returns detailed trade info for simulation.
    """
    if not all([order_book_a, order_book_b, order_book_a.get('asks'), order_book_b.get('bids')]):
        return None

    # Scenario 1: Buy on A, Sell on B
    # Approximate amount of base currency to buy for the given USDT trade size.
    if not order_book_a['asks']: return None
    amount_to_buy_base = trade_size_usdt / float(order_book_a['asks'][0][0])
    
    buy_details = calculate_execution_details(order_book_a['asks'], amount_to_buy_base, is_buy_side=True)

    if buy_details and buy_details['amount_filled'] > 0:
        # Now, try to sell the acquired amount of base currency on exchange B
        sell_details = calculate_execution_details(order_book_b['bids'], buy_details['amount_filled'], is_buy_side=False)

        if sell_details:
            # Ensure the sell amount is significant enough to not be dust
            if sell_details['amount_filled'] < (buy_details['amount_filled'] * 0.99):
                return None # Slippage too high, couldn't sell the amount we bought

            cost = buy_details['total_other_asset'] * (1 + fees['okx']['taker_fee'])
            revenue = sell_details['total_other_asset'] * (1 - fees['bybit']['taker_fee'])
            profit_pct = (revenue / cost) - 1

            if profit_pct > 0:
                return {
                    "type": "Buy A, Sell B",
                    "buy_exchange": "A", "sell_exchange": "B",
                    "buy_price": buy_details['avg_price'], "sell_price": sell_details['avg_price'],
                    "profit_percentage": profit_pct,
                    "base_asset_amount": sell_details['amount_filled'], # The amount we actually sold
                    "quote_asset_cost": cost, # Total USDT cost including fees
                    "quote_asset_revenue": revenue, # Total USDT revenue after fees
                }

    # Scenario 2: Buy on B, Sell on A
    if not all([order_book_b.get('asks'), order_book_a.get('bids')]):
        return None
        
    if not order_book_b['asks']: return None
    amount_to_buy_base = trade_size_usdt / float(order_book_b['asks'][0][0])
    buy_details = calculate_execution_details(order_book_b['asks'], amount_to_buy_base, is_buy_side=True)

    if buy_details and buy_details['amount_filled'] > 0:
        sell_details = calculate_execution_details(order_book_a['bids'], buy_details['amount_filled'], is_buy_side=False)

        if sell_details:
            if sell_details['amount_filled'] < (buy_details['amount_filled'] * 0.99):
                return None

            cost = buy_details['total_other_asset'] * (1 + fees['bybit']['taker_fee'])
            revenue = sell_details['total_other_asset'] * (1 - fees['okx']['taker_fee'])
            profit_pct = (revenue / cost) - 1

            if profit_pct > 0:
                return {
                    "type": "Buy B, Sell A",
                    "buy_exchange": "B", "sell_exchange": "A",
                    "buy_price": buy_details['avg_price'], "sell_price": sell_details['avg_price'],
                    "profit_percentage": profit_pct,
                    "base_asset_amount": sell_details['amount_filled'],
                    "quote_asset_cost": cost,
                    "quote_asset_revenue": revenue,
                }

    return None
