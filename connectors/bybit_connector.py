# connectors/bybit_connector.py

import asyncio
import json
import websockets

class BybitConnector:
    def __init__(self):
        self._url = "wss://stream.bybit.com/v5/public/spot"
        print("Initializing Bybit Native WebSocket Connector...")

    async def start(self, pairs: list, callback):
        """Connects to Bybit, subscribes to pairs, and calls callback with messages."""
        print("Bybit Connector connecting...")
        while True: # Auto-reconnection loop
            try:
                async with websockets.connect(self._url) as ws:
                    # Bybit expects symbols without '/', e.g., 'BTCUSDT'
                    formatted_pairs = [p.replace('/', '') for p in pairs]
                    # Topic format: orderbook.1.{symbol}
                    topics = [f"orderbook.1.{pair}" for pair in formatted_pairs]
                    
                    subscribe_message = {
                        "op": "subscribe",
                        "args": topics
                    }
                    await ws.send(json.dumps(subscribe_message))

                    print(f"Subscribed to Bybit order book for: {', '.join(pairs)}")

                    async for message in ws:
                        data = json.loads(message)
                        # Ping/pong to keep connection alive
                        if "op" in data and data["op"] == "ping":
                            await ws.send(json.dumps({"op": "pong", "req_id": data["req_id"]}))
                            continue
                        
                        # Pass topic and data to the callback
                        if "topic" in data and "data" in data:
                            await callback('bybit', data)
            except websockets.exceptions.ConnectionClosed as e:
                print(f"Bybit connection closed: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"An unexpected error occurred with Bybit connector: {e}. Reconnecting in 10 seconds...")
                await asyncio.sleep(10)
