"""
Whisper Voice Trader - Main Entry Point
"""
import sys
from pathlib import Path

# =======================================================
# KRITIK: Whisper modelini QApplication'dan ÖNCE yükle
# Bu, CUDA + PyQt5 çakışmasını önler
# =======================================================
print("[STARTUP] Whisper modeli yükleniyor...")
try:
    from core.whisper_engine import preload_whisper_model
    _whisper_loaded = preload_whisper_model("tiny")
    if _whisper_loaded:
        print("[STARTUP] Whisper modeli hazır!")
    else:
        print("[STARTUP] Whisper modeli yüklenemedi, sesli komutlar çalışmayacak.")
except Exception as e:
    print(f"[STARTUP] Whisper yükleme hatası: {e}")
    _whisper_loaded = False
# =======================================================

from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QDialog
from PyQt5.QtCore import Qt
import assets.resources_rc


# High DPI Support - MUST BE BEFORE QApplication
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from ui.generated.ui_main_window import Ui_MainWindow
from database.db_manager import get_db
from utils.logger import get_logger
from core.exchange_manager import get_exchange_manager
from core.order_executor import OrderExecutor, OrderParams, OrderResult
from utils.config_manager import ConfigManager
from ui.generated.ui_command_keywords_dialog import Ui_CommandKeywordsDialog  
from core.whisper_engine import WhisperEngine, WhisperSettings
from core.voice_listener import VoiceListener, ListenerSettings
from core.tts_engine import TTSEngine, get_tts_engine
from core.command_parser import CommandParser, CommandValidator




