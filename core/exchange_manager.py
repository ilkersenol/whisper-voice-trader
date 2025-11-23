"""
Whisper Voice Trader - Exchange Manager
Unified interface for cryptocurrency exchanges
"""
import ccxt
from typing import Optional, Dict, Any, List
from utils.logger import get_logger
from database.db_manager import get_db

logger = get_logger(__name__)


class ExchangeManager:
    """
    Manages connections and operations with cryptocurrency exchanges
    
    Features:
    - Multi-exchange support (Binance, ByBit, KuCoin, MEXC, OKX)
    - Unified API interface
    - Balance management
    - Market data retrieval
    - Error handling
    """
    
    # Supported exchanges
    SUPPORTED_EXCHANGES = {
        'binance': ccxt.binance,
        'bybit': ccxt.bybit,
        'kucoin': ccxt.kucoin,
        'mexc': ccxt.mexc,
        'okx': ccxt.okx
    }
    
    def __init__(self, db_manager=None):
        """
        Initialize Exchange Manager
        
        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager or get_db()
        self.exchanges: Dict[str, ccxt.Exchange] = {}
        self.active_exchange: Optional[str] = None
        
        logger.info("ExchangeManager initialized")
    
    def connect_exchange(self, 
                        exchange_name: str, 
                        api_key: str, 
                        secret_key: str,
                        testnet: bool = True,
                        passphrase: Optional[str] = None) -> bool:
        """
        Connect to an exchange
        
        Args:
            exchange_name: Exchange name (binance/bybit/kucoin/mexc/okx)
            api_key: API key
            secret_key: Secret key
            testnet: Use testnet/sandbox mode
            passphrase: Passphrase (for OKX, KuCoin)
            
        Returns:
            bool: True if connection successful
        """
        try:
            exchange_name = exchange_name.lower()
            
            if exchange_name not in self.SUPPORTED_EXCHANGES:
                logger.error(f"Unsupported exchange: {exchange_name}")
                return False
            
            # Get exchange class
            exchange_class = self.SUPPORTED_EXCHANGES[exchange_name]
            
            # Configure exchange
            config = {
                'apiKey': api_key,
                'secret': secret_key,
                'enableRateLimit': True,
                'timeout': 30000,
            }
            
            # Add passphrase if provided (OKX, KuCoin)
            if passphrase:
                config['password'] = passphrase
            
            # Exchange-specific configuration
            if exchange_name == 'binance':
                config['options'] = {
                    'defaultType': 'future',
                    'adjustForTimeDifference': True
                }
            elif exchange_name == 'bybit':
                config['options'] = {
                    'defaultType': 'future'
                }
            elif exchange_name == 'okx':
                config['options'] = {
                    'defaultType': 'swap'
                }
            
            # Create exchange instance
            exchange = exchange_class(config)
            
            # Enable sandbox/testnet mode
            if testnet:
                try:
                    exchange.set_sandbox_mode(True)
                    logger.info(f"✅ {exchange_name} sandbox mode enabled")
                except Exception as e:
                    logger.warning(f"Could not enable sandbox mode: {e}")
            
            # Test connection
            balance = exchange.fetch_balance()
            logger.info(f"✅ Connected to {exchange_name}")
            
            # Store exchange
            self.exchanges[exchange_name] = exchange
            self.active_exchange = exchange_name
            
            # Update database
            self.db.update_exchange_status(exchange_name, is_connected=True)
            
            return True
            
        except ccxt.AuthenticationError as e:
            logger.error(f"Authentication failed for {exchange_name}: {e}")
            return False
        except ccxt.NetworkError as e:
            logger.error(f"Network error connecting to {exchange_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to {exchange_name}: {e}", exc_info=True)
            return False
    
    def disconnect_exchange(self, exchange_name: str) -> bool:
        """
        Disconnect from an exchange
        
        Args:
            exchange_name: Exchange name
            
        Returns:
            bool: True if disconnected successfully
        """
        try:
            exchange_name = exchange_name.lower()
            
            if exchange_name in self.exchanges:
                del self.exchanges[exchange_name]
                
                if self.active_exchange == exchange_name:
                    self.active_exchange = None
                
                # Update database
                self.db.update_exchange_status(exchange_name, is_connected=False)
                
                logger.info(f"Disconnected from {exchange_name}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error disconnecting from {exchange_name}: {e}")
            return False
    
    def get_exchange(self, exchange_name: Optional[str] = None) -> Optional[ccxt.Exchange]:
        """
        Get exchange instance
        
        Args:
            exchange_name: Exchange name (uses active if None)
            
        Returns:
            ccxt.Exchange: Exchange instance or None
        """
        if exchange_name:
            return self.exchanges.get(exchange_name.lower())
        
        if self.active_exchange:
            return self.exchanges.get(self.active_exchange)
        
        return None
    
    def set_active_exchange(self, exchange_name: str) -> bool:
        """
        Set active exchange
        
        Args:
            exchange_name: Exchange name
            
        Returns:
            bool: True if set successfully
        """
        exchange_name = exchange_name.lower()
        
        if exchange_name in self.exchanges:
            self.active_exchange = exchange_name
            logger.info(f"Active exchange set to: {exchange_name}")
            return True
        
        logger.warning(f"Exchange not connected: {exchange_name}")
        return False
    
    def get_balance(self, exchange_name: Optional[str] = None) -> Dict[str, float]:
        """
        Get account balance
        
        Args:
            exchange_name: Exchange name (uses active if None)
            
        Returns:
            dict: Balance information
        """
        try:
            exchange = self.get_exchange(exchange_name)
            if not exchange:
                logger.error("No exchange available")
                return {}
            
            balance = exchange.fetch_balance()
            
            # Extract USDT balance and total
            usdt_balance = balance.get('total', {}).get('USDT', 0.0)
            free_balance = balance.get('free', {}).get('USDT', 0.0)
            used_balance = balance.get('used', {}).get('USDT', 0.0)
            
            return {
                'total': usdt_balance,
                'free': free_balance,
                'used': used_balance,
                'currency': 'USDT'
            }
            
        except Exception as e:
            logger.error(f"Error fetching balance: {e}", exc_info=True)
            return {}
    
    def get_ticker(self, symbol: str, exchange_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get ticker data for a symbol
        
        Args:
            symbol: Trading symbol (e.g., 'BTC/USDT')
            exchange_name: Exchange name (uses active if None)
            
        Returns:
            dict: Ticker data
        """
        try:
            exchange = self.get_exchange(exchange_name)
            if not exchange:
                logger.error("No exchange available")
                return {}
            
            ticker = exchange.fetch_ticker(symbol)
            
            return {
                'symbol': ticker.get('symbol'),
                'last': ticker.get('last'),
                'bid': ticker.get('bid'),
                'ask': ticker.get('ask'),
                'high': ticker.get('high'),
                'low': ticker.get('low'),
                'volume': ticker.get('baseVolume'),
                'timestamp': ticker.get('timestamp')
            }
            
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {e}")
            return {}
    
    def get_markets(self, exchange_name: Optional[str] = None) -> List[str]:
        """
        Get available markets (symbols)
        
        Args:
            exchange_name: Exchange name (uses active if None)
            
        Returns:
            list: List of trading symbols
        """
        try:
            exchange = self.get_exchange(exchange_name)
            if not exchange:
                logger.error("No exchange available")
                return []
            
            markets = exchange.load_markets()
            
            # Filter for futures/perpetual contracts with USDT
            futures_symbols = []
            for symbol, market in markets.items():
                market_type = market.get('type', '').lower()
                is_future = market.get('future', False)
                is_swap = market.get('swap', False)
                
                if (market_type in ['future', 'swap'] or is_future or is_swap) and 'USDT' in symbol:
                    # Clean symbol
                    clean_symbol = symbol.replace(':USDT', '').replace('/USDT', '/USDT')
                    futures_symbols.append(clean_symbol)
            
            return sorted(list(set(futures_symbols)))
            
        except Exception as e:
            logger.error(f"Error fetching markets: {e}", exc_info=True)
            return []
    
    def validate_symbol(self, symbol: str, exchange_name: Optional[str] = None) -> bool:
        """
        Validate if symbol exists on exchange
        
        Args:
            symbol: Trading symbol
            exchange_name: Exchange name (uses active if None)
            
        Returns:
            bool: True if symbol is valid
        """
        try:
            exchange = self.get_exchange(exchange_name)
            if not exchange:
                return False
            
            markets = exchange.load_markets()
            
            # Try different symbol formats
            symbol_formats = [
                symbol,
                f"{symbol}/USDT",
                f"{symbol}:USDT",
                symbol.replace('USDT', '/USDT'),
                symbol.replace('/USDT', ':USDT')
            ]
            
            for sym_format in symbol_formats:
                if sym_format in markets:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error validating symbol {symbol}: {e}")
            return False
    
    def normalize_symbol(self, symbol: str, exchange_name: Optional[str] = None) -> Optional[str]:
        """
        Normalize symbol to exchange format
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT' or 'BTC/USDT')
            exchange_name: Exchange name (uses active if None)
            
        Returns:
            str: Normalized symbol or None
        """
        try:
            exchange = self.get_exchange(exchange_name)
            if not exchange:
                return None
            
            markets = exchange.load_markets()
            
            # Try different formats
            symbol_formats = [
                symbol,
                f"{symbol}/USDT",
                f"{symbol}:USDT",
                symbol.replace('USDT', '/USDT'),
                symbol.replace('/USDT', ':USDT')
            ]
            
            for sym_format in symbol_formats:
                if sym_format in markets:
                    return sym_format
            
            # Try removing USDT and adding back
            base = symbol.replace('USDT', '').replace('/USDT', '').replace(':USDT', '')
            for suffix in ['/USDT', ':USDT', 'USDT']:
                test_symbol = f"{base}{suffix}"
                if test_symbol in markets:
                    return test_symbol
            
            return None
            
        except Exception as e:
            logger.error(f"Error normalizing symbol {symbol}: {e}")
            return None
    
    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get current connection status
        
        Returns:
            dict: Connection status information
        """
        return {
            'connected_exchanges': list(self.exchanges.keys()),
            'active_exchange': self.active_exchange,
            'total_connections': len(self.exchanges)
        }
    
    def cleanup(self):
        """Clean up all exchange connections"""
        try:
            for exchange_name in list(self.exchanges.keys()):
                self.disconnect_exchange(exchange_name)
            
            logger.info("ExchangeManager cleaned up")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Singleton instance
_exchange_manager_instance = None

def get_exchange_manager() -> ExchangeManager:
    """Get singleton ExchangeManager instance"""
    global _exchange_manager_instance
    if _exchange_manager_instance is None:
        _exchange_manager_instance = ExchangeManager()
    return _exchange_manager_instance