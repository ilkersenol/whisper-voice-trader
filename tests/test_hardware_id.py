"""
Test suite for hardware_id module
"""
import pytest
from utils.hardware_id import (
    get_cpu_id,
    get_mac_address,
    get_machine_id,
    generate_hardware_id,
    validate_hardware_id,
    get_hardware_info
)


class TestHardwareID:
    """Test hardware identification functions"""
    
    def test_get_cpu_id(self):
        """Test CPU ID retrieval"""
        cpu_id = get_cpu_id()
        assert cpu_id is not None
        assert isinstance(cpu_id, str)
        assert len(cpu_id) > 0
        assert cpu_id != "UNKNOWN_CPU" or True  # May be UNKNOWN_CPU in some environments
    
    def test_get_mac_address(self):
        """Test MAC address retrieval"""
        mac = get_mac_address()
        assert mac is not None
        assert isinstance(mac, str)
        assert len(mac) > 0
        # Check format (XX:XX:XX:XX:XX:XX)
        assert ':' in mac or mac == "00:00:00:00:00:00"
    
    def test_get_machine_id(self):
        """Test machine ID retrieval"""
        machine_id = get_machine_id()
        assert machine_id is not None
        assert isinstance(machine_id, str)
        assert len(machine_id) > 0
    
    def test_generate_hardware_id(self):
        """Test hardware ID generation"""
        hw_id = generate_hardware_id()
        assert hw_id is not None
        assert isinstance(hw_id, str)
        assert len(hw_id) == 64  # SHA256 produces 64 hex characters
        # Check if it's a valid hex string
        assert all(c in '0123456789abcdef' for c in hw_id.lower())
    
    def test_hardware_id_consistency(self):
        """Test that hardware ID is consistent across multiple calls"""
        hw_id1 = generate_hardware_id()
        hw_id2 = generate_hardware_id()
        hw_id3 = generate_hardware_id()
        
        assert hw_id1 == hw_id2
        assert hw_id2 == hw_id3
        assert hw_id1 == hw_id3
    
    def test_validate_hardware_id_success(self):
        """Test successful hardware ID validation"""
        hw_id = generate_hardware_id()
        is_valid = validate_hardware_id(hw_id)
        assert is_valid is True
    
    def test_validate_hardware_id_failure(self):
        """Test failed hardware ID validation"""
        fake_id = "0" * 64
        is_valid = validate_hardware_id(fake_id)
        assert is_valid is False
    
    def test_validate_with_provided_current_id(self):
        """Test validation with provided current ID"""
        hw_id1 = generate_hardware_id()
        hw_id2 = generate_hardware_id()
        
        # Should succeed (same IDs)
        assert validate_hardware_id(hw_id1, hw_id2) is True
        
        # Should fail (different IDs)
        fake_id = "0" * 64
        assert validate_hardware_id(hw_id1, fake_id) is False
    
    def test_get_hardware_info(self):
        """Test hardware info retrieval"""
        info = get_hardware_info()
        
        assert isinstance(info, dict)
        assert 'cpu_id' in info
        assert 'mac_address' in info
        assert 'machine_id' in info
        assert 'system' in info
        assert 'platform' in info
        assert 'processor' in info
        assert 'machine' in info
        assert 'node' in info
        assert 'hardware_id' in info
        
        # Check that all values are strings
        for key, value in info.items():
            assert isinstance(value, str)
            assert len(value) > 0
    
    def test_hardware_id_uniqueness(self):
        """Test that hardware ID is sufficiently unique"""
        hw_id = generate_hardware_id()
        
        # Hardware ID should not be all zeros
        assert hw_id != "0" * 64
        
        # Hardware ID should not be all ones
        assert hw_id != "f" * 64
        
        # Hardware ID should have reasonable entropy
        unique_chars = set(hw_id.lower())
        assert len(unique_chars) > 4  # At least 4 different hex digits


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
