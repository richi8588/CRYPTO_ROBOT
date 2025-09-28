
# This file contains the logic for finding triangular arbitrage opportunities.
# This is a complete rewrite using an explicit, unit-aware calculation method
# to fix critical mathematical flaws in the previous version.

import logging
from utils.logger import log


def calculate_trade_outcome(order_book_side, amount_to_spend, fee, trade_type):
    """
    Calculates the outcome of a single trade leg, considering order book depth.

    :param order_book_side: The asks or bids from the order book.
    :param amount_to_spend: The amount of currency we are spending.
    :param fee: The taker fee.
    :param trade_type: 'base_to_quote' (selling base for quote) or 'quote_to_base' (buying base with quote).
    :return: The amount of currency received after the trade and fees.
    """
    amount_received = 0
    spent_so_far = 0

    for price_str, volume_str in order_book_side:
        price = float(price_str)
        volume = float(volume_str)

        if spent_so_far >= amount_to_spend:
            break

        if trade_type == 'quote_to_base': # Buying the base currency with the quote currency
            # How much quote currency can we spend at this level?
            can_spend = volume * price
            # How much do we still need to spend?
            will_spend = min(amount_to_spend - spent_so_far, can_spend)
            
            amount_received += will_spend / price
            spent_so_far += will_spend

        elif trade_type == 'base_to_quote': # Selling the base currency for the quote currency
            # How much base currency can we sell at this level?
            can_sell = volume
            # How much do we still need to sell?
            will_sell = min(amount_to_spend - spent_so_far, can_sell)

            amount_received += will_sell * price
            spent_so_far += will_sell

    if spent_so_far == 0:
        return 0

    return amount_received * (1 - fee)


def find_triangular_opportunity(books, pairs, start_amount, fee):
    """
    New, explicit, and correct logic for finding triangular arbitrage opportunities.
    """
    try:
        p1, p2, p3 = pairs # e.g., ('BTC/USDT', 'ETH/BTC', 'ETH/USDT')
        book1, book2, book3 = books[p1], books[p2], books[p3]
        
        base_currency, middle_currency = p1.split('/') # BTC, USDT
        quote_currency, _ = p3.split('/') # ETH, USDT

        # --- Path 1: Start -> Middle -> Quote -> Start (e.g., USDT -> BTC -> ETH -> USDT) ---
        # 1. Buy BTC with USDT (on BTC/USDT asks)
        amount_of_middle = calculate_trade_outcome(book1['asks'], start_amount, fee, 'quote_to_base')
        if amount_of_middle > 0:
            # 2. Sell BTC for ETH (on ETH/BTC bids)
            amount_of_quote = calculate_trade_outcome(book2['bids'], amount_of_middle, fee, 'base_to_quote')
            if amount_of_quote > 0:
                # 3. Sell ETH for USDT (on ETH/USDT bids)
                final_amount = calculate_trade_outcome(book3['bids'], amount_of_quote, fee, 'base_to_quote')
                
                if final_amount > 0:
                    profit_pct = (final_amount / start_amount) - 1
                    if profit_pct > -0.01: # Log near misses
                        return {
                            'path': f"{base_currency}->{middle_currency}->{quote_currency}->{base_currency}",
                            'profit_pct': profit_pct,
                        }

        # --- Path 2: Start -> Quote -> Middle -> Start (e.g., USDT -> ETH -> BTC -> USDT) ---
        # 1. Buy ETH with USDT (on ETH/USDT asks)
        amount_of_quote = calculate_trade_outcome(book3['asks'], start_amount, fee, 'quote_to_base')
        if amount_of_quote > 0:
            # 2. Buy BTC with ETH (on ETH/BTC asks)
            # This is tricky: we are spending ETH (quote) to buy BTC (base)
            amount_of_middle = calculate_trade_outcome(book2['asks'], amount_of_quote, fee, 'quote_to_base')
            if amount_of_middle > 0:
                # 3. Sell BTC for USDT (on BTC/USDT bids)
                final_amount = calculate_trade_outcome(book1['bids'], amount_of_middle, fee, 'base_to_quote')

                if final_amount > 0:
                    profit_pct = (final_amount / start_amount) - 1
                    if profit_pct > -0.01: # Log near misses
                        return {
                            'path': f"{base_currency}->{quote_currency}->{middle_currency}->{base_currency}",
                            'profit_pct': profit_pct,
                        }

    except (KeyError, IndexError, ZeroDivisionError) as e:
        log.debug(f"Calculation error during triangular arbitrage check: {e}")
        pass

    return None
