"""
Hardware ID Module - Generate unique hardware fingerprint
Cross-platform hardware identification for licensing
"""
import hashlib
import platform
import uuid
import subprocess
from typing import Optional
from .logger import get_logger

logger = get_logger(__name__)


def get_cpu_id() -> str:
    """
    Get CPU ID or processor identifier
    
    Returns:
        CPU identifier string
    """
    try:
        system = platform.system()
        
        if system == "Windows":
            # Windows: Use WMIC to get processor ID
            try:
                output = subprocess.check_output(
                    "wmic cpu get ProcessorId",
                    shell=True,
                    stderr=subprocess.DEVNULL
                ).decode().strip()
                lines = output.split('\n')
                if len(lines) > 1:
                    cpu_id = lines[1].strip()
                    if cpu_id:
                        return cpu_id
            except Exception:
                pass
        
        elif system == "Linux":
            # Linux: Try to get CPU info from /proc/cpuinfo
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if 'Serial' in line or 'model name' in line:
                            parts = line.split(':')
                            if len(parts) > 1:
                                return parts[1].strip()
            except Exception:
                pass
        
        elif system == "Darwin":  # macOS
            # macOS: Use system_profiler
            try:
                output = subprocess.check_output(
                    ["system_profiler", "SPHardwareDataType"],
                    stderr=subprocess.DEVNULL
                ).decode()
                for line in output.split('\n'):
                    if 'Serial Number' in line or 'Hardware UUID' in line:
                        parts = line.split(':')
                        if len(parts) > 1:
                            return parts[1].strip()
            except Exception:
                pass
        
        # Fallback: Use processor info
        processor = platform.processor()
        if processor:
            return processor
        
        # Last resort: Use machine info
        return platform.machine()
        
    except Exception as e:
        logger.warning(f"Failed to get CPU ID: {e}")
        return "UNKNOWN_CPU"


def get_mac_address() -> str:
    """
    Get MAC address of the first network interface
    
    Returns:
        MAC address string
    """
    try:
        mac = uuid.getnode()
        mac_str = ':'.join(('%012X' % mac)[i:i+2] for i in range(0, 12, 2))
        return mac_str
    except Exception as e:
        logger.warning(f"Failed to get MAC address: {e}")
        return "00:00:00:00:00:00"


def get_machine_id() -> str:
    """
    Get machine ID (varies by OS)
    
    Returns:
        Machine ID string
    """
    try:
        system = platform.system()
        
        if system == "Linux":
            # Try /etc/machine-id first
            try:
                with open('/etc/machine-id', 'r') as f:
                    return f.read().strip()
            except Exception:
                pass
            
            # Try /var/lib/dbus/machine-id
            try:
                with open('/var/lib/dbus/machine-id', 'r') as f:
                    return f.read().strip()
            except Exception:
                pass
        
        elif system == "Windows":
            # Windows: Use computer name and domain
            try:
                computer_name = platform.node()
                return computer_name
            except Exception:
                pass
        
        elif system == "Darwin":  # macOS
            # macOS: Use IOPlatformUUID
            try:
                output = subprocess.check_output(
                    ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                    stderr=subprocess.DEVNULL
                ).decode()
                for line in output.split('\n'):
                    if 'IOPlatformUUID' in line:
                        parts = line.split('=')
                        if len(parts) > 1:
                            return parts[1].strip().strip('"')
            except Exception:
                pass
        
        # Fallback
        return platform.node()
        
    except Exception as e:
        logger.warning(f"Failed to get machine ID: {e}")
        return "UNKNOWN_MACHINE"


def generate_hardware_id() -> str:
    """
    Generate unique hardware fingerprint by combining multiple hardware identifiers
    
    Returns:
        SHA256 hash of combined hardware identifiers
    """
    try:
        # Collect multiple hardware identifiers
        cpu_id = get_cpu_id()
        mac_addr = get_mac_address()
        machine_id = get_machine_id()
        system_info = f"{platform.system()}-{platform.machine()}"
        
        # Combine all identifiers
        combined = f"{cpu_id}|{mac_addr}|{machine_id}|{system_info}"
        
        # Generate SHA256 hash
        hardware_hash = hashlib.sha256(combined.encode('utf-8')).hexdigest()
        
        logger.info(f"Hardware ID generated: {hardware_hash[:16]}...")
        return hardware_hash
        
    except Exception as e:
        logger.error(f"Failed to generate hardware ID: {e}")
        raise


def validate_hardware_id(stored_id: str, current_id: Optional[str] = None) -> bool:
    """
    Validate if stored hardware ID matches current hardware
    
    Args:
        stored_id: Previously stored hardware ID
        current_id: Current hardware ID (generated if not provided)
        
    Returns:
        True if IDs match, False otherwise
    """
    try:
        if current_id is None:
            current_id = generate_hardware_id()
        
        is_valid = stored_id == current_id
        
        if is_valid:
            logger.info("Hardware ID validation successful")
        else:
            logger.warning("Hardware ID validation failed - mismatch detected")
        
        return is_valid
        
    except Exception as e:
        logger.error(f"Hardware ID validation error: {e}")
        return False


def get_hardware_info() -> dict:
    """
    Get detailed hardware information
    
    Returns:
        Dictionary with hardware details
    """
    return {
        "cpu_id": get_cpu_id(),
        "mac_address": get_mac_address(),
        "machine_id": get_machine_id(),
        "system": platform.system(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "machine": platform.machine(),
        "node": platform.node(),
        "hardware_id": generate_hardware_id()
    }
