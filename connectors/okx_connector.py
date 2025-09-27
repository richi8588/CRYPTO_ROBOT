import asyncio
import json
import websockets

from utils.logger import log

class OKXConnector:
    def __init__(self):
        self._url = "wss://ws.okx.com:8443/ws/v5/public"
        log.info("Initializing OKX Native WebSocket Connector...")

    async def start(self, pairs: list, callback):
        """Connects to OKX, subscribes to pairs, and calls callback with messages."""
        log.info("OKX Connector connecting...")
        while True: # Auto-reconnection loop
            try:
                async with websockets.connect(self._url) as ws:
                    formatted_pairs = [p.replace('/', '-') for p in pairs]
                    args = [{"channel": "books5", "instId": pair} for pair in formatted_pairs]

                    subscribe_message = {
                        "op": "subscribe",
                        "args": args
                    }
                    await ws.send(json.dumps(subscribe_message))
                    
                    log.info(f"Subscribed to OKX order book for: {', '.join(pairs)}")

                    async for message in ws:
                        if message == 'ping':
                            await ws.send('pong')
                            continue
                        
                        data = json.loads(message)
                        if "arg" in data and "data" in data:
                            await callback('okx', data)
            except websockets.exceptions.ConnectionClosed as e:
                log.warning(f"OKX connection closed: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                log.error(f"An unexpected error occurred with OKX connector: {e}. Reconnecting in 10 seconds...")
                await asyncio.sleep(10)