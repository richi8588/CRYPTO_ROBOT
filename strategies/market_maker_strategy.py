from decimal import Decimal, ROUND_DOWN

from connectors.bybit_connector import BybitConnector
from utils.logger import log

class MarketMakerStrategy:
    def __init__(self, connector: BybitConnector, pair: str, spread: float, order_size: float, inventory_limit: float, trade_logger):
        self.connector = connector
        self.pair = pair
        self.spread = spread
        self.order_size = order_size
        self.inventory_limit = inventory_limit
        self.trade_logger = trade_logger
        self.inventory = {
            'base': 0.0,
            'quote': 0.0
        }
        self.tick_size = self.get_tick_size()

    def get_tick_size(self) -> Decimal:
        """Fetches the tick size for the pair."""
        symbol_info = self.connector.get_symbol_info(self.pair)
        if symbol_info:
            return Decimal(symbol_info['priceFilter']['tickSize'])
        else:
            # Default to a reasonable value if fetching fails
            return Decimal('0.01')

    def get_fair_price(self) -> Decimal:
        """Calculates the fair price as the midpoint of the current bid-ask spread."""
        order_book = self.connector.get_order_book(self.pair)
        if not order_book:
            return None

        best_bid = Decimal(order_book['b'][0][0])
        best_ask = Decimal(order_book['a'][0][0])

        return (best_bid + best_ask) / 2

    def get_bid_ask_prices(self, fair_price: Decimal) -> tuple[Decimal, Decimal]:
        """Calculates the bid and ask prices based on the fair price and the desired spread."""
        spread = fair_price * Decimal(self.spread)
        bid_price = fair_price - spread / 2
        ask_price = fair_price + spread / 2

        # Round the prices to the nearest tick size
        bid_price = (bid_price / self.tick_size).quantize(Decimal('1')) * self.tick_size
        ask_price = (ask_price / self.tick_size).quantize(Decimal('1')) * self.tick_size

        return bid_price, ask_price

    def place_orders(self, bid_price: Decimal, ask_price: Decimal):
        """Places the buy and sell orders."""
        # Cancel existing orders first
        self.connector.cancel_all_orders(self.pair)

        # Check inventory limits before placing new orders
        base_asset, _ = self.pair.split('-')
        if self.inventory['base'] >= self.inventory_limit:
            log.warning(f"Inventory limit reached for {base_asset}. Not placing new buy orders.")
        else:
            self.connector.place_order(self.pair, 'buy', self.order_size, bid_price)
            self.trade_logger.info(f"Placed BUY order for {self.order_size} of {self.pair} at {bid_price}")

        if self.inventory['base'] <= -self.inventory_limit:
            log.warning(f"Inventory limit reached for {base_asset}. Not placing new sell orders.")
        else:
            self.connector.place_order(self.pair, 'sell', self.order_size, ask_price)
            self.trade_logger.info(f"Placed SELL order for {self.order_size} of {self.pair} at {ask_price}")

    def update_inventory(self):
        """Updates the inventory based on the filled orders."""
        # This is a simplified inventory management. A real implementation would need to track filled orders.
        # For now, we will assume that the inventory is managed externally or that we can query it.
        base_asset, quote_asset = self.pair.split('-')
        base_balance = self.connector.get_balance(base_asset)
        quote_balance = self.connector.get_balance(quote_asset)

        if base_balance is not None:
            self.inventory['base'] = base_balance
        if quote_balance is not None:
            self.inventory['quote'] = quote_balance