"""Generic Exchange API Settings Controller"""
from PyQt5.QtWidgets import QDialog, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal
from database.db_manager import get_db
from utils.validators import validate_api_key, validate_secret_key
from utils.logger import get_logger

logger = get_logger(__name__)


class ConnectionTestThread(QThread):
    """Thread for testing exchange connection"""
    finished = pyqtSignal(bool, str, dict)  # success, message, data (balance + symbols)
    
    def __init__(self, exchange_name, api_key, secret_key, passphrase=None):
        super().__init__()
        self.exchange_name = exchange_name
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
    
    def run(self):
        """Test connection in background thread"""
        try:
            import ccxt
            
            # Exchange configuration
            exchange_class = getattr(ccxt, self.exchange_name)
            
            config = {
                'apiKey': self.api_key,
                'secret': self.secret_key,
                'enableRateLimit': True,
                'timeout': 30000,
            }
            
            # Add passphrase for KuCoin
            if self.passphrase:
                config['password'] = self.passphrase
            
            # Binance için testnet desteği
            if self.exchange_name == 'binance':
                config['options'] = {'defaultType': 'future'}
            
            # Create exchange instance
            exchange = exchange_class(config)
            
            # Enable testnet/sandbox mode
            try:
                exchange.set_sandbox_mode(True)
                logger.info(f"{self.exchange_name} testnet mode enabled")
            except:
                pass
            
            # Test by fetching balance
            balance = exchange.fetch_balance()
            
            # Fetch futures markets
            markets = exchange.load_markets()
            futures_symbols = []
            
            for symbol, market in markets.items():
                # Only futures/swap markets
                if market.get('type') in ['future', 'swap'] or market.get('future') or market.get('swap'):
                    # Only USDT pairs
                    if 'USDT' in symbol:
                        clean_symbol = symbol.replace(':USDT', '')
                        futures_symbols.append(clean_symbol)
            
            # Sort symbols
            futures_symbols = sorted(list(set(futures_symbols)))
            
            # Success
            total_balance = balance.get('total', {})
            currencies = [f"{k}: {v}" for k, v in total_balance.items() if v > 0][:3]
            
            if currencies:
                msg = f"Connected successfully! (Testnet)\n\nBalance preview:\n" + "\n".join(currencies)
                msg += f"\n\nFutures Symbols: {len(futures_symbols)} pairs"
            else:
                msg = f"Connected successfully! (Testnet)\n\nNo balance found.\n\nFutures Symbols: {len(futures_symbols)} pairs"
            
            # Return data
            data = {
                'balance': total_balance,
                'symbols': futures_symbols
            }
            
            self.finished.emit(True, msg, data)
            
        except Exception as e:
            error_msg = str(e)
            if 'Invalid API' in error_msg or 'authentication' in error_msg.lower():
                msg = f"Authentication failed!\n\nInvalid API keys or insufficient permissions.\n\nError: {error_msg}"
            elif 'timeout' in error_msg.lower():
                msg = f"Connection timeout!\n\nPlease check your internet connection."
            else:
                msg = f"Connection failed!\n\n{error_msg}"
            
            self.finished.emit(False, msg, {})


