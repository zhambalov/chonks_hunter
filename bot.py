import websockets
import asyncio
import json
import ssl
import logging
from datetime import datetime, timedelta
from telegram.ext import Application, CommandHandler
from telegram import Update
from telegram.ext import ContextTypes
import aiohttp
from collections import deque
from config import *

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('opensea_telegram_monitor.log')
    ]
)

class RateLimiter:
    def __init__(self, max_requests, time_window):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()

    async def acquire(self):
        now = datetime.now()
        while self.requests and (now - self.requests[0]) > timedelta(seconds=self.time_window):
            self.requests.popleft()
        if len(self.requests) >= self.max_requests:
            sleep_time = (self.requests[0] + timedelta(seconds=self.time_window) - now).total_seconds()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        self.requests.append(now)

class OpenSeaTelegramBot:
    def __init__(self, debug_mode=False):
        # Initialize with config values
        self.stream_api_key = OPENSEA_STREAM_API_KEY
        self.api_key = OPENSEA_API_KEY
        self.telegram_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_PROFILE_ID  # Using your profile ID
        
        # OpenSea settings
        self.ws_url = f"wss://stream.openseabeta.com/socket/websocket?token={self.stream_api_key}"
        self.api_url = "https://api.opensea.io/api/v2"
        self.collection_slug = COLLECTION_SLUG
        self.collection_contract = COLLECTION_CONTRACT
        self.chain = CHAIN
        self.heartbeat_interval = 30
        self.ref = 0
        self.debug_mode = debug_mode
        
        # Rate limiters
        self.api_limiter = RateLimiter(max_requests=API_RATE_LIMIT, time_window=60)
        self.notification_limiter = RateLimiter(max_requests=NOTIFICATION_RATE_LIMIT, time_window=60)
        
        # Traits
        self.rare_traits = RARE_TRAITS
        
        # Initialize Telegram bot
        self.telegram_app = Application.builder().token(self.telegram_token).build()
        self.setup_telegram_handlers()
        
        # API headers
        self.api_headers = {
            "accept": "application/json",
            "x-api-key": self.api_key
        }

    def setup_telegram_handlers(self):
        self.telegram_app.add_handler(CommandHandler("start", self.cmd_start))
        self.telegram_app.add_handler(CommandHandler("status", self.cmd_status))

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🚀 OpenSea Chonks Monitor Bot started!\n"
            f"Monitoring for rare traits: {', '.join(sorted(self.rare_traits))}"
        )

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        status_message = (
            "📊 Bot Status:\n"
            f"• Monitoring: {self.collection_slug}\n"
            f"• Rare Traits: {', '.join(sorted(self.rare_traits))}"
        )
        await update.message.reply_text(status_message)

    async def send_telegram_message(self, message):
        await self.notification_limiter.acquire()
        try:
            await self.telegram_app.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
        except Exception as e:
            logging.error(f"Error sending Telegram message: {e}")

    async def get_nft_metadata(self, token_id):
        await self.api_limiter.acquire()
        try:
            url = f"{self.api_url}/chain/{self.chain}/contract/{self.collection_contract}/nfts/{token_id}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.api_headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('nft', {})
                    else:
                        logging.error(f"Failed to fetch metadata: {response.status}")
                        return None
        except Exception as e:
            logging.error(f"Error fetching metadata from API: {e}")
            return None

    def extract_token_id(self, nft_id):
        if not nft_id:
            return None
        try:
            return nft_id.split('/')[-1]
        except Exception as e:
            logging.error(f"Error extracting token ID from {nft_id}: {e}")
            return None

    def format_price(self, price_data):
        try:
            if not price_data:
                return 0.0
            price_wei = float(str(price_data))
            return price_wei / (10 ** 18)
        except (ValueError, TypeError) as e:
            logging.error(f"Error converting price {price_data}: {e}")
            return 0.0

    def has_rare_traits(self, traits):
        if not traits:
            return False
        try:
            return any(
                isinstance(trait, dict) and 
                trait.get('trait_type') in self.rare_traits 
                for trait in traits
            )
        except Exception as e:
            logging.error(f"Error checking rare traits: {e}")
            return False

    def format_notification_message(self, token_id, price_eth, traits):
        rare_traits_list = [
            f"  • {trait['trait_type']}: {trait['value']}"
            for trait in traits
            if isinstance(trait, dict) and trait.get('trait_type') in self.rare_traits
        ]
        
        rare_traits_text = "\n".join(rare_traits_list)
        
        message = (
            f"🚨 <b>Rare Chonk Listed!</b> 🚨\n\n"
            f"<b>Chonk #{token_id}</b>\n"
            f"💰 Price: {price_eth:.3f} ETH\n\n"
            f"🎯 Rare Traits:\n{rare_traits_text}\n\n"
            f"🔗 <a href='https://opensea.io/assets/base/{self.collection_contract}/{token_id}'>View on OpenSea</a>"
        )
        return message

    async def handle_listing(self, data):
        try:
            payload = data.get('payload', {})
            if not isinstance(payload, dict):
                return
                
            if 'payload' in payload:
                item_data = payload['payload'].get('item', {})
            else:
                item_data = payload.get('item', {})
            
            if not item_data:
                return

            nft_id = item_data.get('nft_id')
            token_id = self.extract_token_id(nft_id)
            if not token_id:
                return
            
            price_data = payload.get('base_price', payload.get('payload', {}).get('base_price', '0'))
            price_eth = self.format_price(price_data)
            
            metadata = await self.get_nft_metadata(token_id)
            traits = metadata.get('traits', []) if metadata else []
            
            if self.has_rare_traits(traits):
                message = self.format_notification_message(token_id, price_eth, traits)
                await self.send_telegram_message(message)
                
                if self.debug_mode:
                    logging.info(f"Sent notification for Chonk #{token_id}")
            
        except Exception as e:
            logging.error(f"Error processing listing: {e}", exc_info=True)

    async def connect_websocket(self):
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        try:
            async with websockets.connect(self.ws_url, ssl=ssl_context) as websocket:
                logging.info("Connected to OpenSea WebSocket")
                logging.info(f"Monitoring for rare traits: {', '.join(sorted(self.rare_traits))}")

                heartbeat_task = asyncio.create_task(self.send_heartbeat(websocket))
                await self.subscribe_to_collection(websocket)

                try:
                    while True:
                        message = await websocket.recv()
                        data = json.loads(message)
                        
                        if data.get('event') == 'item_listed':
                            await self.handle_listing(data)
                        elif self.debug_mode:
                            logging.debug(f"Received non-listing event: {data.get('event')}")
                        
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

    async def subscribe_to_collection(self, websocket):
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

    async def send_heartbeat(self, websocket):
        while True:
            try:
                heartbeat_message = {
                    "topic": "phoenix",
                    "event": "heartbeat",
                    "payload": {},
                    "ref": 0
                }
                await websocket.send(json.dumps(heartbeat_message))
                if self.debug_mode:
                    logging.debug("Heartbeat sent")
                await asyncio.sleep(self.heartbeat_interval)
            except Exception as e:
                logging.error(f"Heartbeat error: {e}")
                break

    async def run(self):
        try:
            await self.telegram_app.initialize()
            await self.telegram_app.start()
            
            # Send startup message
            await self.send_telegram_message(
                "🟢 Bot Started\n"
                f"Monitoring {self.collection_slug} for rare traits: {', '.join(sorted(self.rare_traits))}"
            )
            
            while True:
                try:
                    await self.connect_websocket()
                except Exception as e:
                    logging.error(f"WebSocket error: {e}")
                    await asyncio.sleep(5)
                    
        finally:
            await self.telegram_app.stop()

def main():
    import argparse
    parser = argparse.ArgumentParser(description='OpenSea Telegram Monitor Bot')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    bot = OpenSeaTelegramBot(debug_mode=args.debug)
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logging.info("\nBot stopped by user.")
    except Exception as e:
        logging.error(f"Fatal error in main: {e}", exc_info=True)

if __name__ == "__main__":
    main()