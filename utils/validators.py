"""
Validators Module - Input validation for trading parameters and API keys
"""
import re
from typing import Optional, Tuple
from .logger import get_logger

logger = get_logger(__name__)


def validate_api_key(api_key: str, min_length: int = 16, max_length: int = 128) -> Tuple[bool, str]:
    """
    Validate API key format
    
    Args:
        api_key: API key string to validate
        min_length: Minimum required length
        max_length: Maximum allowed length
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not api_key:
        return False, "API key cannot be empty"
    
    if not isinstance(api_key, str):
        return False, "API key must be a string"
    
    api_key = api_key.strip()
    
    if len(api_key) < min_length:
        return False, f"API key too short (minimum {min_length} characters)"
    
    if len(api_key) > max_length:
        return False, f"API key too long (maximum {max_length} characters)"
    
    # Check for valid characters (alphanumeric, dash, underscore)
    if not re.match(r'^[A-Za-z0-9_\-]+$', api_key):
        return False, "API key contains invalid characters"
    
    return True, ""


def validate_secret_key(secret_key: str, min_length: int = 16, max_length: int = 128) -> Tuple[bool, str]:
    """
    Validate secret key format
    
    Args:
        secret_key: Secret key string to validate
        min_length: Minimum required length
        max_length: Maximum allowed length
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not secret_key:
        return False, "Secret key cannot be empty"
    
    if not isinstance(secret_key, str):
        return False, "Secret key must be a string"
    
    secret_key = secret_key.strip()
    
    if len(secret_key) < min_length:
        return False, f"Secret key too short (minimum {min_length} characters)"
    
    if len(secret_key) > max_length:
        return False, f"Secret key too long (maximum {max_length} characters)"
    
    # Secret keys typically contain alphanumeric and special characters
    if not re.match(r'^[A-Za-z0-9_\-+=\/]+$', secret_key):
        return False, "Secret key contains invalid characters"
    
    return True, ""


def validate_symbol(symbol: str) -> Tuple[bool, str]:
    """
    Validate cryptocurrency trading symbol
    
    Args:
        symbol: Trading pair symbol (e.g., BTCUSDT, BTC/USDT)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not symbol:
        return False, "Symbol cannot be empty"
    
    if not isinstance(symbol, str):
        return False, "Symbol must be a string"
    
    symbol = symbol.strip().upper()
    
    if len(symbol) < 6:
        return False, "Symbol too short"
    
    if len(symbol) > 20:
        return False, "Symbol too long"
    
    # Allow symbols with or without separator (BTCUSDT or BTC/USDT)
    if not re.match(r'^[A-Z0-9]+[/]?[A-Z0-9]+$', symbol):
        return False, "Invalid symbol format"
    
    # Check for common quote currencies
    common_quotes = ['USDT', 'USDC', 'BUSD', 'USD', 'BTC', 'ETH']
    has_valid_quote = any(symbol.endswith(quote) or f"/{quote}" in symbol for quote in common_quotes)
    
    if not has_valid_quote:
        logger.warning(f"Symbol {symbol} does not end with common quote currency")
    
    return True, ""


def validate_quantity(quantity: float, min_qty: float = 0.0, max_qty: Optional[float] = None) -> Tuple[bool, str]:
    """
    Validate order quantity
    
    Args:
        quantity: Order quantity
        min_qty: Minimum allowed quantity
        max_qty: Maximum allowed quantity (optional)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        return False, "Quantity must be a valid number"
    
    if quantity <= min_qty:
        return False, f"Quantity must be greater than {min_qty}"
    
    if max_qty is not None and quantity > max_qty:
        return False, f"Quantity cannot exceed {max_qty}"
    
    # Check for reasonable precision (max 8 decimal places)
    if len(str(quantity).split('.')[-1]) > 8 if '.' in str(quantity) else False:
        return False, "Quantity has too many decimal places (max 8)"
    
    return True, ""


