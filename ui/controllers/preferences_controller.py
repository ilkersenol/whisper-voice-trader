"""
Preferences Dialog Controller
- Whisper model boyutu seçimi
- GPU ayarları
- TTS ayarları
- Wake word ayarları
- Trading ayarları
"""
from PyQt5.QtWidgets import QDialog, QMessageBox
from PyQt5.QtCore import pyqtSignal
from ui.generated.ui_preferences_dialog import Ui_PreferencesDialog
from utils.config_manager import ConfigManager
from utils.logger import get_logger

logger = get_logger(__name__)


class PreferencesController(QDialog):
    """Tercihler dialog controller."""
    
    # Ayarlar değiştiğinde sinyal gönder
    settings_changed = pyqtSignal(dict)
    model_changed = pyqtSignal(str)  # Model boyutu değiştiğinde
    
    # Model boyutu mapping
    MODEL_SIZES = {
        0: "tiny",   # Tiny (39M)
        1: "base",   # Base (74M)
        2: "small",  # Small (244M)
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_PreferencesDialog()
        self.ui.setupUi(self)
        self.config = ConfigManager()
        
        # Connect buttons
        self.ui.btnSave.clicked.connect(self.save_preferences)
        self.ui.btnCancel.clicked.connect(self.reject)
        
        # Load preferences
        self.load_preferences()
        
        logger.info("PreferencesController initialized")
    
    def load_preferences(self):
        """Mevcut ayarları yükle."""
        try:
            # =====================================
            # Ses Ayarları Tab
            # =====================================
            
            # Whisper Model Boyutu
            model_size = self.config.get('whisper.model_size', 'tiny')
            model_index = {'tiny': 0, 'base': 1, 'small': 2}.get(model_size, 0)
            self.ui.comboWhisperModel.setCurrentIndex(model_index)
            
            # GPU Kullanımı
            use_gpu = self.config.get('whisper.use_gpu', True)
            self.ui.chkUseGPU.setChecked(use_gpu)
            
            # Wake Word
            wake_word = self.config.get('whisper.wake_word', 'Whisper')
            self.ui.lineEditWakeWord.setText(wake_word)
            
            # Aktif Mod Süresi
            active_duration = self.config.get('whisper.active_mode_duration', 15)
            self.ui.spinActiveModeDuration.setValue(active_duration)
            
            # =====================================
            # TTS Ayarları
            # =====================================
            
            # TTS Etkin
            tts_enabled = self.config.get('tts.enabled', True)
            if hasattr(self.ui, 'chkTTSEnabled'):
                self.ui.chkTTSEnabled.setChecked(tts_enabled)
            
            # TTS Hızı
            tts_rate = self.config.get('tts.rate', 150)
            if hasattr(self.ui, 'spinTTSRate'):
                self.ui.spinTTSRate.setValue(tts_rate)
            
            # TTS Ses
            tts_volume = self.config.get('tts.volume', 1.0)
            if hasattr(self.ui, 'sliderTTSVolume'):
                self.ui.sliderTTSVolume.setValue(int(tts_volume * 100))
            
            # =====================================
            # Genel Ayarlar
            # =====================================
            
            # Dil
            lang = self.config.get('app.language', 'tr')
            if hasattr(self.ui, 'comboLanguage'):
                lang_index = {'tr': 0, 'en': 1, 'de': 2}.get(lang, 0)
                self.ui.comboLanguage.setCurrentIndex(lang_index)
            
            # =====================================
            # Trading Ayarları
            # =====================================
            
            # Paper Trading
            paper_trading = self.config.get('trading.paper_trading', True)
            if hasattr(self.ui, 'chkPaperTrading'):
                self.ui.chkPaperTrading.setChecked(paper_trading)
            
            # Varsayılan Kaldıraç
            leverage = self.config.get('trading.default_leverage', 10)
            if hasattr(self.ui, 'spinDefaultLeverage'):
                self.ui.spinDefaultLeverage.setValue(leverage)
            
            # Varsayılan Emir Tipi
            order_type = self.config.get('trading.default_order_type', 'market')
            if hasattr(self.ui, 'comboDefaultOrderType'):
                order_index = {'market': 0, 'limit': 1}.get(order_type.lower(), 0)
                self.ui.comboDefaultOrderType.setCurrentIndex(order_index)
            
            logger.info("Preferences loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load preferences: {e}")
            QMessageBox.warning(self, "Uyarı", f"Ayarlar yüklenirken hata: {e}")
    
    def save_preferences(self):
        """Ayarları kaydet."""
        try:
            old_model = self.config.get('whisper.model_size', 'tiny')
            
            # =====================================
            # Ses Ayarları
            # =====================================
            
            # Whisper Model Boyutu
            model_index = self.ui.comboWhisperModel.currentIndex()
            new_model = self.MODEL_SIZES.get(model_index, 'tiny')
            self.config.set('whisper.model_size', new_model)
            
            # GPU Kullanımı
            self.config.set('whisper.use_gpu', self.ui.chkUseGPU.isChecked())
            
            # Wake Word
            wake_word = self.ui.lineEditWakeWord.text().strip()
            if not wake_word:
                QMessageBox.warning(self, "Hata", "Wake word boş olamaz!")
                return
            self.config.set('whisper.wake_word', wake_word)
            
            # Aktif Mod Süresi
            self.config.set('whisper.active_mode_duration', 
                          self.ui.spinActiveModeDuration.value())
            
            # =====================================
            # TTS Ayarları
            # =====================================
            
            if hasattr(self.ui, 'chkTTSEnabled'):
                self.config.set('tts.enabled', self.ui.chkTTSEnabled.isChecked())
            
            if hasattr(self.ui, 'spinTTSRate'):
                self.config.set('tts.rate', self.ui.spinTTSRate.value())
            
            if hasattr(self.ui, 'sliderTTSVolume'):
                self.config.set('tts.volume', 
                              self.ui.sliderTTSVolume.value() / 100.0)
            
            # =====================================
            # Genel Ayarlar
            # =====================================
            
            if hasattr(self.ui, 'comboLanguage'):
                lang_map = {0: 'tr', 1: 'en', 2: 'de'}
                lang = lang_map.get(self.ui.comboLanguage.currentIndex(), 'tr')
                self.config.set('app.language', lang)
            
            # =====================================
            # Trading Ayarları
            # =====================================
            
            if hasattr(self.ui, 'chkPaperTrading'):
                self.config.set('trading.paper_trading', 
                              self.ui.chkPaperTrading.isChecked())
            
            if hasattr(self.ui, 'spinDefaultLeverage'):
                self.config.set('trading.default_leverage', 
                              self.ui.spinDefaultLeverage.value())
            
            if hasattr(self.ui, 'comboDefaultOrderType'):
                order_map = {0: 'market', 1: 'limit'}
                order_type = order_map.get(
                    self.ui.comboDefaultOrderType.currentIndex(), 'market')
                self.config.set('trading.default_order_type', order_type)
            
            # Kaydet
            self.config.save()
            
            # Model değiştiyse sinyal gönder
            if old_model != new_model:
                logger.info(f"Whisper model changed: {old_model} -> {new_model}")
                self.model_changed.emit(new_model)
                QMessageBox.information(
                    self, 
                    "Model Değişikliği",
                    f"Whisper modeli '{new_model}' olarak değiştirildi.\n"
                    "Değişikliğin uygulanması için uygulamayı yeniden başlatın."
                )
            
            # Genel sinyal gönder
            self.settings_changed.emit({
                'model_size': new_model,
                'use_gpu': self.ui.chkUseGPU.isChecked(),
                'wake_word': wake_word,
                'active_mode_duration': self.ui.spinActiveModeDuration.value(),
            })
            
            logger.info("Preferences saved successfully")
            QMessageBox.information(self, "Başarılı", "Ayarlar kaydedildi!")
            self.accept()
            
        except Exception as e:
            logger.error(f"Failed to save preferences: {e}")
            QMessageBox.critical(self, "Hata", f"Ayarlar kaydedilirken hata: {e}")
    
    def get_current_settings(self) -> dict:
        """Mevcut ayarları dictionary olarak döndür."""
        return {
            'model_size': self.MODEL_SIZES.get(
                self.ui.comboWhisperModel.currentIndex(), 'tiny'),
            'use_gpu': self.ui.chkUseGPU.isChecked(),
            'wake_word': self.ui.lineEditWakeWord.text().strip(),
            'active_mode_duration': self.ui.spinActiveModeDuration.value(),
        }
