# strategies/market_maker_strategy.py

def calculate_mm_orders(order_book, balance_usdt, balance_coin, trade_size_usdt, spread_percentage):
    """
    Calculates the prices and sizes for market maker orders.
    """
    if not order_book or not order_book.get('bids') or not order_book.get('asks'):
        return None

    best_bid = float(order_book['bids'][0][0])
    best_ask = float(order_book['asks'][0][0])

    # If spread is negative or too thin, don't trade
    if best_ask <= best_bid:
        return None

    # --- Calculate our prices ---
    mid_price = (best_bid + best_ask) / 2
    our_spread = mid_price * (spread_percentage / 100)
    our_bid_price = mid_price - (our_spread / 2)
    our_ask_price = mid_price + (our_spread / 2)

    # --- Calculate order sizes ---
    # Simple logic: use a fixed trade size in USDT
    buy_order_size_coin = trade_size_usdt / our_bid_price
    sell_order_size_coin = trade_size_usdt / our_ask_price

    # --- Basic risk management: don't place orders if we don't have the funds ---
    can_place_buy = balance_usdt >= trade_size_usdt
    can_place_sell = balance_coin >= sell_order_size_coin

    orders_to_place = {}
    if can_place_buy:
        orders_to_place['buy'] = {'price': round(our_bid_price, 5), 'size': round(buy_order_size_coin, 2)}
    
    if can_place_sell:
        orders_to_place['sell'] = {'price': round(our_ask_price, 5), 'size': round(sell_order_size_coin, 2)}

    return orders_to_place
