import websockets
import asyncio
import json
import ssl
import time

class OpenSeaStreamMonitor:
    def __init__(self, api_key):
        self.api_key = api_key
        self.ws_url = f"wss://stream.openseabeta.com/socket/websocket?token={api_key}"
        self.collection_slug = "chonks"
        self.heartbeat_interval = 30  # seconds
        self.ref = 0
        
        # Define trait categories
        self.rare_traits = {'Face', 'Head', 'Accessory'}

    async def send_heartbeat(self, websocket):
        """Send heartbeat message every 30 seconds"""
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
                print(f"Heartbeat error: {e}")
                break

    async def subscribe_to_collection(self, websocket):
        """Subscribe to collection events"""
        subscribe_message = {
            "topic": f"collection:{self.collection_slug}",
            "event": "phx_join",
            "payload": {},
            "ref": self.ref
        }
        await websocket.send(json.dumps(subscribe_message))

    def analyze_traits(self, traits):
        """Check for rare traits"""
        if not traits:
            return False
        
        for trait in traits:
            if trait.get('trait_type') in self.rare_traits:
                return True
        return False

    async def handle_listing(self, payload):
        """Process a new listing event"""
        try:
            # Extract relevant information from payload
            nft_data = payload.get('item', {})
            token_id = nft_data.get('nft_id')
            price_data = payload.get('base_price', '0')
            price_eth = float(price_data) / (10 ** 18)  # Convert from wei to ETH
            
            traits = nft_data.get('traits', [])
            has_rare = self.analyze_traits(traits)
            
            print("\n" + "="*50)
            if has_rare:
                print("!!! RARE TRAITS DETECTED !!!")
            print(f"Chonk #{token_id}")
            print(f"Price: {price_eth:.3f} ETH")
            
            if traits:
                print("\nTraits:")
                for trait in traits:
                    print(f"  {trait['trait_type']}: {trait['value']}")
            
            print(f"\nLink: https://opensea.io/assets/ethereum/0x07152bfde079b5319e5308C43fB1Dbc9C76cb4F9/{token_id}")
            print("="*50 + "\n")
            
        except Exception as e:
            print(f"Error processing listing: {e}")

    async def connect_websocket(self):
        """Connect to OpenSea WebSocket"""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        async with websockets.connect(self.ws_url, ssl=ssl_context) as websocket:
            print(f"Starting to monitor NEW Chonks listings...")
            print("Waiting for new listings to appear...")

            # Start heartbeat task
            heartbeat_task = asyncio.create_task(self.send_heartbeat(websocket))
            
            # Subscribe to collection
            await self.subscribe_to_collection(websocket)

            try:
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    # Handle different event types
                    if data.get('event') == 'item_listed':
                        await self.handle_listing(data.get('payload', {}))
                    
            except websockets.ConnectionClosed:
                print("Connection closed. Reconnecting...")
                heartbeat_task.cancel()
            except Exception as e:
                print(f"Error: {e}")
                heartbeat_task.cancel()

    async def run(self):
        """Main loop with automatic reconnection"""
        while True:
            try:
                await self.connect_websocket()
            except Exception as e:
                print(f"Connection error: {e}")
                print("Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

if __name__ == "__main__":
    API_KEY = "31513985dd784d02ab2b596ad6e94040"
    monitor = OpenSeaStreamMonitor(API_KEY)
    
    try:
        asyncio.run(monitor.run())
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")