def validate_price(price: float, min_price: float = 0.0, max_price: Optional[float] = None) -> Tuple[bool, str]:
    """
    Validate order price
    
    Args:
        price: Order price
        min_price: Minimum allowed price
        max_price: Maximum allowed price (optional)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        price = float(price)
    except (TypeError, ValueError):
        return False, "Price must be a valid number"
    
    if price <= min_price:
        return False, f"Price must be greater than {min_price}"
    
    if max_price is not None and price > max_price:
        return False, f"Price cannot exceed {max_price}"
    
    # Check for reasonable precision (max 8 decimal places)
    if len(str(price).split('.')[-1]) > 8 if '.' in str(price) else False:
        return False, "Price has too many decimal places (max 8)"
    
    return True, ""


def validate_leverage(leverage: int, min_leverage: int = 1, max_leverage: int = 125) -> Tuple[bool, str]:
    """
    Validate leverage value
    
    Args:
        leverage: Leverage multiplier
        min_leverage: Minimum allowed leverage
        max_leverage: Maximum allowed leverage
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        leverage = int(leverage)
    except (TypeError, ValueError):
        return False, "Leverage must be an integer"
    
    if leverage < min_leverage:
        return False, f"Leverage must be at least {min_leverage}x"
    
    if leverage > max_leverage:
        return False, f"Leverage cannot exceed {max_leverage}x"
    
    return True, ""


def validate_percentage(percentage: float, min_percent: float = 0.0, max_percent: float = 100.0) -> Tuple[bool, str]:
    """
    Validate percentage value
    
    Args:
        percentage: Percentage value
        min_percent: Minimum allowed percentage
        max_percent: Maximum allowed percentage
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        percentage = float(percentage)
    except (TypeError, ValueError):
        return False, "Percentage must be a valid number"
    
    if percentage < min_percent:
        return False, f"Percentage must be at least {min_percent}%"
    
    if percentage > max_percent:
        return False, f"Percentage cannot exceed {max_percent}%"
    
    return True, ""


def validate_order_side(side: str) -> Tuple[bool, str]:
    """
    Validate order side (buy/sell)
    
    Args:
        side: Order side
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not side:
        return False, "Order side cannot be empty"
    
    side = side.strip().upper()
    valid_sides = ['BUY', 'SELL', 'LONG', 'SHORT']
    
    if side not in valid_sides:
        return False, f"Invalid order side. Must be one of: {', '.join(valid_sides)}"
    
    return True, ""


def validate_order_type(order_type: str) -> Tuple[bool, str]:
    """
    Validate order type
    
    Args:
        order_type: Order type
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not order_type:
        return False, "Order type cannot be empty"
    
    order_type = order_type.strip().upper()
    valid_types = ['MARKET', 'LIMIT', 'STOP_MARKET', 'STOP_LIMIT', 'TAKE_PROFIT_MARKET', 'TAKE_PROFIT_LIMIT']
    
    if order_type not in valid_types:
        return False, f"Invalid order type. Must be one of: {', '.join(valid_types)}"
    
    return True, ""


def validate_time_in_force(tif: str) -> Tuple[bool, str]:
    """
    Validate time in force parameter
    
    Args:
        tif: Time in force value
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not tif:
        return False, "Time in force cannot be empty"
    
    tif = tif.strip().upper()
    valid_tifs = ['GTC', 'IOC', 'FOK', 'GTX']
    
    if tif not in valid_tifs:
        return False, f"Invalid time in force. Must be one of: {', '.join(valid_tifs)}"
    
    return True, ""


def validate_exchange_name(exchange: str) -> Tuple[bool, str]:
    """
    Validate exchange name
    
    Args:
        exchange: Exchange name
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not exchange:
        return False, "Exchange name cannot be empty"
    
    exchange = exchange.strip().lower()
    supported_exchanges = ['binance', 'bybit', 'kucoin', 'mexc', 'okx']
    
    if exchange not in supported_exchanges:
        return False, f"Unsupported exchange. Must be one of: {', '.join(supported_exchanges)}"
    
    return True, ""
