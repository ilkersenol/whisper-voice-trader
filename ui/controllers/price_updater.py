"""Price Updater - Real-time price updates for selected symbol"""
from PyQt5.QtCore import QThread, pyqtSignal
import time
from utils.logger import get_logger

logger = get_logger(__name__)


class PriceUpdateThread(QThread):
    """Thread for real-time price updates"""
    price_updated = pyqtSignal(dict)  # {best_bid, best_ask, current_price}
    error_occurred = pyqtSignal(str)
    
    def __init__(self, exchange_name, symbol, api_key, secret_key, passphrase=None):
        super().__init__()
        self.exchange_name = exchange_name
        self.symbol = symbol
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.running = True
        self.exchange = None
    
    def run(self):
        """Fetch prices continuously"""
        try:
            import ccxt
            
            # Setup exchange
            exchange_class = getattr(ccxt, self.exchange_name)
            
            config = {
                'apiKey': self.api_key,
                'secret': self.secret_key,
                'enableRateLimit': True,
            }
            
            if self.passphrase:
                config['password'] = self.passphrase
            
            if self.exchange_name == 'binance':
                config['options'] = {'defaultType': 'future'}
            
            self.exchange = exchange_class(config)
            
            try:
                self.exchange.set_sandbox_mode(True)
            except:
                pass
            
            # Format symbol for CCXT (add :USDT back)
            ccxt_symbol = self.symbol if ':' in self.symbol else f"{self.symbol}:USDT"
            
            logger.info(f"Starting price updates for {ccxt_symbol}")
            
            while self.running:
                try:
                    # Fetch ticker for current price
                    ticker = self.exchange.fetch_ticker(ccxt_symbol)
                    
                    # Fetch order book for bid/ask (Binance minimum 5)
                    orderbook = self.exchange.fetch_order_book(ccxt_symbol, limit=5)
                    
                    # Extract prices
                    best_bid = orderbook['bids'][0][0] if orderbook['bids'] else None
                    best_ask = orderbook['asks'][0][0] if orderbook['asks'] else None
                    current_price = ticker.get('last')
                    
                    # LOG WITH INFO
                    logger.info(f"[{ccxt_symbol}] Price: {current_price}, Bid: {best_bid}, Ask: {best_ask}")
                    
                    price_data = {
                        'best_bid': best_bid,
                        'best_ask': best_ask,
                        'current_price': current_price,
                        'volume': ticker.get('quoteVolume', 0.0),
                        'change_24h': ticker.get('percentage', 0.0)
                    }
                    
                    self.price_updated.emit(price_data)
                    
                    # Wait 1 second before next update
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Price fetch error: {e}")
                    self.error_occurred.emit(str(e))
                    time.sleep(5)
            
        except Exception as e:
            logger.error(f"Price updater failed: {e}")
            self.error_occurred.emit(str(e))
    
    def stop(self):
        """Stop the price update thread"""
        self.running = False
        logger.info("Price updater stopped")