
import asyncio
import time
import json
import websockets
from pybit.unified_trading import HTTP

from config.settings import API_KEYS
from utils.logger import log

class BybitConnector:
    def __init__(self, testnet=False):
        log.info("Initializing Bybit WebSocket Connector...")
        self._url = "wss://stream-testnet.bybit.com/v5/public/spot" if testnet else "wss://stream.bybit.com/v5/public/spot"
        
        self.session = HTTP(
            testnet=testnet,
            api_key=API_KEYS['bybit']['api_key'],
            api_secret=API_KEYS['bybit']['secret_key'],
        )

    def get_balance(self, coin: str):
        """Fetches the balance for a specific coin from the UNIFIED account."""
        try:
            result = self.session.get_wallet_balance(
                accountType="UNIFIED",
                coin=coin
            )
            if result and result.get('retCode') == 0:
                balance_list = result['result']['list']
                if not balance_list or not balance_list[0]['coin']:
                    return 0.0
                
                balance_info = balance_list[0]['coin'][0]
                wallet_balance = balance_info['walletBalance']
                return float(wallet_balance) if wallet_balance else 0.0
            else:
                log.error(f"Error fetching Bybit balance: {result.get('retMsg')}")
                return None
        except Exception as e:
            log.error(f"An exception occurred while fetching Bybit balance: {e}")
            return None

    async def start_public_stream(self, pairs: list, callback, stream_type="orderbook"):
        """Connects to Bybit, subscribes to pairs, and calls callback with messages."""
        log.info(f"Bybit Connector connecting to public {stream_type} stream...")
        while True: # Auto-reconnection loop
            try:
                async with websockets.connect(self._url) as ws:
                    formatted_pairs = [p.replace('/', '') for p in pairs]
                    
                    if stream_type == "trade":
                        topics = [f"publicTrade.{pair}" for pair in formatted_pairs]
                    else: # Default to orderbook
                        topics = [f"orderbook.50.{pair}" for pair in formatted_pairs]
                    
                    subscribe_message = {
                        "op": "subscribe",
                        "args": topics
                    }
                    await ws.send(json.dumps(subscribe_message))

                    log.info(f"Subscribed to Bybit {stream_type} stream for: {', '.join(pairs)}")

                    async for message in ws:
                        data = json.loads(message)
                        if "op" in data and data["op"] == "ping":
                            await ws.send(json.dumps({"op": "pong", "req_id": data["req_id"]}))
                            continue
                        
                        # For trade streams, the data is a list of trades
                        if "topic" in data and "data" in data:
                            if stream_type == "trade":
                                # Pass each trade individually to the callback
                                for trade_data in data['data']:
                                    # Re-wrap it to look like a single message for the handler
                                    single_trade_message = {'topic': data['topic'], 'data': [trade_data]}
                                    await callback(single_trade_message)
                            else:
                                await callback(data)
            except websockets.exceptions.ConnectionClosed as e:
                log.warning(f"Bybit connection closed: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                log.error(f"An unexpected error occurred with Bybit connector: {e}. Reconnecting in 10 seconds...")
                await asyncio.sleep(10)
