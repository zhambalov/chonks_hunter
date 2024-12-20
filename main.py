import asyncio
import argparse
import logging
from src.bot.telegram_bot import ChonksMonitorBot
import config  # Import the config module directly

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('opensea_telegram_monitor.log')
    ]
)

def parse_args():
    parser = argparse.ArgumentParser(description='OpenSea Chonks Monitor Bot')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    return parser.parse_args()

async def main():
    args = parse_args()
    
    try:
        # Initialize and run bot with config module
        bot = ChonksMonitorBot(config, debug_mode=args.debug)
        await bot.run()
    except KeyboardInterrupt:
        logging.info("\nBot stopped by user.")
    except Exception as e:
        logging.error(f"Fatal error in main: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())