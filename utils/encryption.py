"""
Encryption Module - AES-256 encryption for sensitive data
Uses Fernet (AES-256 CBC + HMAC) for symmetric encryption
"""
import os
import base64
from pathlib import Path
from typing import Union, Optional
from cryptography.fernet import Fernet, InvalidToken
from .logger import get_logger

logger = get_logger(__name__)


class EncryptionManager:
    """Manage encryption/decryption operations"""
    
    def __init__(self, key_file: Optional[str] = None):
        """
        Initialize encryption manager
        
        Args:
            key_file: Path to encryption key file. If None, uses default location.
        """
        if key_file is None:
            key_dir = Path(__file__).parent.parent / "data" / "config"
            key_dir.mkdir(parents=True, exist_ok=True)
            key_file = str(key_dir / ".encryption_key")
        
        self.key_file = key_file
        self._key: Optional[bytes] = None
        self._cipher: Optional[Fernet] = None
        self._load_or_generate_key()
    
    def _load_or_generate_key(self):
        """Load existing key or generate new one"""
        if os.path.exists(self.key_file):
            try:
                with open(self.key_file, 'rb') as f:
                    self._key = f.read()
                logger.info("Encryption key loaded")
            except Exception as e:
                logger.error(f"Failed to load encryption key: {e}")
                raise
        else:
            self._key = Fernet.generate_key()
            try:
                with open(self.key_file, 'wb') as f:
                    f.write(self._key)
                # Set restrictive permissions on Unix-like systems
                if os.name != 'nt':  # Not Windows
                    os.chmod(self.key_file, 0o600)
                logger.info(f"New encryption key generated and saved to {self.key_file}")
            except Exception as e:
                logger.error(f"Failed to save encryption key: {e}")
                raise
        
        self._cipher = Fernet(self._key)
    
    def encrypt(self, data: Union[str, bytes]) -> bytes:
        """
        Encrypt data
        
        Args:
            data: String or bytes to encrypt
            
        Returns:
            Encrypted bytes
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        try:
            encrypted = self._cipher.encrypt(data)
            return encrypted
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt(self, encrypted_data: bytes) -> str:
        """
        Decrypt data
        
        Args:
            encrypted_data: Encrypted bytes
            
        Returns:
            Decrypted string
        """
        try:
            decrypted = self._cipher.decrypt(encrypted_data)
            return decrypted.decode('utf-8')
        except InvalidToken:
            logger.error("Decryption failed: Invalid token or corrupted data")
            raise
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise
    
    def encrypt_to_base64(self, data: Union[str, bytes]) -> str:
        """
        Encrypt data and return base64 string
        
        Args:
            data: String or bytes to encrypt
            
        Returns:
            Base64 encoded encrypted string
        """
        encrypted = self.encrypt(data)
        return base64.b64encode(encrypted).decode('utf-8')
    
    def decrypt_from_base64(self, base64_data: str) -> str:
        """
        Decrypt from base64 string
        
        Args:
            base64_data: Base64 encoded encrypted string
            
        Returns:
            Decrypted string
        """
        encrypted = base64.b64decode(base64_data.encode('utf-8'))
        return self.decrypt(encrypted)


# Global instance
_encryption_instance: Optional[EncryptionManager] = None


def get_encryption_manager() -> EncryptionManager:
    """Get global encryption manager instance"""
    global _encryption_instance
    if _encryption_instance is None:
        _encryption_instance = EncryptionManager()
    return _encryption_instance


# Convenience functions
def generate_key() -> bytes:
    """Generate a new Fernet key"""
    return Fernet.generate_key()


def encrypt_data(data: str, key: Optional[bytes] = None) -> bytes:
    """Encrypt data with key (uses global instance if key not provided)"""
    if key:
        cipher = Fernet(key)
        return cipher.encrypt(data.encode('utf-8'))
    return get_encryption_manager().encrypt(data)


def decrypt_data(encrypted_data: bytes, key: Optional[bytes] = None) -> str:
    """Decrypt data with key (uses global instance if key not provided)"""
    if key:
        cipher = Fernet(key)
        return cipher.decrypt(encrypted_data).decode('utf-8')
    return get_encryption_manager().decrypt(encrypted_data)
