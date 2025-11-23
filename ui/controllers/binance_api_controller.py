"""Binance API Settings Dialog Controller"""
from PyQt5.QtWidgets import QDialog, QMessageBox
from ui.generated.ui_binance_api_settings_dialog import Ui_BinanceApiSettingsDialog
from database.db_manager import get_db
from utils.validators import validate_api_key, validate_secret_key
from utils.logger import get_logger

logger = get_logger(__name__)


class BinanceApiController(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_BinanceApiSettingsDialog()
        self.ui.setupUi(self)
        self.db = get_db()
        
        # Connect buttons
        self.ui.btnSave.clicked.connect(self.save_keys)
        self.ui.btnCancel.clicked.connect(self.reject)
        self.ui.btnTest.clicked.connect(self.test_connection)
        
        # Load existing keys
        self.load_keys()
    
    def load_keys(self):
        """Load existing API keys"""
        try:
            keys = self.db.load_api_keys('binance', decrypt=True)
            if keys:
                self.ui.lineEditApiKey.setText(keys['api_key'])
                self.ui.lineEditSecretKey.setText(keys['secret_key'])
                logger.info("Binance keys loaded")
        except Exception as e:
            logger.error(f"Failed to load keys: {e}")
    
    def save_keys(self):
        """Save API keys"""
        api_key = self.ui.lineEditApiKey.text().strip()
        secret_key = self.ui.lineEditSecretKey.text().strip()
        
        # Validate
        valid, msg = validate_api_key(api_key)
        if not valid:
            QMessageBox.warning(self, "Invalid API Key", msg)
            return
        
        valid, msg = validate_secret_key(secret_key)
        if not valid:
            QMessageBox.warning(self, "Invalid Secret Key", msg)
            return
        
        # Save
        try:
            success = self.db.save_api_keys('binance', api_key, secret_key, encrypted=False)
            if success:
                QMessageBox.information(self, "Success", "API keys saved!")
                logger.info("Binance keys saved")
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Failed to save keys")
        except Exception as e:
            logger.error(f"Save error: {e}")
            QMessageBox.critical(self, "Error", str(e))
    
    def test_connection(self):
        """Test connection (placeholder)"""
        QMessageBox.information(
            self, 
            "Test Connection",
            "Connection test will be implemented with CCXT.\nKeys are valid and saved."
        )