"""
Logger Module - Centralized Logging Configuration
Windows-compatible with file locking handling
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


class SafeRotatingFileHandler(RotatingFileHandler):
    """
    Windows'ta dosya kilidi sorunlarını yöneten RotatingFileHandler.
    Rotation başarısız olursa sessizce devam eder.
    """
    def doRollover(self):
        try:
            super().doRollover()
        except (PermissionError, OSError) as e:
            # Windows'ta dosya kilitli olabilir, yoksay
            pass
    
    def emit(self, record):
        try:
            super().emit(record)
        except (PermissionError, OSError):
            # Dosyaya yazılamıyorsa sadece console'a yaz
            pass


def get_logger(name: str = "WhisperVoiceTrader") -> logging.Logger:
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        log_dir = Path(__file__).parent.parent / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        app_log = log_dir / "app.log"
        
        # File handler - Windows uyumlu, delay=True ile
        try:
            file_handler = SafeRotatingFileHandler(
                app_log, 
                maxBytes=10*1024*1024, 
                backupCount=5,
                delay=True,  # Dosyayı hemen açma
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception:
            # Dosya oluşturulamazsa sadece console kullan
            pass
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    return logger


def get_trade_logger() -> logging.Logger:
    logger = logging.getLogger("TradeLogger")
    
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        log_dir = Path(__file__).parent.parent / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        trade_log = log_dir / "trades.log"
        
        try:
            handler = SafeRotatingFileHandler(
                trade_log, 
                maxBytes=5*1024*1024, 
                backupCount=10,
                delay=True,
                encoding='utf-8'
            )
            
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s', 
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        except Exception:
            pass
    
    return logger
