"""
Integration tests for Day 2: Encryption & API Key Management
Tests the full workflow of encrypting, storing, and retrieving API keys
"""
import os
import tempfile
import pytest
from database.db_manager import DatabaseManager
from utils.encryption import EncryptionManager
from utils.hardware_id import generate_hardware_id, validate_hardware_id
from utils.validators import validate_api_key, validate_exchange_name


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    
    db = DatabaseManager(db_path)
    db.initialize()
    
    yield db
    
    # Cleanup
    db.disconnect()
    try:
        os.remove(db_path)
        os.rmdir(tmpdir)
    except:
        pass


@pytest.fixture
def temp_encryption():
    """Create temporary encryption manager"""
    tmpdir = tempfile.mkdtemp()
    key_file = os.path.join(tmpdir, ".test_key")
    
    em = EncryptionManager(key_file)
    
    yield em
    
    # Cleanup
    try:
        os.remove(key_file)
        os.rmdir(tmpdir)
    except:
        pass


class TestFullIntegration:
    """Test complete integration of Day 2 modules"""
    
    def test_full_api_key_lifecycle(self, temp_db, temp_encryption):
        """Test complete API key lifecycle: encrypt -> save -> load -> decrypt -> delete"""
        db = temp_db
        em = temp_encryption
        
        # Test data
        test_exchange = "binance"
        test_api_key = "test_api_key_12345678"
        test_secret = "test_secret_key_87654321"
        
        # Step 1: Validate inputs
        valid_api, _ = validate_api_key(test_api_key)
        valid_exchange, _ = validate_exchange_name(test_exchange)
        assert valid_api is True
        assert valid_exchange is True
        
        # Step 2: Save encrypted keys
        success = db.save_api_keys(
            exchange=test_exchange,
            api_key=test_api_key,
            secret_key=test_secret,
            encrypted=False
        )
        assert success is True
        
        # Step 3: Load and verify keys
        keys = db.load_api_keys(test_exchange, decrypt=True)
        assert keys is not None
        assert keys['api_key'] == test_api_key
        assert keys['secret_key'] == test_secret
        
        # Step 4: Verify keys are encrypted in database
        raw_keys = db.load_api_keys(test_exchange, decrypt=False)
        assert raw_keys['api_key'] != test_api_key  # Should be encrypted
        
        # Step 5: Update connection status
        success = db.update_exchange_status(test_exchange, True)
        assert success is True
        
        # Step 6: Verify configured exchanges
        configured = db.get_configured_exchanges()
        assert test_exchange in configured
        
        # Step 7: Verify connected exchanges
        connected = db.get_connected_exchanges()
        assert test_exchange in connected
        
        # Step 8: Delete keys
        success = db.delete_api_keys(test_exchange)
        assert success is True
        
        # Step 9: Verify deletion
        keys_after = db.load_api_keys(test_exchange)
        assert keys_after is None
    
    def test_multiple_exchange_keys(self, temp_db):
        """Test managing keys for multiple exchanges"""
        db = temp_db
        
        exchanges = ['binance', 'bybit', 'kucoin']
        
        # Save keys for all exchanges
        for exchange in exchanges:
            success = db.save_api_keys(
                exchange=exchange,
                api_key=f"{exchange}_api_key",
                secret_key=f"{exchange}_secret_key",
                encrypted=False
            )
            assert success is True
        
        # Verify all are configured
        configured = db.get_configured_exchanges()
        for exchange in exchanges:
            assert exchange in configured
        
        # Load and verify each
        for exchange in exchanges:
            keys = db.load_api_keys(exchange, decrypt=True)
            assert keys is not None
            assert keys['api_key'] == f"{exchange}_api_key"
    
    def test_encryption_consistency(self, temp_encryption):
        """Test that encryption/decryption is consistent"""
        em1 = temp_encryption
        test_data = "sensitive_api_key"
        encrypted = em1.encrypt(test_data)
        
        # Same instance should decrypt correctly
        decrypted = em1.decrypt(encrypted)
        
        assert test_data == decrypted
    
    def test_hardware_id_consistency(self):
        """Test hardware ID generation consistency"""
        hw_id1 = generate_hardware_id()
        hw_id2 = generate_hardware_id()
        
        assert hw_id1 == hw_id2
        assert validate_hardware_id(hw_id1, hw_id2) is True
    
    def test_invalid_exchange_rejection(self):
        """Test that invalid exchange names are rejected"""
        valid, msg = validate_exchange_name("invalid_exchange")
        assert valid is False
        assert "unsupported" in msg.lower()
    
    def test_api_key_encryption_security(self, temp_db):
        """Test that encrypted keys cannot be easily reversed"""
        db = temp_db
        
        original_key = "super_secret_api_key_123"
        
        # Save encrypted
        db.save_api_keys(
            exchange='binance',
            api_key=original_key,
            secret_key='secret',
            encrypted=False
        )
        
        # Get raw encrypted data
        raw = db.load_api_keys('binance', decrypt=False)
        encrypted_key = raw['api_key']
        
        # Verify it's not the original
        assert encrypted_key != original_key
        
        # Verify it's base64-like (encrypted format)
        assert len(encrypted_key) > len(original_key)
    
    def test_passphrase_support(self, temp_db):
        """Test passphrase encryption for exchanges that require it"""
        db = temp_db
        
        # Save with passphrase (like KuCoin)
        success = db.save_api_keys(
            exchange='kucoin',
            api_key='kucoin_api',
            secret_key='kucoin_secret',
            passphrase='kucoin_pass',
            encrypted=False
        )
        assert success is True
        
        # Load and verify passphrase
        keys = db.load_api_keys('kucoin', decrypt=True)
        assert keys is not None
        assert keys['passphrase'] == 'kucoin_pass'
    
    def test_error_handling_no_keys(self, temp_db):
        """Test error handling when no keys exist"""
        db = temp_db
        
        # Try to load non-existent keys
        keys = db.load_api_keys('binance')
        assert keys is None
    
    def test_update_existing_keys(self, temp_db):
        """Test updating existing API keys"""
        db = temp_db
        
        # Save initial keys
        db.save_api_keys(
            exchange='binance',
            api_key='old_key',
            secret_key='old_secret',
            encrypted=False
        )
        
        # Update with new keys
        db.save_api_keys(
            exchange='binance',
            api_key='new_key',
            secret_key='new_secret',
            encrypted=False
        )
        
        # Verify new keys
        keys = db.load_api_keys('binance', decrypt=True)
        assert keys['api_key'] == 'new_key'
        assert keys['secret_key'] == 'new_secret'