class ExchangeApiController(QDialog):
    # Signal to notify main window
    connection_updated = pyqtSignal(str, bool, dict)  # exchange_name, is_connected, balance_info
    """Generic controller for all exchange API settings"""
    
    def __init__(self, exchange_name, ui_module_name, parent=None):
        """
        Args:
            exchange_name: Exchange name (binance, bybit, kucoin, mexc, okx)
            ui_module_name: UI module name (e.g., 'ui_binance_api_settings_dialog')
            parent: Parent widget
        """
        super().__init__(parent)
        self.exchange_name = exchange_name.lower()
        self.test_thread = None
        
        # Import UI class dynamically
        import importlib
        ui_module = importlib.import_module(f'ui.generated.{ui_module_name}')
        ui_class = ui_module.Ui_APISettingsDialog
        
        self.ui = ui_class()
        self.ui.setupUi(self)
        self.db = get_db()
        
        # Update title
        self.setWindowTitle(f"{exchange_name.title()} API Settings")
        
        # Connect buttons
        self.ui.btnSave.clicked.connect(self.save_keys)
        self.ui.btnCancel.clicked.connect(self.reject)
        if hasattr(self.ui, 'btnTestConnection'):
            self.ui.btnTestConnection.clicked.connect(self.test_connection)
        
        # Load existing keys
        self.load_keys()
    
    def load_keys(self):
        """Load existing API keys"""
        try:
            keys = self.db.load_api_keys(self.exchange_name, decrypt=True)
            if keys:
                self.ui.lineEditAPIKey.setText(keys['api_key'])
                self.ui.lineEditSecretKey.setText(keys['secret_key'])
                
                # Passphrase (for KuCoin)
                if hasattr(self.ui, 'lineEditPassphrase') and keys.get('passphrase'):
                    self.ui.lineEditPassphrase.setText(keys['passphrase'])
                
                logger.info(f"{self.exchange_name} keys loaded")
                
                # Check connection status from database
                result = self.db.fetch_one(
                    "SELECT is_connected FROM exchanges WHERE name = ?",
                    (self.exchange_name,)
                )
                
                if result and hasattr(self.ui, 'lblConnectionStatusText'):
                    if result['is_connected']:
                        self.ui.lblConnectionStatusText.setText("✅ Bağlantı başarılı (önceki test)")
                        self.ui.lblConnectionStatusText.setStyleSheet("color: #4CAF50;")
                    else:
                        self.ui.lblConnectionStatusText.setText("⚠️ Son test başarısız")
                        self.ui.lblConnectionStatusText.setStyleSheet("color: #FF9800;")
                
        except Exception as e:
            logger.error(f"Failed to load {self.exchange_name} keys: {e}")
    
    def save_keys(self):
        """Save API keys"""
        api_key = self.ui.lineEditAPIKey.text().strip()
        secret_key = self.ui.lineEditSecretKey.text().strip()
        passphrase = None
        
        # Get passphrase if exists (KuCoin)
        if hasattr(self.ui, 'lineEditPassphrase'):
            passphrase = self.ui.lineEditPassphrase.text().strip() or None
        
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
            success = self.db.save_api_keys(
                self.exchange_name,
                api_key,
                secret_key,
                passphrase,
                encrypted=False
            )
            
            if success:
                QMessageBox.information(
                    self,
                    "Success",
                    f"{self.exchange_name.title()} API keys saved!"
                )
                logger.info(f"{self.exchange_name} keys saved")
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Failed to save keys")
        except Exception as e:
            logger.error(f"Save error: {e}")
            QMessageBox.critical(self, "Error", str(e))
    
    def test_connection(self):
        """Test connection to exchange"""
        api_key = self.ui.lineEditAPIKey.text().strip()
        secret_key = self.ui.lineEditSecretKey.text().strip()
        passphrase = None
        
        if hasattr(self.ui, 'lineEditPassphrase'):
            passphrase = self.ui.lineEditPassphrase.text().strip() or None
        
        # Validate inputs first
        if not api_key or not secret_key:
            QMessageBox.warning(self, "Missing Keys", "Please enter API Key and Secret Key first")
            return
        
        # Disable button during test
        if hasattr(self.ui, 'btnTestConnection'):
            self.ui.btnTestConnection.setEnabled(False)
            self.ui.btnTestConnection.setText("Testing...")
        
        # Start connection test in background thread
        self.test_thread = ConnectionTestThread(
            self.exchange_name,
            api_key,
            secret_key,
            passphrase
        )
        self.test_thread.finished.connect(self.on_test_finished)
        self.test_thread.start()
        
        logger.info(f"Testing connection to {self.exchange_name}...")
    
    def on_test_finished(self, success, message, data):
        """Handle connection test result"""
        # Re-enable button
        if hasattr(self.ui, 'btnTestConnection'):
            self.ui.btnTestConnection.setEnabled(True)
            self.ui.btnTestConnection.setText("Test Connection")
        
        # Update status indicator
        if hasattr(self.ui, 'lblConnectionStatusText'):
            if success:
                self.ui.lblConnectionStatusText.setText("✅ Bağlantı başarılı")
                self.ui.lblConnectionStatusText.setStyleSheet("color: #4CAF50; font-weight: bold;")
            else:
                self.ui.lblConnectionStatusText.setText("❌ Bağlantı başarısız")
                self.ui.lblConnectionStatusText.setStyleSheet("color: #f44336; font-weight: bold;")
        
        # Update connection log
        if hasattr(self.ui, 'textEditConnectionLog'):
            self.ui.textEditConnectionLog.clear()
            self.ui.textEditConnectionLog.append(message)
        
        # Update database connection status
        if success:
            self.db.update_exchange_status(self.exchange_name, True)
            logger.info(f"{self.exchange_name} connection test successful")
            
            # Emit signal with data
            self.connection_updated.emit(self.exchange_name, True, data)
            
            QMessageBox.information(self, "Connection Success", message)
        else:
            self.db.update_exchange_status(self.exchange_name, False)
            logger.error(f"{self.exchange_name} connection test failed: {message}")
            self.connection_updated.emit(self.exchange_name, False, {})
            QMessageBox.critical(self, "Connection Failed", message)

    def _get_balance_info(self):
        """Get balance info from last test"""
        try:
            import ccxt
            exchange_class = getattr(ccxt, self.exchange_name)
            
            api_key = self.ui.lineEditAPIKey.text().strip()
            secret_key = self.ui.lineEditSecretKey.text().strip()
            passphrase = None
            
            if hasattr(self.ui, 'lineEditPassphrase'):
                passphrase = self.ui.lineEditPassphrase.text().strip() or None
            
            config = {
                'apiKey': api_key,
                'secret': secret_key,
                'enableRateLimit': True,
            }
            
            if passphrase:
                config['password'] = passphrase
            
            if self.exchange_name == 'binance':
                config['options'] = {'defaultType': 'future'}
            
            exchange = exchange_class(config)
            
            try:
                exchange.set_sandbox_mode(True)
            except:
                pass
            
            balance = exchange.fetch_balance()
            return balance.get('total', {})
        except:
            return {}


# Convenience functions for each exchange
def create_binance_controller(parent=None):
    return ExchangeApiController('binance', 'ui_binance_api_settings_dialog', parent)


def create_bybit_controller(parent=None):
    return ExchangeApiController('bybit', 'ui_bybit_api_settings_dialog', parent)


def create_kucoin_controller(parent=None):
    return ExchangeApiController('kucoin', 'ui_kucoin_api_settings_dialog', parent)


def create_mexc_controller(parent=None):
    return ExchangeApiController('mexc', 'ui_mexc_api_settings_dialog', parent)


def create_okx_controller(parent=None):
    return ExchangeApiController('okx', 'ui_okx_api_settings_dialog', parent)