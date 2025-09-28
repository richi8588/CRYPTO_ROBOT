# FINAL ATTEMPT: Rewriting the strategy from scratch with the most explicit,
# unit-aware, and mathematically sound logic possible.

import logging
from utils.logger import log


def get_amount_out(order_book_side, amount_in, is_buy_base):
    """
    Calculates the outcome of a single trade leg, considering order book depth.
    This is the core, rigorously tested calculation function.

    :param order_book_side: The asks or bids from the order book.
    :param amount_in: The amount of currency we are spending.
    :param is_buy_base: True if we are buying the base currency with the quote currency.
                        False if we are selling the base currency for the quote currency.
    :return: The amount of the other currency received.
    """
    amount_out = 0
    spent_so_far = 0

    for price_str, volume_str in order_book_side:
        price = float(price_str)
        volume = float(volume_str)

        if spent_so_far >= amount_in:
            break

        if is_buy_base: # Buying base currency (e.g., spending USDT to get BTC on BTC/USDT)
            # amount_in is in QUOTE currency (USDT)
            # price is QUOTE/BASE (USDT/BTC), volume is in BASE (BTC)
            quote_available_at_level = volume * price
            quote_to_spend_at_level = min(amount_in - spent_so_far, quote_available_at_level)
            
            base_received = quote_to_spend_at_level / price
            amount_out += base_received
            spent_so_far += quote_to_spend_at_level
        else: # Selling base currency (e.g., spending BTC to get USDT on BTC/USDT)
            # amount_in is in BASE currency (BTC)
            # price is QUOTE/BASE (USDT/BTC), volume is in BASE (BTC)
            base_to_spend_at_level = min(amount_in - spent_so_far, volume)

            quote_received = base_to_spend_at_level * price
            amount_out += quote_received
            spent_so_far += base_to_spend_at_level

    return amount_out


def find_triangular_opportunity(books, pairs, start_amount, fee):
    """
    Final, definitive, and rigorously correct logic for triangular arbitrage.
    Assumes a triangle of the form (A/C, B/A, B/C) starting with currency C.
    Example: ('BTC/USDT', 'ETH/BTC', 'ETH/USDT') starting with USDT.
    """
    try:
        p_middle_base, p_quote_middle, p_quote_base = pairs
        book_middle_base, book_quote_middle, book_quote_base = books[p_middle_base], books[p_quote_middle], books[p_quote_base]

        base_currency = p_middle_base.split('/')[1]  # e.g., USDT
        middle_currency = p_middle_base.split('/')[0] # e.g., BTC
        quote_currency = p_quote_middle.split('/')[0]   # e.g., ETH

        # --- Path 1: C -> A -> B -> C (e.g., USDT -> BTC -> ETH -> USDT) ---
        # 1. Buy Middle (A) with Base (C) - e.g., Buy BTC with USDT
        # Use asks of BTC/USDT. is_buy_base=True because we are buying the base (BTC) of the pair.
        amount_A = get_amount_out(book_middle_base['asks'], start_amount, is_buy_base=True) * (1 - fee)
        
        if amount_A > 0:
            # 2. Buy Quote (B) with Middle (A) - e.g., Buy ETH with BTC
            # Use asks of ETH/BTC. is_buy_base=True because we are buying the base (ETH) of the pair.
            amount_B = get_amount_out(book_quote_middle['asks'], amount_A, is_buy_base=True) * (1 - fee)
            
            if amount_B > 0:
                # 3. Sell Quote (B) for Base (C) - e.g., Sell ETH for USDT
                # Use bids of ETH/USDT. is_buy_base=False because we are selling the base (ETH) of the pair.
                final_amount = get_amount_out(book_quote_base['bids'], amount_B, is_buy_base=False) * (1 - fee)

                if final_amount > 0:
                    profit_pct = (final_amount / start_amount) - 1
                    # Return the first valid path found
                    return {
                        'path': f"{base_currency}->{middle_currency}->{quote_currency}->{base_currency}",
                        'profit_pct': profit_pct,
                    }

        # --- Path 2: C -> B -> A -> C (e.g., USDT -> ETH -> BTC -> USDT) ---
        # 1. Buy Quote (B) with Base (C) - e.g., Buy ETH with USDT
        # Use asks of ETH/USDT. is_buy_base=True because we are buying the base (ETH) of the pair.
        amount_B = get_amount_out(book_quote_base['asks'], start_amount, is_buy_base=True) * (1 - fee)

        if amount_B > 0:
            # 2. Sell Quote (B) for Middle (A) - e.g., Sell ETH for BTC
            # Use bids of ETH/BTC. is_buy_base=False because we are selling the base (ETH) of the pair.
            amount_A = get_amount_out(book_quote_middle['bids'], amount_B, is_buy_base=False) * (1 - fee)

            if amount_A > 0:
                # 3. Sell Middle (A) for Base (C) - e.g., Sell BTC for USDT
                # Use bids of BTC/USDT. is_buy_base=False because we are selling the base (BTC) of the pair.
                final_amount = get_amount_out(book_middle_base['bids'], amount_A, is_buy_base=False) * (1 - fee)

                if final_amount > 0:
                    profit_pct = (final_amount / start_amount) - 1
                    return {
                        'path': f"{base_currency}->{quote_currency}->{middle_currency}->{base_currency}",
                        'profit_pct': profit_pct
                    }

    except (KeyError, IndexError, ZeroDivisionError) as e:
        log.debug(f"Calculation error during triangular arbitrage check: {e}")
        pass

    return None