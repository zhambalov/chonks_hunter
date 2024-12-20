import logging
from telegram.ext import Application, CommandHandler
from telegram import Update
from telegram.ext import ContextTypes
import asyncio
from ..core.rate_limiter import RateLimiter
from ..opensea.websocket import OpenSeaWebSocket
from ..opensea.client import OpenSeaClient
from .message_formatter import format_notification_message

class ChonksMonitorBot:
    def __init__(self, config, debug_mode=False):
        # Config
        self.config = config
        self.debug_mode = debug_mode
        
        # Rate limiters
        self.api_limiter = RateLimiter(max_requests=config.API_RATE_LIMIT, time_window=60)
        self.notification_limiter = RateLimiter(max_requests=config.NOTIFICATION_RATE_LIMIT, time_window=60)
        
        # Initialize components
        self.opensea_client = OpenSeaClient(
            api_key=config.OPENSEA_API_KEY,
            api_url="https://api.opensea.io/api/v2",
            api_limiter=self.api_limiter
        )
        
        self.websocket = OpenSeaWebSocket(
            stream_api_key=config.OPENSEA_STREAM_API_KEY,
            collection_slug=config.COLLECTION_SLUG
        )
        
        # Initialize Telegram bot
        self.telegram_app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        self.setup_telegram_handlers()

    def setup_telegram_handlers(self):
        self.telegram_app.add_handler(CommandHandler("start", self.cmd_start))
        self.telegram_app.add_handler(CommandHandler("status", self.cmd_status))

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🚀 OpenSea Chonks Monitor Bot started!\n"
            f"Monitoring for rare traits: {', '.join(sorted(self.config.RARE_TRAITS))}"
        )

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        status_message = (
            "📊 Bot Status:\n"
            f"• Monitoring: {self.config.COLLECTION_SLUG}\n"
            f"• Rare Traits: {', '.join(sorted(self.config.RARE_TRAITS))}"
        )
        await update.message.reply_text(status_message)

    async def send_telegram_message(self, message):
        await self.notification_limiter.acquire()
        try:
            await self.telegram_app.bot.send_message(
                chat_id=self.config.TELEGRAM_PROFILE_ID,
                text=message,
                parse_mode='HTML'
            )
        except Exception as e:
            logging.error(f"Error sending Telegram message: {e}")

    def extract_token_id(self, nft_id):
        if not nft_id:
            return None
        try:
            return nft_id.split('/')[-1]
        except Exception as e:
            logging.error(f"Error extracting token ID from {nft_id}: {e}")
            return None

    def has_rare_traits(self, traits):
        if not traits:
            return False
        try:
            return any(
                isinstance(trait, dict) and 
                trait.get('trait_type') in self.config.RARE_TRAITS 
                for trait in traits
            )
        except Exception as e:
            logging.error(f"Error checking rare traits: {e}")
            return False

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
            price_eth = self.opensea_client.format_price(price_data)
            
            metadata = await self.opensea_client.get_nft_metadata(
                self.config.CHAIN,
                self.config.COLLECTION_CONTRACT,
                token_id
            )
            traits = metadata.get('traits', []) if metadata else []
            
            if self.has_rare_traits(traits):
                message = format_notification_message(
                    token_id=token_id,
                    price_eth=price_eth,
                    traits=traits,
                    rare_traits=self.config.RARE_TRAITS,
                    collection_contract=self.config.COLLECTION_CONTRACT
                )
                await self.send_telegram_message(message)
                
                if self.debug_mode:
                    logging.info(f"Sent notification for Chonk #{token_id}")
            
        except Exception as e:
            logging.error(f"Error processing listing: {e}", exc_info=True)

    async def run(self):
        try:
            await self.telegram_app.initialize()
            await self.telegram_app.start()
            
            # Send startup message
            await self.send_telegram_message(
                "🟢 Bot Started\n"
                f"Monitoring {self.config.COLLECTION_SLUG} for rare traits: "
                f"{', '.join(sorted(self.config.RARE_TRAITS))}"
            )
            
            while True:
                await self.websocket.connect(self.handle_listing)
                await asyncio.sleep(5)  # Wait before reconnecting
                    
        finally:
            await self.telegram_app.stop()