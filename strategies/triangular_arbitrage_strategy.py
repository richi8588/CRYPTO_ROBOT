
# This file contains the logic for finding triangular arbitrage opportunities.


def calculate_execution_details(order_book_side, amount_to_trade, is_buy_side):
    """
    Calculates the execution details (VWAP, total cost/revenue) for a trade against an order book.
    This is a generic utility function.

    :param order_book_side: A list of [price, volume] lists (bids or asks).
    :param amount_to_trade: The amount of asset to buy or sell.
    :param is_buy_side: True if we are buying (iterating asks), False if selling (iterating bids).
    :return: A dict with {'avg_price', 'amount_filled', 'cost_or_revenue'}.
    """
    total_cost_or_revenue = 0
    amount_filled = 0
    remaining_amount = amount_to_trade

    for level in order_book_side:
        price = float(level[0])
        volume = float(level[1])

        if remaining_amount <= 0:
            break

        # On buy side, volume is in base currency. On sell side, it's also in base currency.
        # The amount_to_trade is always in the base currency of the pair.
        trade_volume = min(remaining_amount, volume)

        total_cost_or_revenue += trade_volume * price
        amount_filled += trade_volume
        remaining_amount -= trade_volume

    if amount_filled == 0:
        return None

    avg_price = total_cost_or_revenue / amount_filled
    return {
        'avg_price': avg_price,
        'amount_filled': amount_filled,
        'cost_or_revenue': total_cost_or_revenue
    }


def find_triangular_opportunity(books, pairs, start_amount, fee):
    """
    Analyzes three order books to find a triangular arbitrage opportunity on a single exchange.

    :param books: A dictionary of the three order books, keyed by pair string.
    :param pairs: A tuple of the three pair strings, e.g., ('BTC/USDT', 'ETH/BTC', 'ETH/USDT').
    :param start_amount: The initial amount of the base currency (e.g., 100.0 USDT).
    :param fee: The taker fee for the exchange.
    :return: A dictionary with opportunity details if one is found, otherwise None.
    """
    p1, p2, p3 = pairs
    book1, book2, book3 = books[p1], books[p2], books[p3]

    # Example: ('BTC/USDT', 'ETH/BTC', 'ETH/USDT')
    # Path 1: USDT -> BTC -> ETH -> USDT (Buy BTC, Buy ETH, Sell ETH)
    try:
        # Step 1: Buy BTC with USDT (use BTC/USDT asks)
        # We need to calculate how much BTC we can buy for `start_amount` USDT.
        # This is an approximation. A more precise method would iterate.
        initial_btc_amount = start_amount / float(book1['asks'][0][0])
        trade1 = calculate_execution_details(book1['asks'], initial_btc_amount, is_buy_side=True)
        if not trade1: raise ValueError("Trade 1 failed")
        amount_after_trade1 = trade1['amount_filled'] * (1 - fee)

        # Step 2: Buy ETH with BTC (use ETH/BTC asks)
        trade2 = calculate_execution_details(book2['asks'], amount_after_trade1, is_buy_side=True)
        if not trade2: raise ValueError("Trade 2 failed")
        amount_after_trade2 = trade2['amount_filled'] * (1 - fee)

        # Step 3: Sell ETH for USDT (use ETH/USDT bids)
        trade3 = calculate_execution_details(book3['bids'], amount_after_trade2, is_buy_side=False)
        if not trade3: raise ValueError("Trade 3 failed")
        final_amount = trade3['cost_or_revenue'] * (1 - fee)

        profit_pct = (final_amount / start_amount) - 1
        if profit_pct > 0:
            return {
                'path': f"USDT -> {p1.split('/')[0]} -> {p2.split('/')[0]} -> USDT",
                'profit_pct': profit_pct,
                'final_amount': final_amount
            }

    except (ValueError, KeyError, IndexError):
        pass # A trade failed, likely due to empty order book side

    # Path 2: USDT -> ETH -> BTC -> USDT (Buy ETH, Sell ETH for BTC, Sell BTC for USDT)
    try:
        # Step 1: Buy ETH with USDT (use ETH/USDT asks)
        initial_eth_amount = start_amount / float(book3['asks'][0][0])
        trade1 = calculate_execution_details(book3['asks'], initial_eth_amount, is_buy_side=True)
        if not trade1: raise ValueError("Trade 1 failed")
        amount_after_trade1 = trade1['amount_filled'] * (1 - fee)

        # Step 2: Sell ETH for BTC (use ETH/BTC bids)
        trade2 = calculate_execution_details(book2['bids'], amount_after_trade1, is_buy_side=False)
        if not trade2: raise ValueError("Trade 2 failed")
        amount_after_trade2 = trade2['cost_or_revenue'] * (1 - fee)

        # Step 3: Sell BTC for USDT (use BTC/USDT bids)
        trade3 = calculate_execution_details(book1['bids'], amount_after_trade2, is_buy_side=False)
        if not trade3: raise ValueError("Trade 3 failed")
        final_amount = trade3['cost_or_revenue'] * (1 - fee)

        profit_pct = (final_amount / start_amount) - 1
        if profit_pct > 0:
            return {
                'path': f"USDT -> {p3.split('/')[0]} -> {p1.split('/')[0]} -> USDT",
                'profit_pct': profit_pct,
                'final_amount': final_amount
            }

    except (ValueError, KeyError, IndexError):
        pass

    return None
