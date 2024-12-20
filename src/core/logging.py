import logging
import sys
from pathlib import Path

def setup_logging(debug: bool = False):
    """Setup logging configuration"""
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Set logging level
    level = logging.DEBUG if debug else logging.INFO
    
    # Configure logging
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / 'opensea_monitor.log'),
            logging.FileHandler(log_dir / 'error.log', level=logging.ERROR)
        ]
    )
    
    # Suppress noisy loggers
    logging.getLogger('websockets').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)
    
    # Log startup message
    logging.info("Logging system initialized")