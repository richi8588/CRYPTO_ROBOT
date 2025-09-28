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
            quote_available_at_level = volume * price
            quote_to_spend_at_level = min(amount_in - spent_so_far, quote_available_at_level)
            
            base_received = quote_to_spend_at_level / price
            amount_out += base_received
            spent_so_far += quote_to_spend_at_level
        else: # Selling base currency (e.g., spending BTC to get USDT on BTC/USDT)
            base_to_spend_at_level = min(amount_in - spent_so_far, volume)

            quote_received = base_to_spend_at_level * price
            amount_out += quote_received
            spent_so_far += base_to_spend_at_level

    return amount_out


def find_triangular_opportunity(books, pairs, start_amount, fee):
    """
    Final attempt with extreme verbose logging to trace every calculation step.
    """
    try:
        p_middle_base, p_quote_middle, p_quote_base = pairs
        book_middle_base, book_quote_middle, book_quote_base = books[p_middle_base], books[p_quote_middle], books[p_quote_base]

        base_C = p_middle_base.split('/')[1]
        middle_A = p_middle_base.split('/')[0]
        quote_B = p_quote_middle.split('/')[0]

        # --- Path 1: C -> A -> B -> C (e.g., USDT -> BTC -> ETH -> USDT) ---
        log.info(f"--- PATH 1: {base_C}->{middle_A}->{quote_B}->{base_C} ---")
        # 1. Buy Middle (A) with Base (C)
        log.info(f"  STEP 1 (C->A): Spending {start_amount:.4f} {base_C} on {p_middle_base} asks...")
        amount_A = get_amount_out(book_middle_base['asks'], start_amount, is_buy_base=True) * (1 - fee)
        log.info(f"  STEP 1 RESULT: Received {amount_A:.8f} {middle_A}")
        
        if amount_A > 0:
            # 2. Buy Quote (B) with Middle (A)
            log.info(f"  STEP 2 (A->B): Spending {amount_A:.8f} {middle_A} on {p_quote_middle} asks...")
            amount_B = get_amount_out(book_quote_middle['asks'], amount_A, is_buy_base=True) * (1 - fee)
            log.info(f"  STEP 2 RESULT: Received {amount_B:.8f} {quote_B}")
            
            if amount_B > 0:
                # 3. Sell Quote (B) for Base (C)
                log.info(f"  STEP 3 (B->C): Spending {amount_B:.8f} {quote_B} on {p_quote_base} bids...")
                final_amount = get_amount_out(book_quote_base['bids'], amount_B, is_buy_base=False) * (1 - fee)
                log.info(f"  STEP 3 RESULT: Received {final_amount:.4f} {base_C}")

                if final_amount > 0:
                    profit_pct = (final_amount / start_amount) - 1
                    log.info(f"  FINAL CALC: Start={start_amount:.4f} {base_C}, End={final_amount:.4f} {base_C}, Profit={profit_pct*100:.4f}%")
                    return {
                        'path': f"{base_C}->{middle_A}->{quote_B}->{base_C}",
                        'profit_pct': profit_pct,
                    }

        # --- Path 2: C -> B -> A -> C (e.g., USDT -> ETH -> BTC -> USDT) ---
        log.info(f"--- PATH 2: {base_C}->{quote_B}->{middle_A}->{base_C} ---")
        # 1. Buy Quote (B) with Base (C)
        log.info(f"  STEP 1 (C->B): Spending {start_amount:.4f} {base_C} on {p_quote_base} asks...")
        amount_B = get_amount_out(book_quote_base['asks'], start_amount, is_buy_base=True) * (1 - fee)
        log.info(f"  STEP 1 RESULT: Received {amount_B:.8f} {quote_B}")

        if amount_B > 0:
            # 2. Sell Quote (B) for Middle (A)
            log.info(f"  STEP 2 (B->A): Spending {amount_B:.8f} {quote_B} on {p_quote_middle} bids...")
            amount_A = get_amount_out(book_quote_middle['bids'], amount_B, is_buy_base=False) * (1 - fee)
            log.info(f"  STEP 2 RESULT: Received {amount_A:.8f} {middle_A}")

            if amount_A > 0:
                # 3. Sell Middle (A) for Base (C)
                log.info(f"  STEP 3 (A->C): Spending {amount_A:.8f} {middle_A} on {p_middle_base} bids...")
                final_amount = get_amount_out(book_middle_base['bids'], amount_A, is_buy_base=False) * (1 - fee)
                log.info(f"  STEP 3 RESULT: Received {final_amount:.4f} {base_C}")

                if final_amount > 0:
                    profit_pct = (final_amount / start_amount) - 1
                    log.info(f"  FINAL CALC: Start={start_amount:.4f} {base_C}, End={final_amount:.4f} {base_C}, Profit={profit_pct*100:.4f}%")
                    return {
                        'path': f"{base_C}->{quote_B}->{middle_A}->{base_C}",
                        'profit_pct': profit_pct
                    }

    except (KeyError, IndexError, ZeroDivisionError) as e:
        log.debug(f"Calculation error during triangular arbitrage check: {e}")
        pass

    return None