logger = get_logger(__name__)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.db = get_db()
        self.exchange_manager = get_exchange_manager()  # Exchange Manager instance
        self.config = ConfigManager()
        self.order_executor = OrderExecutor(
        db_manager=self.db,
        config_manager=self.config,
        exchange_manager=self.exchange_manager,
        paper_trading_engine=None,
    )

        self.price_updater_thread = None  
        self.current_exchange = None  
        self.symbol_change_timer = None 
        self.ensure_voice_commands_table()
        self.load_voice_commands()
        self.voice_commands = []
        logger.info("MainWindow initialized")
        self.apply_dark_theme()
        self.setWindowTitle("Whisper Voice Trader - v1.0.0")
        self.setup_table_headers()
        self.connect_menu_actions()
        self.connect_button_actions()

        # Sesli komutlar için Whisper motoru ve dinleyici
        # Model boyutunu ayarlardan oku
        model_size = self.config.get('whisper.model_size', 'tiny')
        use_gpu = self.config.get('whisper.use_gpu', True)
        language = self.config.get('app.language', 'tr')
        
        voice_settings = WhisperSettings(
            model_size=model_size,
            use_gpu=use_gpu,
            language=language,
        )
        self.whisper_engine = WhisperEngine(voice_settings)
        self.voice_listener: VoiceListener = None
        self._whisper_ready = _whisper_loaded  # Global değişkenden al
        
        # TTS Engine başlat
        tts_enabled = self.config.get('tts.enabled', True)
        tts_speed = self.config.get('tts.speed', 100)
        # TTS rate: speed% -> gerçek rate (100 = 150, yani varsayılan)
        # 50% = 75, 100% = 150, 200% = 300
        tts_rate = int(150 * tts_speed / 100)
        self.tts_engine = get_tts_engine(
            enabled=tts_enabled,
            language=language,
            rate=tts_rate,
        )
        
        # Onay bekleme süresi (command handler'da kullanılacak)
        self.confirmation_timeout = self.config.get('tts.confirmation_timeout', 10)
        
        # Command Parser başlat
        self.command_parser = CommandParser(default_symbol="BTCUSDT")

        if hasattr(self.ui, 'comboSymbol'):
            self.ui.comboSymbol.currentIndexChanged.connect(self.on_symbol_changed)

    def ensure_voice_commands_table(self):
        """Sesli komut eşleşmeleri için tabloyu oluşturur (yoksa)."""
        try:
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS voice_commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    phrase   TEXT NOT NULL,
                    language TEXT DEFAULT 'tr',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            logger.info("voice_commands table ensured")
        except Exception as e:
            logger.error(f"Failed to ensure voice_commands table: {e}")
    @staticmethod
    def normalize_text(text: str) -> str:
        """Karşılaştırma için metni normalize eder (küçük harf, TR karakter düzeltme, noktalama temizleme)."""
        if not text:
            return ""
        text = text.strip().lower()

        # Noktalama işaretlerini temizle
        import re
        text = re.sub(r'[.,!?;:\'"()]+', '', text)

        # Türkçe karakter basitleştirme
        replacements = {
            "ı": "i",
            "ğ": "g",
            "ü": "u",
            "ş": "s",
            "ö": "o",
            "ç": "c",
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)

        return text.strip()
    
    def load_voice_commands(self):
        """Aktif sesli komutları DB'den okuyup RAM'e cache eder."""
        try:
            rows = self.db.execute(
                "SELECT category, phrase, language "
                "FROM voice_commands WHERE is_active = 1"
            ).fetchall()

            self.voice_commands = []
            for row in rows:
                category = row[0]
                phrase = row[1]
                language = row[2] if len(row) > 2 else "tr"

                if not phrase:
                    continue

                self.voice_commands.append(
                    {
                        "category": category,
                        "phrase": phrase,
                        "language": language or "tr",
                        "norm_phrase": self.normalize_text(phrase),
                    }
                )

            logger.info(f"Loaded {len(self.voice_commands)} voice commands")

        except Exception as e:
            logger.error(f"Failed to load voice commands: {e}")
            self.voice_commands = []

    def match_voice_command(self, transcript: str):
        """
        Whisper'dan gelen transcript içinde tanımlı komutlardan biri geçiyorsa
        category + orijinal phrase'i döndürür, yoksa (None, None).
        """
        if not transcript:
            return None, None

        if not self.voice_commands:
            return None, None

        norm_text = self.normalize_text(transcript)

        for cmd in self.voice_commands:
            key = cmd.get("norm_phrase")
            if not key:
                continue

            if key in norm_text:
                # İlk eşleşen komutu döndürüyoruz
                return cmd.get("category"), cmd.get("phrase")

        return None, None



    def on_exchange_connection_updated(self, exchange_name, is_connected, data):
        """Update main window when exchange connection changes"""
        try:
            # Current exchange durumunu güncelle
            if is_connected:
                self.current_exchange = exchange_name

            # Connection status label
            if hasattr(self.ui, 'lblConnectionStatus'):
                if is_connected:
                    self.ui.lblConnectionStatus.setText(f"✅ {exchange_name.title()} Connected")
                    self.ui.lblConnectionStatus.setStyleSheet("color: #4CAF50; font-weight: bold;")
                else:
                    self.ui.lblConnectionStatus.setText(f"❌ {exchange_name.title()} Disconnected")
                    self.ui.lblConnectionStatus.setStyleSheet("color: #f44336; font-weight: bold;")

            # Balance label
            balance_info = data.get('balance', {})
            if hasattr(self.ui, 'lblBalance') and balance_info:
                usdt_balance = balance_info.get('USDT', 0.0)
                self.ui.lblBalance.setText(f"${usdt_balance:,.2f}")
                self.ui.lblBalance.setStyleSheet("color: #FFC107; font-size: 18px; font-weight: bold;")

            # Symbol list
            symbols = data.get('symbols', [])
            if hasattr(self.ui, 'comboSymbol') and symbols:
                self.ui.comboSymbol.clear()
                self.ui.comboSymbol.addItems(symbols)
                logger.info(f"Loaded {len(symbols)} symbols for {exchange_name}")
                if symbols:
                    self.start_price_updater(symbols[0])

            # Connect / Disconnect buton durumları
            if hasattr(self.ui, 'btnConnect'):
                self.ui.btnConnect.setEnabled(not is_connected)
            if hasattr(self.ui, 'btnDisconnect'):
                self.ui.btnDisconnect.setEnabled(is_connected)

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
                        balance = exchange.fetch_balance()
                        usdt_balance = balance.get('total', {}).get('USDT', 0.0)
                        if hasattr(self.ui, 'lblBalance'):
                            self.ui.lblBalance.setText(f"${usdt_balance:,.2f}")
                            self.ui.lblBalance.setStyleSheet("color: #FFC107; font-size: 18px; font-weight: bold;")
                        markets = exchange.load_markets()
                        futures_symbols = []
                        for symbol, market in markets.items():
                            if market.get('type') in ['future', 'swap'] or market.get('future') or market.get('swap'):
                                if 'USDT' in symbol:
                                    clean_symbol = symbol.replace(':USDT', '')
                                    futures_symbols.append(clean_symbol)
                        futures_symbols = sorted(list(set(futures_symbols)))
                        if hasattr(self.ui, 'comboSymbol') and futures_symbols:
                            self.ui.comboSymbol.blockSignals(True)
                            self.ui.comboSymbol.clear()
                            self.ui.comboSymbol.addItems(futures_symbols)
                            logger.info(f"Loaded {len(futures_symbols)} symbols on startup")
                            self.ui.comboSymbol.blockSignals(False)
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
        header_pos = self.ui.tablePositions.horizontalHeader()
        header_pos.setSectionResizeMode(0, QHeaderView.Stretch)  # Sembol
        header_pos.setSectionResizeMode(2, QHeaderView.Stretch)  # Miktar
        header_pos.setSectionResizeMode(3, QHeaderView.Stretch)  # Giriş Fiyatı
        header_pos.setSectionResizeMode(4, QHeaderView.Stretch)  # Mevcut Fiyat
        header_pos.setSectionResizeMode(5, QHeaderView.Stretch)  # Kâr/Zarar
        header_pos.setSectionResizeMode(7, QHeaderView.Stretch)  # Likitasyon
        header_pos.setSectionResizeMode(8, QHeaderView.Stretch)  # İşlemler
        header_pos.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Yön
        header_pos.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Kâr/Zarar %
        header_ord = self.ui.tableOrders.horizontalHeader()
        header_ord.setSectionResizeMode(0, QHeaderView.Stretch)  # Sembol
        header_ord.setSectionResizeMode(3, QHeaderView.Stretch)  # Fiyat
        header_ord.setSectionResizeMode(4, QHeaderView.Stretch)  # Miktar
        header_ord.setSectionResizeMode(5, QHeaderView.Stretch)  # Dolum
        header_ord.setSectionResizeMode(6, QHeaderView.Stretch)  # Zaman
        header_ord.setSectionResizeMode(7, QHeaderView.Stretch)  # İşlemler
        header_ord.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Tip
        header_ord.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Yön
        header_hist = self.ui.tableHistory.horizontalHeader()
        header_hist.setSectionResizeMode(0, QHeaderView.Stretch)  # Zaman
        header_hist.setSectionResizeMode(1, QHeaderView.Stretch)  # Sembol
        header_hist.setSectionResizeMode(3, QHeaderView.Stretch)  # Fiyat
        header_hist.setSectionResizeMode(4, QHeaderView.Stretch)  # Miktar
        header_hist.setSectionResizeMode(5, QHeaderView.Stretch)  # Komisyon
        header_hist.setSectionResizeMode(6, QHeaderView.Stretch)  # Kâr/Zarar
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

        def format_price(value):
            if value is None or value <= 0:
                return "N/A"
            # Küçük fiyatlar için daha fazla hane
            if value < 0.01:
                return f"${value:,.6f}"
            elif value < 1:
                return f"${value:,.5f}"
            elif value < 100:
                return f"${value:,.4f}"
            else:
                return f"${value:,.2f}"

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

                        # --- 24H STATS LABELS ---

            # 24H Change %
            if hasattr(self.ui, 'lbl24hChange'):
                change = price_data.get('change_24h', 0.0)
                if change is not None:
                    self.ui.lbl24hChange.setText(f"{change:+.2f}%")
                else:
                    self.ui.lbl24hChange.setText("-")

            # 24H Volume (USDT)
            if hasattr(self.ui, 'lbl24hVolume'):
                vol = price_data.get('volume', 0.0)
                if vol is not None and vol > 0:
                    self.ui.lbl24hVolume.setText(f"{vol:,.0f} USDT")
                else:
                    self.ui.lbl24hVolume.setText("-")

            # 24H HIGH (USDT)
            if hasattr(self.ui, 'lbl24hHigh'):
                high = price_data.get('high_24h', 0.0)
                if high is not None and high > 0:
                    self.ui.lbl24hHigh.setText(f"{high:,.4f} USDT")
                else:
                    self.ui.lbl24hHigh.setText("-")

            # 24H LOW (USDT)
            if hasattr(self.ui, 'lbl24hLow'):
                low = price_data.get('low_24h', 0.0)
                if low is not None and low > 0:
                    self.ui.lbl24hLow.setText(f"{low:,.4f} USDT")
                else:
                    self.ui.lbl24hLow.setText("-")

            
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


    def open_command_keywords_dialog(self):
        """'Komut Ekle' penceresini açar ve girilen komutu DB'ye kaydeder."""
        try:
            dialog = QDialog(self)
            ui = Ui_CommandKeywordsDialog()
            ui.setupUi(dialog)

            # Varsayılanlar
            ui.cmbCategory.setCurrentIndex(0)
            ui.lineWord.clear()

            result = dialog.exec_()
            if result != QDialog.Accepted:
                logger.info("Command dialog cancelled")
                return

            category_text = ui.cmbCategory.currentText()
            phrase = ui.lineWord.text().strip()

            if not phrase:
                QMessageBox.warning(self, "Geçersiz komut", "Lütfen bir kelime veya cümle girin.")
                return

            # UI'daki görünen metni internal kategori koduna çevir
            category_map = {
                "Al (BUY)": "BUY",
                "Sat (SELL)": "SELL",
                "Ters Çevir (REVERSE)": "REVERSE",
                "Yok say (STOP)": "STOP",
            }
            category = category_map.get(category_text, "OTHER")

            language = "tr"  # Şimdilik sabit; ileride comboLanguage ile ilişkilendirilebilir

            # SQL string içinde tek tırnak sorun çıkarmasın diye kaçır
            safe_phrase = phrase.replace("'", "''")
            safe_category = category.replace("'", "''")
            safe_language = language.replace("'", "''")

            sql = (
                "INSERT INTO voice_commands (category, phrase, language, is_active) "
                f"VALUES ('{safe_category}', '{safe_phrase}', '{safe_language}', 1)"
            )

            try:
                self.db.execute(sql)
                logger.info(f"Voice command added: [{category}] {phrase}")
                QMessageBox.information(self, "Komut kaydedildi", f"\"{phrase}\" komutu kaydedildi.")
                self.load_voice_commands()
            except Exception as e:
                logger.error(f"Failed to save voice command: {e}")
                QMessageBox.critical(self, "Hata", f"Komut kaydedilemedi:\n{e}")

        except Exception as e:
            logger.error(f"Failed to open command dialog: {e}")
            QMessageBox.critical(self, "Hata", f"Komut penceresi açılamadı:\n{e}")

    def on_voice_order_clicked(self):
        """Kısa süreli ses kaydı başlatır ve sonucu Whisper ile çözer."""
        try:
            # Whisper hazır mı kontrol et
            if not self._whisper_ready:
                QMessageBox.warning(
                    self,
                    "Whisper Hazır Değil",
                    "Sesli komut motoru henüz yüklenmedi.\n"
                    "Lütfen birkaç saniye bekleyin veya uygulamayı yeniden başlatın."
                )
                return
            
            # Zaten bir dinleyici çalışıyorsa tekrar başlatma
            if hasattr(self, "voice_listener") and self.voice_listener is not None:
                if self.voice_listener.isRunning():
                    QMessageBox.information(
                        self,
                        "Sesli Emir",
                        "Zaten dinleniyor. Lütfen mevcut işlemin bitmesini bekleyin.",
                    )
                    return

            # Yeni dinleyici oluştur (Wake Word destekli)
            # Tüm ayarları config'den oku
            wake_word = self.config.get('whisper.wake_word', 'Whisper')
            active_duration = self.config.get('whisper.active_mode_duration', 15)
            mic_device = self.config.get('whisper.microphone_device', -1)
            sensitivity = self.config.get('whisper.sensitivity', 5)
            
            listener_settings = ListenerSettings(
                wake_word=wake_word,
                active_mode_duration=active_duration,
                passive_chunk_duration=2.0,
                active_chunk_duration=5.0,
                sample_rate=16000,
                device=mic_device if mic_device != -1 else None,
                sensitivity=sensitivity,
            )
            
            self.voice_listener = VoiceListener(
                whisper_engine=self.whisper_engine,
                settings=listener_settings,
                tts_engine=self.tts_engine,
                parent=self,
            )
            self.voice_listener.transcript_ready.connect(
                self.on_voice_transcript_ready
            )
            self.voice_listener.command_received.connect(
                self.on_voice_command_received
            )
            self.voice_listener.error_occurred.connect(
                self.on_voice_error
            )
            self.voice_listener.status_changed.connect(
                self.on_voice_status_changed
            )
            self.voice_listener.wake_word_detected.connect(
                self.on_wake_word_detected
            )
            self.voice_listener.mode_changed.connect(
                self.on_voice_mode_changed
            )

            self.voice_listener.start_passive_listening()

        except Exception as e:
            logger.error(f"Voice order start failed: {e}")
            QMessageBox.critical(
                self,
                "Sesli Emir Hatası",
                f"Sesli emir başlatılamadı:\n{e}",
            )

    def on_voice_transcript_ready(self, transcript: str):
        """Whisper'dan gelen metni komutlarla eşleştirir."""
        transcript = (transcript or "").strip()
        if not transcript:
            QMessageBox.information(
                self,
                "Sesli Emir",
                "Herhangi bir sesli komut algılanamadı.",
            )
            return

        logger.info(f"Voice transcript: {transcript}")

        category, phrase = self.match_voice_command(transcript)

        if not category:
            QMessageBox.information(
                self,
                "Sesli Emir",
                f"Metin algılandı ama tanımlı bir komut bulunamadı.\n\n"
                f"Metin: \"{transcript}\"",
            )
            return

        # Şimdilik SADECE bilgilendirme yapıyoruz, işlem göndermiyoruz.
        QMessageBox.information(
            self,
            "Sesli Komut Algılandı",
            f"Metin: \"{transcript}\"\n"
            f"Eşleşen komut: [{category}] \"{phrase}\"",
        )

        # İLERİDE: Burada BUY/SELL/REVERSE/STOP aksiyonlarını çağıracağız.
        # Örn:
        # if category == "BUY":
        #     self.on_order_button_clicked("buy")
        # elif category == "SELL":
        #     self.on_order_button_clicked("sell")
        # ...

    def on_voice_status_changed(self, status: str):
        """VoiceListener durumuna göre UI'ı günceller."""
        try:
            if not hasattr(self.ui, 'lblWakeStatus'):
                return

            status_texts = {
                "listening": "🎙️ Dinleniyor...",
                "transcribing": "🧠 Çözümleniyor...",
                "passive": "🎙️ Pasif Mod (Wake word bekliyor)",
                "active": "🎤 Aktif Mod (Komut bekleniyor)",
                "processing": "🧠 İşleniyor...",
                "idle": "⏸️ Durduruldu",
            }
            
            text = status_texts.get(status, f"🎙️ {status}")
            self.ui.lblWakeStatus.setText(text)
            
        except Exception as e:
            logger.error(f"on_voice_status_changed error: {e}")
    
    def on_wake_word_detected(self):
        """Wake word algılandığında çağrılır."""
        logger.info("Wake word detected!")
        try:
            if hasattr(self.ui, 'lblWakeStatus'):
                self.ui.lblWakeStatus.setText("🎤 Wake word algılandı!")
            
            # Status bar'da bilgi göster
            self.statusBar().showMessage("🎤 Dinliyorum... Komutunuzu söyleyin.", 5000)
            
        except Exception as e:
            logger.error(f"on_wake_word_detected error: {e}")
    
    def on_voice_mode_changed(self, mode: str):
        """Voice listener modu değiştiğinde çağrılır."""
        logger.debug(f"Voice mode changed: {mode}")
        try:
            if hasattr(self.ui, 'lblWakeStatus'):
                mode_texts = {
                    "idle": "⏸️ Durduruldu",
                    "passive": "🎙️ Pasif Mod",
                    "active": "🎤 Aktif Mod",
                    "processing": "🧠 İşleniyor...",
                }
                self.ui.lblWakeStatus.setText(mode_texts.get(mode, mode))
                
        except Exception as e:
            logger.error(f"on_voice_mode_changed error: {e}")
    
    def on_voice_command_received(self, command_text: str):
        """
        Wake word sisteminden gelen komutu işle.
        CommandParser ile parse edip trading işlemi yap.
        """
        logger.info(f"Voice command received: {command_text}")
        
        try:
            # CommandParser ile parse et
            parsed = self.command_parser.parse(command_text)
            
            if not parsed:
                self.tts_engine.speak_message('not_understood')
                QMessageBox.information(
                    self,
                    "Sesli Komut",
                    f"Komut anlaşılamadı:\n\"{command_text}\""
                )
                return
            
            # Komutu doğrula
            is_valid, errors = CommandValidator.validate(parsed)
            
            if not is_valid:
                error_text = ", ".join(errors)
                self.tts_engine.speak(f"Hata: {error_text}")
                QMessageBox.warning(
                    self,
                    "Geçersiz Komut",
                    f"Komut: \"{command_text}\"\n\nHatalar:\n{error_text}"
                )
                return
            
            # Komut tipine göre işlem yap
            summary = self.command_parser.format_command_summary(parsed)
            logger.info(f"Parsed command: {summary}")
            
            if parsed.action in ("buy", "sell"):
                # Trading işlemi - onay iste
                reply = QMessageBox.question(
                    self,
                    "Emir Onayı",
                    f"{summary}\n\nBu emri onaylıyor musunuz?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    self.tts_engine.speak_message('command_received')
                    # TODO: Order executor'a gönder
                    # self.execute_voice_order(parsed)
                    QMessageBox.information(
                        self, "Emir",
                        f"Emir alındı:\n{summary}\n\n(Paper Trading aktif)"
                    )
                else:
                    self.tts_engine.speak_message('cancelled')
                    
            elif parsed.action == "close":
                self.tts_engine.speak_message('position_closed')
                QMessageBox.information(self, "Pozisyon", "Pozisyon kapatma komutu alındı.")
                
            elif parsed.action == "balance":
                # Bakiye göster
                self.tts_engine.speak("Bakiye sorgulama")
                # TODO: Bakiyeyi TTS ile söyle
                
            elif parsed.action == "status":
                # Durum göster
                self.tts_engine.speak("Durum sorgulama")
                # TODO: Pozisyonları göster
                
            else:
                QMessageBox.information(
                    self,
                    "Sesli Komut",
                    f"Komut algılandı:\n{summary}"
                )
                
        except Exception as e:
            logger.error(f"Voice command processing error: {e}")
            self.tts_engine.speak_message('error')
            QMessageBox.critical(
                self,
                "Hata",
                f"Komut işlenirken hata oluştu:\n{e}"
            )

    def on_voice_error(self, message: str):
        logger.error(f"VoiceListener error: {message}")
        QMessageBox.critical(
            self,
            "Sesli Emir Hatası",
            message,
        )
        # Durumu pasife çek
        self.on_voice_status_changed("idle")




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

        if hasattr(self.ui, 'btnConnect'):
            self.ui.btnConnect.setEnabled(True)
        if hasattr(self.ui, 'btnDisconnect'):
            self.ui.btnDisconnect.setEnabled(False)

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
        if hasattr(self.ui, 'btnAddCommand'):
            self.ui.btnAddCommand.clicked.connect(self.open_command_keywords_dialog)
                # Sesli Emir butonu
        if hasattr(self.ui, 'btnVoiceOrder'):
            self.ui.btnVoiceOrder.clicked.connect(self.on_voice_order_clicked)




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


            # Buton durumlarını güncelle
            if hasattr(self.ui, 'btnConnect'):
                self.ui.btnConnect.setEnabled(False)
            if hasattr(self.ui, 'btnDisconnect'):
                self.ui.btnDisconnect.setEnabled(True)

            
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
        """
        Paper trading checkbox değişince:
        - Backend'e mod bilgisini iletir
        - UI ikonlarını günceller
        """
        # enabled HER KOŞULDA burada tanımlanıyor
        enabled = (state == Qt.Checked)

        try:
            # Backend'e bildir (OrderExecutor varsa)
            if hasattr(self, "order_executor") and self.order_executor is not None:
                self.order_executor.set_paper_trading(enabled)

            # UI ikonları
            if hasattr(self.ui, "lblPaperIcon"):
                self.ui.lblPaperIcon.setVisible(enabled)
            if hasattr(self.ui, "lblRealIcon"):
                self.ui.lblRealIcon.setVisible(not enabled)

            mode = "PAPER" if enabled else "REAL"
            logger.info(f"Trading mode changed (UI+backend): {mode}")

        except Exception as e:
            logger.error(f"on_paper_trading_changed failed: {e}", exc_info=True)
            QMessageBox.critical(self, "Hata", f"Paper trading mod değişiminde hata:\n{e}")



    def on_order_button_clicked(self, side: str):
            """
            BUY / SELL tıklandığında:
            - UI'dan parametreleri toplar
            - OrderParams oluşturur
            - OrderExecutor'a gönderir
            - Sonucu popup olarak gösterir
            """
            try:
                # Sembol
                symbol = None
                if hasattr(self.ui, "comboSymbol"):
                    symbol = self.ui.comboSymbol.currentText()

                # Aktif sekme: 0=Limit, 1=Market, 2=Stop
                active_tab = 1
                if hasattr(self.ui, "tabOrderTypes"):
                    active_tab = self.ui.tabOrderTypes.currentIndex()

                # Kaldıraç
                leverage = None
                if hasattr(self.ui, "sliderLeverage"):
                    leverage = int(self.ui.sliderLeverage.value())

                # Tab'a göre order_type + fiyat
                order_type = "market"
                price = None

                if active_tab == 0:  # Limit
                    order_type = "limit"
                    if hasattr(self.ui, "spinLimitPrice"):
                        price = float(self.ui.spinLimitPrice.value())
                elif active_tab == 1:  # Market
                    order_type = "market"
                    price = None
                elif active_tab == 2:  # Stop
                    order_type = "stop"
                    if hasattr(self.ui, "spinStopPrice"):
                        price = float(self.ui.spinStopPrice.value())

                # Miktar: Her tab'da (potansiyel olarak) farklı spinbox olabilir ama
                # şimdilik tek spinAmount varsayıyoruz.
                amount = 0.0
                if hasattr(self.ui, "spinAmount"):
                    amount = float(self.ui.spinAmount.value())

                # --- ÖN KONTROLLER ---
                if not symbol:
                    QMessageBox.warning(self, "Uyarı", "Lütfen bir sembol seçin.")
                    return

                if amount <= 0:
                    QMessageBox.warning(self, "Uyarı", "Geçerli bir miktar girin (> 0).")
                    return

                if leverage is None or leverage < 1:
                    leverage = 10  # Varsayılan

                if order_type == "limit" and (price is None or price <= 0):
                    QMessageBox.warning(
                        self, "Uyarı", "Limit emir için geçerli bir fiyat girin."
                    )
                    return

                if order_type == "stop" and (price is None or price <= 0):
                    QMessageBox.warning(
                        self, "Uyarı", "Stop emir için geçerli bir tetik fiyatı girin."
                    )
                    return

                # Stop emir türünü backend henüz tam desteklemiyor; market / limit dışı reddedebilir.
                if order_type not in ("market", "limit"):
                    QMessageBox.warning(
                        self, "Desteklenmiyor", f"{order_type.upper()} türü henüz desteklenmiyor."
                    )
                    return

                logger.info(
                    "UI Order -> symbol=%s, side=%s, order_type=%s, amount=%s, price=%s, leverage=%s",
                    symbol,
                    side,
                    order_type,
                    amount,
                    price,
                    leverage,
                )

                # -------------------------
                # BACKEND EMİR GÖNDERİMİ
                # -------------------------
                params = OrderParams(
                    symbol=symbol,
                    side=side,
                    amount=amount,
                    amount_type="usd",  # UI USDT cinsinden miktar kullanıyor
                    leverage=leverage,
                    order_type=order_type,
                    price=price,
                    extra={"source": "ui"},
                )

                if order_type == "market":
                    result = self.order_executor.execute_market_order(params)
                elif order_type == "limit":
                    result = self.order_executor.execute_limit_order(params)
                else:
                    QMessageBox.critical(
                        self, "Hata", f"Order type desteklenmiyor: {order_type}"
                    )
                    return

                # Sonuç popup
                if result.success:
                    QMessageBox.information(
                        self,
                        "Emir Başarılı",
                        f"Emir başarıyla gönderildi!\n\n"
                        f"Order ID: {result.order_id}\n"
                        f"Durum: {result.status}\n"
                        f"Gerçekleşen miktar: {result.filled_qty}\n"
                        f"Ortalama fiyat: {result.avg_price}",
                    )
                else:
                    QMessageBox.critical(
                        self,
                        "Emir Hatası",
                        f"Emir başarısız.\n\nHata: {result.error_message}",
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
                except Exception:
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
                self.ui.lblConnectionStatus.setText("⚠️ Disconnected")
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
                self.ui.lblBestAsk.setText("N/A")
                self.ui.lblBestAsk.setStyleSheet("")

            if hasattr(self.ui, 'lblBestBid'):
                self.ui.lblBestBid.setText("N/A")
                self.ui.lblBestBid.setStyleSheet("")

            if hasattr(self.ui, 'lblCurrentPrice'):
                self.ui.lblCurrentPrice.setText("N/A")
                self.ui.lblCurrentPrice.setStyleSheet("color: #9E9E9E; font-size: 20px;")

            # 8. Connect / Disconnect butonlarını resetle
            if hasattr(self.ui, 'btnConnect'):
                self.ui.btnConnect.setEnabled(True)
            if hasattr(self.ui, 'btnDisconnect'):
                self.ui.btnDisconnect.setEnabled(False)

            logger.info(f"Disconnected from {exchange_name}")

            QMessageBox.information(
                self,
                "Disconnected",
                f"Successfully disconnected from {exchange_name.title()}"
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

    window = MainWindow()
    # Show window
    window.showMaximized()
    
    logger.info("Application started successfully (Maximized)")
    
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())