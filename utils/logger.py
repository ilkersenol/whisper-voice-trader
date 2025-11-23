"""
Logger Module - Centralized Logging Configuration
"""
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

def get_logger(name: str = "WhisperVoiceTrader") -> logging.Logger:
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        log_dir = Path(__file__).parent.parent / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        app_log = log_dir / "app.log"
        file_handler = RotatingFileHandler(app_log, maxBytes=10*1024*1024, backupCount=5)
        file_handler.setLevel(logging.DEBUG)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger

def get_trade_logger() -> logging.Logger:
    logger = logging.getLogger("TradeLogger")
    
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        log_dir = Path(__file__).parent.parent / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        trade_log = log_dir / "trades.log"
        handler = RotatingFileHandler(trade_log, maxBytes=5*1024*1024, backupCount=10)
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger
