"""
Test suite for encryption module
"""
import os
import tempfile
import pytest
from utils.encryption import EncryptionManager, generate_key, encrypt_data, decrypt_data


class TestEncryptionManager:
    """Test EncryptionManager class"""
    
    def test_key_generation(self):
        """Test encryption key generation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_file = os.path.join(tmpdir, ".test_key")
            em = EncryptionManager(key_file)
            
            assert os.path.exists(key_file)
            assert em._key is not None
            assert len(em._key) > 0
    
    def test_key_persistence(self):
        """Test that key is saved and loaded correctly"""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_file = os.path.join(tmpdir, ".test_key")
            
            # Create first instance
            em1 = EncryptionManager(key_file)
            key1 = em1._key
            
            # Create second instance (should load same key)
            em2 = EncryptionManager(key_file)
            key2 = em2._key
            
            assert key1 == key2
    
    def test_encrypt_decrypt_string(self):
        """Test encryption and decryption of string"""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_file = os.path.join(tmpdir, ".test_key")
            em = EncryptionManager(key_file)
            
            original = "test_api_key_12345"
            encrypted = em.encrypt(original)
            decrypted = em.decrypt(encrypted)
            
            assert original == decrypted
            assert encrypted != original.encode()
    
    def test_encrypt_decrypt_bytes(self):
        """Test encryption and decryption of bytes"""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_file = os.path.join(tmpdir, ".test_key")
            em = EncryptionManager(key_file)
            
            original = b"test_secret_key_67890"
            encrypted = em.encrypt(original)
            decrypted = em.decrypt(encrypted)
            
            assert original.decode() == decrypted
    
    def test_encrypt_decrypt_base64(self):
        """Test base64 encryption and decryption"""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_file = os.path.join(tmpdir, ".test_key")
            em = EncryptionManager(key_file)
            
            original = "test_api_key_base64"
            encrypted_b64 = em.encrypt_to_base64(original)
            decrypted = em.decrypt_from_base64(encrypted_b64)
            
            assert original == decrypted
            assert isinstance(encrypted_b64, str)
    
    def test_encrypt_utf8_characters(self):
        """Test encryption with UTF-8 characters"""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_file = os.path.join(tmpdir, ".test_key")
            em = EncryptionManager(key_file)
            
            original = "test_şifre_türkçe_çğıöşü"
            encrypted = em.encrypt(original)
            decrypted = em.decrypt(encrypted)
            
            assert original == decrypted
    
    def test_decrypt_with_wrong_key_fails(self):
        """Test that decryption fails with wrong key"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Encrypt with first key
            key_file1 = os.path.join(tmpdir, ".key1")
            em1 = EncryptionManager(key_file1)
            encrypted = em1.encrypt("test_data")
            
            # Try to decrypt with second key
            key_file2 = os.path.join(tmpdir, ".key2")
            em2 = EncryptionManager(key_file2)
            
            with pytest.raises(Exception):
                em2.decrypt(encrypted)
    
    def test_encrypt_empty_string(self):
        """Test encryption of empty string"""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_file = os.path.join(tmpdir, ".test_key")
            em = EncryptionManager(key_file)
            
            original = ""
            encrypted = em.encrypt(original)
            decrypted = em.decrypt(encrypted)
            
            assert original == decrypted
    
    def test_encrypt_long_string(self):
        """Test encryption of long string"""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_file = os.path.join(tmpdir, ".test_key")
            em = EncryptionManager(key_file)
            
            original = "A" * 10000
            encrypted = em.encrypt(original)
            decrypted = em.decrypt(encrypted)
            
            assert original == decrypted


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    def test_generate_key(self):
        """Test key generation function"""
        key = generate_key()
        assert key is not None
        assert len(key) > 0
    
    def test_encrypt_decrypt_with_custom_key(self):
        """Test encryption with custom key"""
        key = generate_key()
        original = "test_data"
        encrypted = encrypt_data(original, key)
        decrypted = decrypt_data(encrypted, key)
        
        assert original == decrypted


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
