"""Configuration Manager - JSON based config file management"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from .logger import get_logger

logger = get_logger(__name__)


class ConfigManager:
    """Manage application configuration in JSON format"""
    
    def __init__(self, config_path: str = "data/config/settings.json"):
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self._ensure_config_directory()
        self._load_or_create_default()
    
    def _ensure_config_directory(self):
        """Create config directory if not exists"""
        config_dir = os.path.dirname(self.config_path)
        if config_dir:
            Path(config_dir).mkdir(parents=True, exist_ok=True)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "app": {
                "version": "1.0.0",
                "language": "tr",
                "theme": "dark",
                "startup_check_updates": True
            },
            "whisper": {
                "model_size": "base",
                "use_gpu": True,
                "wake_word": "Whisper",
                "active_mode_duration": 15,
                "min_confidence": 0.7
            },
            "tts": {
                "enabled": True,
                "language": "turkish",
                "rate": 150,
                "volume": 1.0
            },
            "trading": {
                "paper_trading": True,
                "paper_balance": 10000.0,
                "default_leverage": 10,
                "position_mode": "one-way",
                "default_order_type": "market",
                "max_positions": 5,
                "max_position_size_percent": 20.0,
                "daily_loss_limit": 500.0
            },
            "risk": {
                "max_positions": 5,
                "max_position_size_percent": 20.0,
                "daily_loss_limit": 500.0,
                "stop_loss_enabled": True,
                "take_profit_enabled": True
            },
            "exchange": {
                "default": "binance",
                "environment": "testnet"
            },
            "ui": {
                "show_charts": True,
                "auto_scroll_logs": True,
                "confirmation_dialogs": True,
                "sound_alerts": True
            }
        }
    
    def _load_or_create_default(self):
        """Load config from file or create default"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.info(f"Config loaded from {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                self.config = self._get_default_config()
                self.save()
        else:
            logger.info("Config file not found, creating default")
            self.config = self._get_default_config()
            self.save()
    
    def save(self):
        """Save config to file"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            logger.info(f"Config saved to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by key (supports nested keys with dot notation)"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """Set config value by key (supports nested keys with dot notation)"""
        keys = key.split('.')
        config = self.config
        
        # Navigate to the nested location
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value
        logger.debug(f"Config updated: {key} = {value}")
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire config section"""
        return self.config.get(section, {})
    
    def set_section(self, section: str, data: Dict[str, Any]):
        """Set entire config section"""
        self.config[section] = data
        logger.debug(f"Config section updated: {section}")
    
    def reload(self):
        """Reload config from file"""
        self._load_or_create_default()
    
    def reset_to_default(self):
        """Reset config to default values"""
        self.config = self._get_default_config()
        self.save()
        logger.info("Config reset to default")
    
    def get_all(self) -> Dict[str, Any]:
        """Get all config"""
        return self.config.copy()
