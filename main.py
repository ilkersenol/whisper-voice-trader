"""
Whisper Voice Trader - Main Entry Point
"""
import sys
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QDialog
from PyQt5.QtCore import Qt
import assets.resources_rc
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
sys.path.insert(0, str(Path(__file__).parent))
from ui.generated.ui_main_window import Ui_MainWindow
from database.db_manager import get_db
from utils.logger import get_logger
from core.exchange_manager import get_exchange_manager
from core.order_executor import OrderExecutor, OrderParams, OrderResult
from database.db_manager import DatabaseManager
from utils.config_manager import ConfigManager
from core.exchange_manager import get_exchange_manager


logger = get_logger(__name__)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.db = get_db()
        self.exchange_manager = get_exchange_manager()  # Exchange Manager instance
        self.price_updater_thread = None  
        self.current_exchange = None  
        self.symbol_change_timer = None 
        logger.info("MainWindow initialized")
        self.apply_dark_theme()
        self.setWindowTitle("Whisper Voice Trader - v1.0.0")
        self.setup_table_headers()
        self.connect_menu_actions()
        self.connect_button_actions()
        # -------------------------------
        # ORDER EXECUTOR (Backend emir motoru)
        # -------------------------------
        self.db = DatabaseManager("database/sqlite.db")
        self.config = ConfigManager()
        self.exchange_manager = get_exchange_manager()
        self.order_executor = OrderExecutor(
            db_manager=self.db,
            config_manager=self.config,
            exchange_manager=self.exchange_manager,
            paper_trading_engine=None,  # Paper engine sonra bağlanacak
        )

        if hasattr(self.ui, 'comboSymbol'):
            self.ui.comboSymbol.currentIndexChanged.connect(self.on_symbol_changed)

        #self.load_connection_status()
    def on_exchange_connection_updated(self, exchange_name, is_connected, data):
        """Update main window when exchange connection changes"""
        try:
            # Store current exchange (EKLE)
            if is_connected:
                self.current_exchange = exchange_name
            
            # Update connection status
            if hasattr(self.ui, 'lblConnectionStatus'):
                if is_connected:
                    self.ui.lblConnectionStatus.setText(f"✅ {exchange_name.title()} Connected")
                    self.ui.lblConnectionStatus.setStyleSheet("color: #4CAF50; font-weight: bold;")
                else:
                    self.ui.lblConnectionStatus.setText(f"❌ {exchange_name.title()} Disconnected")
                    self.ui.lblConnectionStatus.setStyleSheet("color: #f44336; font-weight: bold;")
            
            # Update balance
            balance_info = data.get('balance', {})
            if hasattr(self.ui, 'lblBalance') and balance_info:
                usdt_balance = balance_info.get('USDT', 0.0)
                self.ui.lblBalance.setText(f"${usdt_balance:,.2f}")
                self.ui.lblBalance.setStyleSheet("color: #FFC107; font-size: 18px; font-weight: bold;")
            
            # Update symbols combobox
            symbols = data.get('symbols', [])
            if hasattr(self.ui, 'comboSymbol') and symbols:
                self.ui.comboSymbol.clear()
                self.ui.comboSymbol.addItems(symbols)
                logger.info(f"Loaded {len(symbols)} symbols for {exchange_name}")
                
                # Start price updater for first symbol (EKLE)
                if symbols:
                    self.start_price_updater(symbols[0])
            
            logger.info(f"Main window updated: {exchange_name} connection={is_connected}")
            
        except Exception as e:
            logger.error(f"Failed to update main window: {e}")

    def load_connection_status(self):
        """Load connection status on startup"""
        try:
            connected = self.db.get_connected_exchanges()
            
            if connected:
                exchange_name = connected[0]
                self.current_exchange = exchange_name
                
                if hasattr(self.ui, 'lblConnectionStatus'):
                    self.ui.lblConnectionStatus.setText(f"✅ {exchange_name.title()} Connected")
                    self.ui.lblConnectionStatus.setStyleSheet("color: #4CAF50; font-weight: bold;")
                
                try:
                    keys = self.db.load_api_keys(exchange_name, decrypt=True)
                    if keys:
                        import ccxt
                        exchange_class = getattr(ccxt, exchange_name)
                        
                        config = {
                            'apiKey': keys['api_key'],
                            'secret': keys['secret_key'],
                            'enableRateLimit': True,
                        }
                        
                        if exchange_name == 'binance':
                            config['options'] = {'defaultType': 'future'}
                        
                        exchange = exchange_class(config)
                        
                        try:
                            exchange.set_sandbox_mode(True)
                        except:
                            pass
                        
                        # Get balance
                        balance = exchange.fetch_balance()
                        usdt_balance = balance.get('total', {}).get('USDT', 0.0)
                        
                        if hasattr(self.ui, 'lblBalance'):
                            self.ui.lblBalance.setText(f"${usdt_balance:,.2f}")
                            self.ui.lblBalance.setStyleSheet("color: #FFC107; font-size: 18px; font-weight: bold;")
                        
                        # Get symbols
                        markets = exchange.load_markets()
                        futures_symbols = []
                        
                        for symbol, market in markets.items():
                            if market.get('type') in ['future', 'swap'] or market.get('future') or market.get('swap'):
                                if 'USDT' in symbol:
                                    clean_symbol = symbol.replace(':USDT', '')
                                    futures_symbols.append(clean_symbol)
                        
                        futures_symbols = sorted(list(set(futures_symbols)))
                        
                        if hasattr(self.ui, 'comboSymbol') and futures_symbols:
                            # BU SATIRI EKLE - Signal'i geçici olarak disconnect et
                            self.ui.comboSymbol.blockSignals(True)
                            
                            self.ui.comboSymbol.clear()
                            self.ui.comboSymbol.addItems(futures_symbols)
                            logger.info(f"Loaded {len(futures_symbols)} symbols on startup")
                            
                            # Signal'i tekrar aç
                            self.ui.comboSymbol.blockSignals(False)
                            
                            # ŞİMDİ thread başlat
                            if futures_symbols:
                                self.start_price_updater(futures_symbols[0])
                                
                except Exception as e:
                    logger.error(f"Failed to load exchange data: {e}")
            else:
                if hasattr(self.ui, 'lblConnectionStatus'):
                    self.ui.lblConnectionStatus.setText("⚠️ No Exchange Connected")
                    self.ui.lblConnectionStatus.setStyleSheet("color: #FF9800;")
                
                if hasattr(self.ui, 'lblBalance'):
                    self.ui.lblBalance.setText("$0.00")
        
        except Exception as e:
            logger.error(f"Failed to load connection status: {e}")
    def setup_table_headers(self):
        """Configure table headers to stretch across full width"""
        from PyQt5.QtWidgets import QHeaderView
        
        # ============================================
        # AÇIK POZİSYONLAR TABLOSU (9 sütun)
        # ============================================
        header_pos = self.ui.tablePositions.horizontalHeader()
        
        # Stretch sütunlar
        header_pos.setSectionResizeMode(0, QHeaderView.Stretch)  # Sembol
        header_pos.setSectionResizeMode(2, QHeaderView.Stretch)  # Miktar
        header_pos.setSectionResizeMode(3, QHeaderView.Stretch)  # Giriş Fiyatı
        header_pos.setSectionResizeMode(4, QHeaderView.Stretch)  # Mevcut Fiyat
        header_pos.setSectionResizeMode(5, QHeaderView.Stretch)  # Kâr/Zarar
        header_pos.setSectionResizeMode(7, QHeaderView.Stretch)  # Likitasyon
        header_pos.setSectionResizeMode(8, QHeaderView.Stretch)  # İşlemler
        
        # Sabit genişlik sütunlar (içeriğe göre)
        header_pos.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Yön
        header_pos.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Kâr/Zarar %
        
        # ============================================
        # AÇIK EMİRLER TABLOSU (8 sütun)
        # ============================================
        header_ord = self.ui.tableOrders.horizontalHeader()
        
        # Stretch sütunlar
        header_ord.setSectionResizeMode(0, QHeaderView.Stretch)  # Sembol
        header_ord.setSectionResizeMode(3, QHeaderView.Stretch)  # Fiyat
        header_ord.setSectionResizeMode(4, QHeaderView.Stretch)  # Miktar
        header_ord.setSectionResizeMode(5, QHeaderView.Stretch)  # Dolum
        header_ord.setSectionResizeMode(6, QHeaderView.Stretch)  # Zaman
        header_ord.setSectionResizeMode(7, QHeaderView.Stretch)  # İşlemler
        
        # Sabit genişlik sütunlar
        header_ord.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Tip
        header_ord.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Yön
        
        # ============================================
        # İŞLEM GEÇMİŞİ TABLOSU (8 sütun)
        # ============================================
        header_hist = self.ui.tableHistory.horizontalHeader()
        
        # Stretch sütunlar
        header_hist.setSectionResizeMode(0, QHeaderView.Stretch)  # Zaman
        header_hist.setSectionResizeMode(1, QHeaderView.Stretch)  # Sembol
        header_hist.setSectionResizeMode(3, QHeaderView.Stretch)  # Fiyat
        header_hist.setSectionResizeMode(4, QHeaderView.Stretch)  # Miktar
        header_hist.setSectionResizeMode(5, QHeaderView.Stretch)  # Komisyon
        header_hist.setSectionResizeMode(6, QHeaderView.Stretch)  # Kâr/Zarar
        
        # Sabit genişlik sütunlar
        header_hist.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Yön
        header_hist.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # Durum
        
    def apply_dark_theme(self):
        """Load and apply dark theme stylesheet"""
        theme_path = Path(__file__).parent / "ui" / "raw" / "dark_theme.qss"
        if theme_path.exists():
            with open(theme_path, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())
            logger.debug("Dark theme applied")


    def connect_menu_actions(self):
        """Connect menu actions to slots"""
        # File menu
        self.ui.actionAPISettings.triggered.connect(self.open_api_settings)
        self.ui.actionPreferences.triggered.connect(self.open_preferences)
        self.ui.actionExit.triggered.connect(self.close)
        
        # Help menu (if exists)
        if hasattr(self.ui, 'actionAbout'):
            self.ui.actionAbout.triggered.connect(self.show_about)

    def open_api_settings(self):
        """Open API Settings dialog with exchange selection"""
        try:
            from ui.controllers.exchange_selector import ExchangeSelectorDialog
            from ui.controllers.exchange_api_controller import (
                create_binance_controller,
                create_bybit_controller,
                create_kucoin_controller,
                create_mexc_controller,
                create_okx_controller
            )
            
            # Show exchange selector
            selector = ExchangeSelectorDialog(self)
            if selector.exec_() == QDialog.Accepted:
                exchange = selector.get_selected_exchange()
                
                # Open appropriate dialog
                dialog = None
                if exchange == 'binance':
                    dialog = create_binance_controller(self)
                elif exchange == 'bybit':
                    dialog = create_bybit_controller(self)
                elif exchange == 'kucoin':
                    dialog = create_kucoin_controller(self)
                elif exchange == 'mexc':
                    dialog = create_mexc_controller(self)
                elif exchange == 'okx':
                    dialog = create_okx_controller(self)
                else:
                    return
                
                # Connect signal to update main window
                dialog.connection_updated.connect(self.on_exchange_connection_updated)
                
                dialog.exec_()
        except Exception as e:
            logger.error(f"Failed to open API settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open API settings:\n{str(e)}")


    def on_symbol_changed(self, index):
        """Handle symbol selection change"""
        if index < 0:
            return
        
        symbol = self.ui.comboSymbol.currentText()
        if not symbol:
            return
        
        # Cancel pending timer
        if self.symbol_change_timer:
            self.symbol_change_timer.stop()
            self.symbol_change_timer = None
        
        # Use timer to debounce rapid changes (500ms delay)
        from PyQt5.QtCore import QTimer
        self.symbol_change_timer = QTimer()
        self.symbol_change_timer.setSingleShot(True)
        self.symbol_change_timer.timeout.connect(lambda: self._change_symbol(symbol))
        self.symbol_change_timer.start(500)

    def _change_symbol(self, symbol):
        """Actually change the symbol (called after debounce)"""
        logger.info(f"Symbol changed to: {symbol}")
        
        # Stop and cleanup previous updater
        if self.price_updater_thread:
            logger.info("Stopping previous price updater...")
            
            try:
                # Disconnect signals
                self.price_updater_thread.price_updated.disconnect(self.on_price_updated)
                self.price_updater_thread.error_occurred.disconnect(self.on_price_error)
            except:
                pass
            
            if self.price_updater_thread.isRunning():
                self.price_updater_thread.stop()
                
                # Wait longer and force terminate if needed
                if not self.price_updater_thread.wait(5000):  # 5 seconds
                    logger.warning("Thread did not stop, terminating...")
                    self.price_updater_thread.terminate()
                    self.price_updater_thread.wait(1000)
            
            self.price_updater_thread = None
            logger.info("Previous updater stopped")
        
        # Start new updater
        if self.current_exchange:
            self.start_price_updater(symbol)

    def start_price_updater(self, symbol):
        """Start real-time price updates for symbol"""
        try:
            # Clean up existing thread first
            if self.price_updater_thread:
                try:
                    self.price_updater_thread.price_updated.disconnect(self.on_price_updated)
                    self.price_updater_thread.error_occurred.disconnect(self.on_price_error)
                except:
                    pass
                
                if self.price_updater_thread.isRunning():
                    self.price_updater_thread.stop()
                    self.price_updater_thread.wait(2000)
                
                self.price_updater_thread = None
            
            # Get API keys
            keys = self.db.load_api_keys(self.current_exchange, decrypt=True)
            if not keys:
                logger.error("No API keys found for price updates")
                return
            
            # Create NEW thread
            from ui.controllers.price_updater import PriceUpdateThread
            
            self.price_updater_thread = PriceUpdateThread(
                self.current_exchange,
                symbol,
                keys['api_key'],
                keys['secret_key'],
                keys.get('passphrase')
            )
            
            # Connect signals
            self.price_updater_thread.price_updated.connect(self.on_price_updated)
            self.price_updater_thread.error_occurred.connect(self.on_price_error)
            
            # Start thread
            self.price_updater_thread.start()
            
            logger.info(f"Price updater started for {symbol}")
            
        except Exception as e:
            logger.error(f"Failed to start price updater: {e}")

    def on_price_updated(self, price_data):
        """Update UI with new prices"""
        try:
            # lblBestAsk'a BID değerini yaz (SOL - Yeşil)
            if hasattr(self.ui, 'lblBestAsk'):
                bid = price_data.get('best_bid')
                if bid is not None and bid > 0:
                    self.ui.lblBestAsk.setText(f"${bid:,.4f}")
                else:
                    self.ui.lblBestAsk.setText("N/A")
            
            # lblBestBid'e ASK değerini yaz (SAĞ - Kırmızı)
            if hasattr(self.ui, 'lblBestBid'):
                ask = price_data.get('best_ask')
                if ask is not None and ask > 0:
                    self.ui.lblBestBid.setText(f"${ask:,.4f}")
                else:
                    self.ui.lblBestBid.setText("N/A")
            
            # Update Current Price
            if hasattr(self.ui, 'lblCurrentPrice'):
                current = price_data.get('current_price')
                if current is not None and current > 0:
                    self.ui.lblCurrentPrice.setText(f"${current:,.4f}")
                    
                    change = price_data.get('change_24h', 0)
                    if change and change > 0:
                        color = "#4CAF50"
                    elif change and change < 0:
                        color = "#f44336"
                    else:
                        color = "#FFC107"
                    
                    self.ui.lblCurrentPrice.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: bold;")
                else:
                    self.ui.lblCurrentPrice.setText("N/A")
            
        except Exception as e:
            logger.error(f"Failed to update prices: {e}")

    def on_price_error(self, error_msg):
        """Handle price update errors"""
        logger.error(f"Price update error: {error_msg}")

    def closeEvent(self, event):
        """Handle window close event"""
        logger.info("Application closing...")
        
        # Stop price updater
        if self.price_updater_thread:
            logger.info("Stopping price updater thread...")
            
            try:
                # Disconnect signals
                self.price_updater_thread.price_updated.disconnect()
                self.price_updater_thread.error_occurred.disconnect()
            except:
                pass
            
            if self.price_updater_thread.isRunning():
                self.price_updater_thread.stop()
                if not self.price_updater_thread.wait(3000):  # Wait 3 seconds
                    logger.warning("Price updater thread did not stop gracefully")
                    self.price_updater_thread.terminate()  # Force terminate
                    self.price_updater_thread.wait(1000)
            
            self.price_updater_thread = None
            logger.info("Price updater stopped")
        
        event.accept()

    def open_preferences(self):
        """Open Preferences dialog"""
        try:
            from ui.controllers.preferences_controller import PreferencesController
            dialog = PreferencesController(self)
            dialog.exec_()
        except Exception as e:
            logger.error(f"Failed to open preferences: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open preferences:\n{str(e)}")

    def open_emergency(self):
        """Open Emergency Stop dialog"""
        try:
            from PyQt5.QtWidgets import QDialog
            from ui.generated.ui_emergency_dialog import Ui_EmergencyDialog
            
            # Create dialog
            dialog = QDialog(self)
            ui = Ui_EmergencyDialog()
            ui.setupUi(dialog)
            
            # Show and wait for response
            result = dialog.exec_()
            
            if result == QDialog.Accepted:
                # User confirmed
                logger.warning("Emergency protocol activated")
                self.execute_emergency_protocol()
            else:
                logger.info("Emergency protocol cancelled")
                
        except Exception as e:
            logger.error(f"Failed to open emergency dialog: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open emergency dialog:\n{str(e)}")

    def execute_emergency_protocol(self):
        """Execute emergency shutdown protocol"""
        try:
            logger.warning("="*50)
            logger.warning("EMERGENCY PROTOCOL EXECUTING")
            logger.warning("="*50)
            
            # 1. Stop price updater
            if self.price_updater_thread and self.price_updater_thread.isRunning():
                logger.warning("Stopping price updater...")
                self.price_updater_thread.stop()
                self.price_updater_thread.wait(2000)
            
            # 2. Close all positions (database update)
            try:
                result = self.db.execute("UPDATE positions SET status = 'closed' WHERE status = 'open'")
                logger.warning(f"Closed all open positions")
            except Exception as e:
                logger.error(f"Failed to close positions: {e}")
            
            # 3. Cancel all orders (database update)
            try:
                result = self.db.execute("UPDATE orders SET status = 'cancelled' WHERE status = 'pending'")
                logger.warning(f"Cancelled all pending orders")
            except Exception as e:
                logger.error(f"Failed to cancel orders: {e}")
            
            # 4. Disconnect exchange
            if self.current_exchange:
                logger.warning(f"Disconnecting from {self.current_exchange}...")
                self.disconnect_exchange()
            
            logger.warning("="*50)
            logger.warning("EMERGENCY PROTOCOL COMPLETED")
            logger.warning("="*50)
            
            QMessageBox.information(
                self,
                "Emergency Protocol Complete",
                "All positions closed\n"
                "All orders cancelled\n"
                "Bot stopped\n"
                "Exchange disconnected"
            )
            
        except Exception as e:
            logger.error(f"Emergency protocol error: {e}")
            QMessageBox.critical(self, "Error", f"Emergency protocol failed:\n{str(e)}")

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About Whisper Voice Trader",
            "<h3>Whisper Voice Trader v1.0.0</h3>"
            "<p>Voice-controlled cryptocurrency trading bot</p>"
            "<p><b>Developer:</b> Creagent</p>"
            "<p><b>License:</b> Commercial</p>"
        )

    def connect_button_actions(self):
        """Connect button actions to slots"""
        # Emergency button
        if hasattr(self.ui, 'btnEmergency'):  # btnEmergencyStop -> btnEmergency
            self.ui.btnEmergency.clicked.connect(self.open_emergency)
        
        # Connect button (EKLE)
        if hasattr(self.ui, 'btnConnect'):
            self.ui.btnConnect.clicked.connect(self.on_connect_clicked)

            # Disconnect button (EKLE)
        if hasattr(self.ui, 'btnDisconnect'):
            self.ui.btnDisconnect.clicked.connect(self.on_disconnect_clicked)
                # Buy / Sell butonları
        if hasattr(self.ui, 'btnBuy'):
            self.ui.btnBuy.clicked.connect(lambda: self.on_order_button_clicked("buy"))
        if hasattr(self.ui, 'btnSell'):
            self.ui.btnSell.clicked.connect(lambda: self.on_order_button_clicked("sell"))

        # Paper trading checkbox
        if hasattr(self.ui, 'chkPaperTrading'):
            self.ui.chkPaperTrading.stateChanged.connect(self.on_paper_trading_changed)

        # Leverage slider
        if hasattr(self.ui, 'sliderLeverage'):
            self.ui.sliderLeverage.valueChanged.connect(self.on_leverage_changed)



    def on_connect_clicked(self):
        """Handle connect button click"""
        try:
            # Get selected exchange from combobox
            if not hasattr(self.ui, 'comboExchange'):
                QMessageBox.warning(self, "Error", "Exchange selector not found")
                return
            
            exchange_text = self.ui.comboExchange.currentText()
            if not exchange_text:
                QMessageBox.warning(self, "No Selection", "Please select an exchange first")
                return
            
            # Convert to lowercase
            exchange_name = exchange_text.lower()
            
            logger.info(f"Connect button clicked for: {exchange_name}")
            
            # Check if API keys exist in database
            keys = self.db.load_api_keys(exchange_name, decrypt=True)
            
            if keys:
                # Keys found - Connect
                logger.info(f"Keys found for {exchange_name}, connecting...")
                self.connect_to_exchange(exchange_name, keys)
            else:
                # No keys - Open API Settings dialog
                logger.info(f"No keys found for {exchange_name}, opening settings...")
                self.open_exchange_settings(exchange_name)
                
        except Exception as e:
            logger.error(f"Connect button error: {e}")
            QMessageBox.critical(self, "Error", f"Failed to connect:\n{str(e)}")

    def on_leverage_changed(self, value: int):
        """Kaldıraç slider değişince label günceller."""
        try:
            if hasattr(self.ui, 'lblLeverageValue'):
                self.ui.lblLeverageValue.setText(f"x{value}")
        except Exception as e:
            logger.error(f"Failed to update leverage label: {e}")


    def connect_to_exchange(self, exchange_name, keys):
        """Connect to exchange with existing keys - Using ExchangeManager"""
        try:
            # Show progress
            from PyQt5.QtWidgets import QProgressDialog
            progress = QProgressDialog("Connecting to exchange...", None, 0, 0, self)
            progress.setWindowTitle("Connecting")
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            QApplication.processEvents()
            
            # Connect using ExchangeManager
            success = self.exchange_manager.connect_exchange(
                exchange_name=exchange_name,
                api_key=keys['api_key'],
                secret_key=keys['secret_key'],
                testnet=True,
                passphrase=keys.get('passphrase')
            )
            
            if not success:
                progress.close()
                QMessageBox.critical(
                    self,
                    "Connection Failed",
                    f"Failed to connect to {exchange_name.title()}.\n\n"
                    "Please check your API keys and try again."
                )
                return
            
            # Get balance
            balance = self.exchange_manager.get_balance(exchange_name)
            usdt_balance = balance.get('total', 0.0)
            
            # Get symbols
            futures_symbols = self.exchange_manager.get_markets(exchange_name)
            
            progress.close()
            
            # Update UI
            self.current_exchange = exchange_name
            
            if hasattr(self.ui, 'lblConnectionStatus'):
                self.ui.lblConnectionStatus.setText(f"✅ {exchange_name.title()} Connected")
                self.ui.lblConnectionStatus.setStyleSheet("color: #4CAF50; font-weight: bold;")
            
            if hasattr(self.ui, 'lblBalance'):
                self.ui.lblBalance.setText(f"${usdt_balance:,.2f}")
                self.ui.lblBalance.setStyleSheet("color: #FFC107; font-size: 18px; font-weight: bold;")
            
            if hasattr(self.ui, 'comboSymbol') and futures_symbols:
                self.ui.comboSymbol.blockSignals(True)
                self.ui.comboSymbol.clear()
                self.ui.comboSymbol.addItems(futures_symbols)
                self.ui.comboSymbol.blockSignals(False)
                
                if futures_symbols:
                    self.start_price_updater(futures_symbols[0])
            
            QMessageBox.information(
                self,
                "Connected",
                f"Successfully connected to {exchange_name.title()}!\n\n"
                f"Balance: ${usdt_balance:,.2f} USDT\n"
                f"Symbols: {len(futures_symbols)} pairs"
            )
            
            logger.info(f"Successfully connected to {exchange_name}")
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            logger.error(f"Connection failed: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Connection Failed",
                f"Failed to connect to {exchange_name.title()}:\n\n{str(e)}"
            )


    def on_disconnect_clicked(self):
        """Handle disconnect button click"""
        try:
            # Check if connected
            if not self.current_exchange:
                QMessageBox.information(self, "Not Connected", "No active connection to disconnect")
                return
            
            # Confirm disconnect
            reply = QMessageBox.question(
                self,
                'Disconnect',
                f'Disconnect from {self.current_exchange.title()}?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.disconnect_exchange()
                
        except Exception as e:
            logger.error(f"Disconnect error: {e}")
            QMessageBox.critical(self, "Error", f"Failed to disconnect:\n{str(e)}")


    def on_paper_trading_changed(self, state: int):
        """Paper trading checkbox değişince ikonları günceller (şimdilik sadece UI)."""
        try:
            enabled = (state == Qt.Checked)
            self.order_executor.set_paper_trading(enabled)
            # İkonlar varsa görünürlüklerini ayarla
            if hasattr(self.ui, 'lblPaperIcon'):
                self.ui.lblPaperIcon.setVisible(enabled)
            if hasattr(self.ui, 'lblRealIcon'):
                self.ui.lblRealIcon.setVisible(not enabled)

            mode = "PAPER" if enabled else "REAL"
            logger.info(f"Trading mode changed (UI): {mode}")

            # İLERİDE: burada OrderExecutor.set_paper_trading(...) çağrılacak
        except Exception as e:
            logger.error(f"Failed to handle paper trading toggle: {e}")


    def on_order_button_clicked(self, side: str):

        
        """
        BUY / SELL tıklandığında UI'dan emir parametrelerini toplar.
        ŞİMDİLİK sadece log + bilgi popup gösterir.
        Backend (OrderExecutor) ile bağlantıyı daha sonra ekleyeceğiz.
        """
        try:
            symbol = None
            if hasattr(self.ui, 'comboSymbol'):
                symbol = self.ui.comboSymbol.currentText()

            active_tab = 1
            if hasattr(self.ui, 'tabOrderTypes'):
                active_tab = self.ui.tabOrderTypes.currentIndex()  # 0: Limit, 1: Market, 2: Stop

            leverage = None
            if hasattr(self.ui, 'sliderLeverage'):
                leverage = self.ui.sliderLeverage.value()

            order_type = "market"
            price = None
            amount = None

            # Limit tabı
            if active_tab == 0:
                order_type = "limit"
                if hasattr(self.ui, 'spinLimitPrice'):
                    price = float(self.ui.spinLimitPrice.value())
                if hasattr(self.ui, 'spinLimitAmount'):
                    amount = float(self.ui.spinLimitAmount.value())

            # Market tabı
            elif active_tab == 1:
                order_type = "market"
                if hasattr(self.ui, 'spinMarketAmount'):
                    amount = float(self.ui.spinMarketAmount.value())

            # Stop tabı
            elif active_tab == 2:
                QMessageBox.warning(self, "Henüz desteklenmiyor",
                                    "Stop emir akışı backend tarafında henüz hazır değil.")
                return

                if hasattr(self.ui, 'spinStopPrice'):
                    price = float(self.ui.spinStopPrice.value())
                if hasattr(self.ui, 'spinStopAmount'):
                    amount = float(self.ui.spinStopAmount.value())

            logger.info(
                "UI order click: side=%s type=%s symbol=%s amount=%s price=%s lev=%s",
                side, order_type, symbol, amount, price, leverage,
            )

            QMessageBox.information(
                self,
                "Emir (UI tarafı hazır)",
                f"UI'dan emir isteği alındı.\n\n"
                f"Yön: {side}\n"
                f"Tip: {order_type}\n"
                f"Sembol: {symbol}\n"
                f"Miktar: {amount}\n"
                f"Fiyat: {price}\n"
                f"Kaldıraç: {leverage}\n\n"
                f"(Bu aşamada backend'e henüz bağlamadık.)"
            )

        except Exception as e:
            logger.error("on_order_button_clicked failed: %s", e, exc_info=True)
            QMessageBox.critical(self, "Hata", f"Emir UI işleyicisinde hata:\n{e}")



    def disconnect_exchange(self):
        """Disconnect from current exchange - Using ExchangeManager"""
        try:
            exchange_name = self.current_exchange
            
            logger.info(f"Disconnecting from {exchange_name}...")
            
            # 1. Stop price updater thread
            if self.price_updater_thread:
                logger.info("Stopping price updater thread...")
                
                try:
                    self.price_updater_thread.price_updated.disconnect(self.on_price_updated)
                    self.price_updater_thread.error_occurred.disconnect(self.on_price_error)
                except:
                    pass
                
                if self.price_updater_thread.isRunning():
                    self.price_updater_thread.stop()
                    if not self.price_updater_thread.wait(3000):
                        logger.warning("Thread did not stop, terminating...")
                        self.price_updater_thread.terminate()
                        self.price_updater_thread.wait(1000)
                
                self.price_updater_thread = None
                logger.info("Price updater stopped")
            
            # 2. Disconnect using ExchangeManager
            if exchange_name:
                self.exchange_manager.disconnect_exchange(exchange_name)
            
            # 3. Clear current exchange
            self.current_exchange = None
            
            # 4. Reset UI - Connection Status
            if hasattr(self.ui, 'lblConnectionStatus'):
                self.ui.lblConnectionStatus.setText("⚠️ Bağlantı Kesildi")
                self.ui.lblConnectionStatus.setStyleSheet("color: #FF9800; font-weight: bold;")
            
            # 5. Reset UI - Balance
            if hasattr(self.ui, 'lblBalance'):
                self.ui.lblBalance.setText("$0.00")
                self.ui.lblBalance.setStyleSheet("color: #9E9E9E; font-size: 18px;")
            
            # 6. Clear symbols
            if hasattr(self.ui, 'comboSymbol'):
                self.ui.comboSymbol.blockSignals(True)
                self.ui.comboSymbol.clear()
                self.ui.comboSymbol.blockSignals(False)
            
            # 7. Reset price labels
            if hasattr(self.ui, 'lblBestAsk'):
                self.ui.lblBestAsk.setText("Veri Yok")
                self.ui.lblBestAsk.setStyleSheet("")
            
            if hasattr(self.ui, 'lblBestBid'):
                self.ui.lblBestBid.setText("Veri Yok")
                self.ui.lblBestBid.setStyleSheet("")
            
            if hasattr(self.ui, 'lblCurrentPrice'):
                self.ui.lblCurrentPrice.setText("Veri Yok")
                self.ui.lblCurrentPrice.setStyleSheet("color: #9E9E9E; font-size: 20px;")
            
            logger.info(f"{exchange_name} bağlantısı kesildi")
            
            QMessageBox.information(
                self,
                "Bağlantı kesildi",
                f" {exchange_name.title()} bağlantısı sonlandırıldı"
            )
            
        except Exception as e:
            logger.error(f"Disconnect failed: {e}")
            raise

    def open_exchange_settings(self, exchange_name):
        """Open API settings dialog for exchange"""
        try:
            from ui.controllers.exchange_api_controller import (
                create_binance_controller,
                create_bybit_controller,
                create_kucoin_controller,
                create_mexc_controller,
                create_okx_controller
            )
            
            # Create appropriate dialog
            if exchange_name == 'binance':
                dialog = create_binance_controller(self)
            elif exchange_name == 'bybit':
                dialog = create_bybit_controller(self)
            elif exchange_name == 'kucoin':
                dialog = create_kucoin_controller(self)
            elif exchange_name == 'mexc':
                dialog = create_mexc_controller(self)
            elif exchange_name == 'okx':
                dialog = create_okx_controller(self)
            else:
                QMessageBox.warning(self, "Error", f"Unsupported exchange: {exchange_name}")
                return
            
            # Connect signal
            dialog.connection_updated.connect(self.on_exchange_connection_updated)
            
            # Show dialog
            dialog.exec_()
            
        except Exception as e:
            logger.error(f"Failed to open settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open settings:\n{str(e)}")


def main():
    """Application entry point"""
    logger.info("="*50)
    logger.info("Whisper Voice Trader Starting...")
    logger.info("="*50)
    
    # Initialize database
    try:
        db = get_db()
        db.initialize()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return 1
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Whisper Voice Trader")
    app.setOrganizationName("Creagent")
    
    # Create main window
    window = MainWindow()
    
    # Show window FIRST
    window.showMaximized()
    
    logger.info("Application started successfully (Maximized)")
    
    # Load connection status AFTER window is shown (async)
    from PyQt5.QtCore import QTimer
  # QTimer.singleShot(100, window.load_connection_status)
    
    # Start event loop
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())