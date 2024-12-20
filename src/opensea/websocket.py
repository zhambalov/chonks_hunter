import websockets
import json
import ssl
import logging
import asyncio

class OpenSeaWebSocket:
    def __init__(self, stream_api_key, collection_slug):
        self.ws_url = f"wss://stream.openseabeta.com/socket/websocket?token={stream_api_key}"
        self.collection_slug = collection_slug
        self.heartbeat_interval = 30
        self.ref = 0

    async def connect(self, handler):
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        try:
            async with websockets.connect(self.ws_url, ssl=ssl_context) as websocket:
                logging.info("Connected to OpenSea WebSocket")
                
                heartbeat_task = asyncio.create_task(self._send_heartbeat(websocket))
                await self._subscribe_to_collection(websocket)

                try:
                    while True:
                        message = await websocket.recv()
                        data = json.loads(message)
                        
                        if data.get('event') == 'item_listed':
                            await handler(data)
                            
                except websockets.ConnectionClosed:
                    logging.warning("WebSocket connection closed")
                    heartbeat_task.cancel()
                except json.JSONDecodeError as e:
                    logging.error(f"JSON decode error: {e}")
                    heartbeat_task.cancel()
                except Exception as e:
                    logging.error(f"WebSocket error: {e}")
                    heartbeat_task.cancel()
                    
        except Exception as e:
            logging.error(f"Connection error: {e}")
            await asyncio.sleep(5)

    async def _send_heartbeat(self, websocket):
        while True:
            try:
                heartbeat_message = {
                    "topic": "phoenix",
                    "event": "heartbeat",
                    "payload": {},
                    "ref": 0
                }
                await websocket.send(json.dumps(heartbeat_message))
                await asyncio.sleep(self.heartbeat_interval)
            except Exception as e:
                logging.error(f"Heartbeat error: {e}")
                break

    async def _subscribe_to_collection(self, websocket):
        try:
            subscribe_message = {
                "topic": f"collection:{self.collection_slug}",
                "event": "phx_join",
                "payload": {},
                "ref": self.ref
            }
            await websocket.send(json.dumps(subscribe_message))
            logging.info(f"Subscribed to collection: {self.collection_slug}")
        except Exception as e:
            logging.error(f"Subscription error: {e}")
            raise