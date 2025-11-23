"""
Test suite for validators module
"""
import pytest
from utils.validators import (
    validate_api_key,
    validate_secret_key,
    validate_symbol,
    validate_quantity,
    validate_price,
    validate_leverage,
    validate_percentage,
    validate_order_side,
    validate_order_type,
    validate_time_in_force,
    validate_exchange_name
)


class TestAPIKeyValidation:
    """Test API key validation"""
    
    def test_valid_api_key(self):
        """Test valid API key"""
        valid, msg = validate_api_key("abcd1234efgh5678")
        assert valid is True
        assert msg == ""
    
    def test_api_key_too_short(self):
        """Test API key that is too short"""
        valid, msg = validate_api_key("short")
        assert valid is False
        assert "too short" in msg.lower()
    
    def test_api_key_too_long(self):
        """Test API key that is too long"""
        valid, msg = validate_api_key("a" * 200)
        assert valid is False
        assert "too long" in msg.lower()
    
    def test_api_key_empty(self):
        """Test empty API key"""
        valid, msg = validate_api_key("")
        assert valid is False
        assert "empty" in msg.lower()
    
    def test_api_key_invalid_characters(self):
        """Test API key with invalid characters"""
        valid, msg = validate_api_key("abc@def#ghi!jklm1234")  # 20 chars, has invalid chars
        assert valid is False
        assert "invalid characters" in msg.lower()
    
    def test_api_key_with_whitespace(self):
        """Test API key with whitespace (should be stripped)"""
        valid, msg = validate_api_key("  abcd1234efgh5678  ")
        assert valid is True


class TestSecretKeyValidation:
    """Test secret key validation"""
    
    def test_valid_secret_key(self):
        """Test valid secret key"""
        valid, msg = validate_secret_key("abcd1234efgh5678ijk+/=")
        assert valid is True
        assert msg == ""
    
    def test_secret_key_too_short(self):
        """Test secret key that is too short"""
        valid, msg = validate_secret_key("short")
        assert valid is False
        assert "too short" in msg.lower()


class TestSymbolValidation:
    """Test symbol validation"""
    
    def test_valid_symbol_no_separator(self):
        """Test valid symbol without separator"""
        valid, msg = validate_symbol("BTCUSDT")
        assert valid is True
        assert msg == ""
    
    def test_valid_symbol_with_separator(self):
        """Test valid symbol with separator"""
        valid, msg = validate_symbol("BTC/USDT")
        assert valid is True
        assert msg == ""
    
    def test_symbol_lowercase(self):
        """Test symbol in lowercase (should be converted)"""
        valid, msg = validate_symbol("btcusdt")
        assert valid is True
    
    def test_symbol_too_short(self):
        """Test symbol that is too short"""
        valid, msg = validate_symbol("BTC")
        assert valid is False
        assert "too short" in msg.lower()
    
    def test_symbol_empty(self):
        """Test empty symbol"""
        valid, msg = validate_symbol("")
        assert valid is False
        assert "empty" in msg.lower()
    
    def test_symbol_invalid_format(self):
        """Test symbol with invalid format"""
        valid, msg = validate_symbol("BTC-USDT!")
        assert valid is False
        assert "invalid" in msg.lower()


class TestQuantityValidation:
    """Test quantity validation"""
    
    def test_valid_quantity(self):
        """Test valid quantity"""
        valid, msg = validate_quantity(0.5, min_qty=0.001, max_qty=100)
        assert valid is True
        assert msg == ""
    
    def test_quantity_below_minimum(self):
        """Test quantity below minimum"""
        valid, msg = validate_quantity(0.0001, min_qty=0.001)
        assert valid is False
        assert "greater than" in msg.lower()
    
    def test_quantity_above_maximum(self):
        """Test quantity above maximum"""
        valid, msg = validate_quantity(150, max_qty=100)
        assert valid is False
        assert "exceed" in msg.lower()
    
    def test_quantity_invalid_type(self):
        """Test invalid quantity type"""
        valid, msg = validate_quantity("not_a_number")
        assert valid is False
        assert "valid number" in msg.lower()
    
    def test_quantity_too_many_decimals(self):
        """Test quantity with too many decimals"""
        valid, msg = validate_quantity(0.123456789)
        assert valid is False
        assert "decimal places" in msg.lower()


