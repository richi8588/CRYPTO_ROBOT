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

        trade_volume = 0
        if is_buy_side:
            # When buying, amount_to_trade is in the quote currency. We need to see how much base we can buy.
            # This logic is simplified; a more precise version would handle this conversion more carefully.
            # For our purpose, we assume amount_to_trade is in the asset we are spending.
            # Let's adjust the logic to be more robust.
            # amount_to_trade is the amount of the asset we want to acquire or dispose of.
            trade_volume = min(remaining_amount, volume)
            total_cost_or_revenue += trade_volume * price
        else:
            # When selling, amount_to_trade is in the base currency.
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
    Corrected logic for finding triangular arbitrage opportunities.
    """
    p1, p2, p3 = pairs # e.g., ('BTC/USDT', 'ETH/BTC', 'ETH/USDT')
    book1, book2, book3 = books[p1], books[p2], books[p3]
    base_currency = p1.split('/')[1] # USDT
    middle_currency = p1.split('/')[0] # BTC
    quote_currency = p2.split('/')[0] # ETH

    # --- Path 1: Base -> Middle -> Quote -> Base (e.g., USDT -> BTC -> ETH -> USDT) ---
    try:
        # Step 1: Buy Middle with Base (e.g., Buy BTC with USDT)
        # Trade on BTC/USDT asks. We have USDT, we want BTC.
        # We approximate how much BTC we can get for our start_amount of USDT.
        amount_to_buy_middle = start_amount / float(book1['asks'][0][0])
        trade1 = calculate_execution_details(book1['asks'], amount_to_buy_middle, is_buy_side=True)
        amount_of_middle = trade1['amount_filled'] * (1 - fee)

        # Step 2: Sell Middle for Quote (e.g., Sell BTC for ETH)
        # Trade on ETH/BTC bids. We have BTC, we want ETH.
        trade2 = calculate_execution_details(book2['bids'], amount_of_middle, is_buy_side=False)
        amount_of_quote = trade2['cost_or_revenue'] * (1 - fee)

        # Step 3: Sell Quote for Base (e.g., Sell ETH for USDT)
        # Trade on ETH/USDT bids. We have ETH, we want USDT.
        trade3 = calculate_execution_details(book3['bids'], amount_of_quote, is_buy_side=False)
        final_amount = trade3['cost_or_revenue'] * (1 - fee)

        profit_pct = (final_amount / start_amount) - 1
        if profit_pct >= -0.01: # Log even small losses to see if we are close
            return {
                'path': f"{base_currency}->{middle_currency}->{quote_currency}->{base_currency}",
                'profit_pct': profit_pct,
                'final_amount': final_amount
            }

    except (ValueError, KeyError, IndexError, ZeroDivisionError):
        pass

    # --- Path 2: Base -> Quote -> Middle -> Base (e.g., USDT -> ETH -> BTC -> USDT) ---
    try:
        # Step 1: Buy Quote with Base (e.g., Buy ETH with USDT)
        # Trade on ETH/USDT asks. We have USDT, we want ETH.
        amount_to_buy_quote = start_amount / float(book3['asks'][0][0])
        trade1 = calculate_execution_details(book3['asks'], amount_to_buy_quote, is_buy_side=True)
        amount_of_quote = trade1['amount_filled'] * (1 - fee)

        # Step 2: Buy Middle with Quote (e.g., Buy BTC with ETH)
        # Trade on ETH/BTC asks. We have ETH, we want BTC.
        trade2 = calculate_execution_details(book2['asks'], amount_of_quote, is_buy_side=True)
        amount_of_middle = trade2['amount_filled'] * (1 - fee)

        # Step 3: Sell Middle for Base (e.g., Sell BTC for USDT)
        # Trade on BTC/USDT bids. We have BTC, we want USDT.
        trade3 = calculate_execution_details(book1['bids'], amount_of_middle, is_buy_side=False)
        final_amount = trade3['cost_or_revenue'] * (1 - fee)

        profit_pct = (final_amount / start_amount) - 1
        if profit_pct >= -0.01: # Log even small losses to see if we are close
            return {
                'path': f"{base_currency}->{quote_currency}->{middle_currency}->{base_currency}",
                'profit_pct': profit_pct,
                'final_amount': final_amount
            }

    except (ValueError, KeyError, IndexError, ZeroDivisionError):
        pass

    return None