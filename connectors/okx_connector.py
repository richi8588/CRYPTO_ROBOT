# connectors/okx_connector.py

import asyncio
import json
import websockets

class OKXConnector:
    def __init__(self):
        self._url = "wss://ws.okx.com:8443/ws/v5/public"
        print("Initializing OKX Native WebSocket Connector...")

    async def start(self, pairs: list, callback):
        """Connects to OKX, subscribes to pairs, and calls callback with messages."""
        print("OKX Connector connecting...")
        while True: # Auto-reconnection loop
            try:
                async with websockets.connect(self._url) as ws:
                    # OKX expects symbols with '-', e.g., 'BTC-USDT'
                    formatted_pairs = [p.replace('/', '-') for p in pairs]
                    # Channel for top 5 levels: books5
                    args = [{"channel": "books5", "instId": pair} for pair in formatted_pairs]

                    subscribe_message = {
                        "op": "subscribe",
                        "args": args
                    }
                    await ws.send(json.dumps(subscribe_message))
                    
                    print(f"Subscribed to OKX order book for: {', '.join(pairs)}")

                    async for message in ws:
                        # OKX sends 'ping' and expects 'pong'
                        if message == 'ping':
                            await ws.send('pong')
                            continue
                        
                        data = json.loads(message)
                        # Pass arg (which contains channel info) and data to the callback
                        if "arg" in data and "data" in data:
                            await callback('okx', data)
            except websockets.exceptions.ConnectionClosed as e:
                print(f"OKX connection closed: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"An unexpected error occurred with OKX connector: {e}. Reconnecting in 10 seconds...")
                await asyncio.sleep(10)