class TestPriceValidation:
    """Test price validation"""
    
    def test_valid_price(self):
        """Test valid price"""
        valid, msg = validate_price(50000.50)
        assert valid is True
        assert msg == ""
    
    def test_price_below_minimum(self):
        """Test price below minimum"""
        valid, msg = validate_price(0, min_price=0.01)
        assert valid is False
        assert "greater than" in msg.lower()


class TestLeverageValidation:
    """Test leverage validation"""
    
    def test_valid_leverage(self):
        """Test valid leverage"""
        valid, msg = validate_leverage(10)
        assert valid is True
        assert msg == ""
    
    def test_leverage_below_minimum(self):
        """Test leverage below minimum"""
        valid, msg = validate_leverage(0)
        assert valid is False
        assert "at least" in msg.lower()
    
    def test_leverage_above_maximum(self):
        """Test leverage above maximum"""
        valid, msg = validate_leverage(150, max_leverage=125)
        assert valid is False
        assert "exceed" in msg.lower()
    
    def test_leverage_invalid_type(self):
        """Test invalid leverage type"""
        valid, msg = validate_leverage("ten")
        assert valid is False
        assert "integer" in msg.lower()


class TestPercentageValidation:
    """Test percentage validation"""
    
    def test_valid_percentage(self):
        """Test valid percentage"""
        valid, msg = validate_percentage(50.5)
        assert valid is True
        assert msg == ""
    
    def test_percentage_below_minimum(self):
        """Test percentage below minimum"""
        valid, msg = validate_percentage(-10)
        assert valid is False
        assert "at least" in msg.lower()
    
    def test_percentage_above_maximum(self):
        """Test percentage above maximum"""
        valid, msg = validate_percentage(150)
        assert valid is False
        assert "exceed" in msg.lower()


class TestOrderSideValidation:
    """Test order side validation"""
    
    def test_valid_order_sides(self):
        """Test all valid order sides"""
        for side in ['BUY', 'SELL', 'LONG', 'SHORT']:
            valid, msg = validate_order_side(side)
            assert valid is True
            assert msg == ""
    
    def test_order_side_lowercase(self):
        """Test order side in lowercase"""
        valid, msg = validate_order_side("buy")
        assert valid is True
    
    def test_invalid_order_side(self):
        """Test invalid order side"""
        valid, msg = validate_order_side("HOLD")
        assert valid is False
        assert "invalid" in msg.lower()


class TestOrderTypeValidation:
    """Test order type validation"""
    
    def test_valid_order_types(self):
        """Test all valid order types"""
        for order_type in ['MARKET', 'LIMIT', 'STOP_MARKET']:
            valid, msg = validate_order_type(order_type)
            assert valid is True
            assert msg == ""
    
    def test_invalid_order_type(self):
        """Test invalid order type"""
        valid, msg = validate_order_type("FOO")
        assert valid is False
        assert "invalid" in msg.lower()


class TestTimeInForceValidation:
    """Test time in force validation"""
    
    def test_valid_time_in_force(self):
        """Test valid time in force values"""
        for tif in ['GTC', 'IOC', 'FOK']:
            valid, msg = validate_time_in_force(tif)
            assert valid is True
            assert msg == ""
    
    def test_invalid_time_in_force(self):
        """Test invalid time in force"""
        valid, msg = validate_time_in_force("BAR")
        assert valid is False
        assert "invalid" in msg.lower()


class TestExchangeValidation:
    """Test exchange name validation"""
    
    def test_valid_exchanges(self):
        """Test all valid exchange names"""
        for exchange in ['binance', 'bybit', 'kucoin', 'mexc', 'okx']:
            valid, msg = validate_exchange_name(exchange)
            assert valid is True
            assert msg == ""
    
    def test_exchange_uppercase(self):
        """Test exchange name in uppercase"""
        valid, msg = validate_exchange_name("BINANCE")
        assert valid is True
    
    def test_invalid_exchange(self):
        """Test invalid exchange name"""
        valid, msg = validate_exchange_name("kraken")
        assert valid is False
        assert "unsupported" in msg.lower()
    
    def test_empty_exchange(self):
        """Test empty exchange name"""
        valid, msg = validate_exchange_name("")
        assert valid is False
        assert "empty" in msg.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
