"""
Preferences Dialog Controller
=============================
Tüm tercih ayarlarını yönetir:
- Whisper model boyutu
- GPU ayarları  
- Wake word ayarları
- Mikrofon seçimi
- TTS ayarları
- Trading ayarları
"""
from PyQt5.QtWidgets import QDialog, QMessageBox
from PyQt5.QtCore import pyqtSignal
from ui.generated.ui_preferences_dialog import Ui_PreferencesDialog
from utils.config_manager import ConfigManager
from utils.logger import get_logger

logger = get_logger(__name__)

# sounddevice opsiyonel import
try:
    import sounddevice as sd
    _HAS_SD = True
except ImportError:
    sd = None
    _HAS_SD = False


class PreferencesController(QDialog):
    """Tercihler dialog controller."""
    
    # Sinyaller
    settings_changed = pyqtSignal(dict)
    model_changed = pyqtSignal(str)
    
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
        
        # Mikrofon listesini doldur
        self._populate_microphones()
        
        # Slider değer gösterimi için bağlantılar
        self._connect_sliders()
        
        # Butonlar
        self.ui.btnSave.clicked.connect(self.save_preferences)
        self.ui.btnCancel.clicked.connect(self.reject)
        
        # Ayarları yükle
        self.load_preferences()
        
        logger.info("PreferencesController initialized")
    
    def _populate_microphones(self):
        """Mikrofon listesini doldur."""
        if not _HAS_SD:
            logger.warning("sounddevice yüklü değil, mikrofon listesi alınamıyor")
            return
        
        try:
            self.ui.comboMicrophone.clear()
            self.ui.comboMicrophone.addItem("Varsayılan Mikrofon", -1)
            
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    name = dev['name']
                    # İsim çok uzunsa kısalt
                    if len(name) > 50:
                        name = name[:47] + "..."
                    self.ui.comboMicrophone.addItem(name, i)
            
            logger.info(f"Mikrofon listesi dolduruldu: {self.ui.comboMicrophone.count()} cihaz")
            
        except Exception as e:
            logger.error(f"Mikrofon listesi alınamadı: {e}")
    
    def _connect_sliders(self):
        """Slider'ları değer etiketlerine bağla."""
        # Hassasiyet slider
        if hasattr(self.ui, 'sliderSensitivity') and hasattr(self.ui, 'lblSensitivityValue'):
            self.ui.sliderSensitivity.valueChanged.connect(
                lambda v: self.ui.lblSensitivityValue.setText(f"<b>{v}</b>")
            )
        
        # TTS hız slider (varsa etiket)
        if hasattr(self.ui, 'sliderTTSSpeed'):
            # TTS slider için değer etiketi yoksa sadece tooltip güncelle
            self.ui.sliderTTSSpeed.valueChanged.connect(
                lambda v: self.ui.sliderTTSSpeed.setToolTip(f"Hız: {v}%")
            )
    
    def load_preferences(self):
        """Tüm ayarları yükle."""
        try:
            # =====================================
            # WHISPER MODEL AYARLARI
            # =====================================
            
            # Model Boyutu
            model_size = self.config.get('whisper.model_size', 'tiny')
            model_index = {'tiny': 0, 'base': 1, 'small': 2}.get(model_size, 0)
            if hasattr(self.ui, 'comboWhisperModel'):
                self.ui.comboWhisperModel.setCurrentIndex(model_index)
            
            # GPU Kullanımı
            use_gpu = self.config.get('whisper.use_gpu', True)
            if hasattr(self.ui, 'chkUseGPU'):
                self.ui.chkUseGPU.setChecked(use_gpu)
            
            # =====================================
            # WAKE WORD AYARLARI
            # =====================================
            
            # Wake Word
            wake_word = self.config.get('whisper.wake_word', 'Whisper')
            if hasattr(self.ui, 'lineEditWakeWord'):
                self.ui.lineEditWakeWord.setText(wake_word)
            
            # Aktif Mod Süresi
            active_duration = self.config.get('whisper.active_mode_duration', 15)
            if hasattr(self.ui, 'spinActiveModeDuration'):
                self.ui.spinActiveModeDuration.setValue(active_duration)
            
            # =====================================
            # MİKROFON AYARLARI
            # =====================================
            
            # Mikrofon seçimi
            mic_device = self.config.get('whisper.microphone_device', -1)
            if hasattr(self.ui, 'comboMicrophone'):
                # Device ID'ye göre index bul
                for i in range(self.ui.comboMicrophone.count()):
                    if self.ui.comboMicrophone.itemData(i) == mic_device:
                        self.ui.comboMicrophone.setCurrentIndex(i)
                        break
            
            # Hassasiyet
            sensitivity = self.config.get('whisper.sensitivity', 5)
            if hasattr(self.ui, 'sliderSensitivity'):
                self.ui.sliderSensitivity.setValue(sensitivity)
            if hasattr(self.ui, 'lblSensitivityValue'):
                self.ui.lblSensitivityValue.setText(f"<b>{sensitivity}</b>")
            
            # =====================================
            # TTS AYARLARI
            # =====================================
            
            # TTS Etkin
            tts_enabled = self.config.get('tts.enabled', True)
            if hasattr(self.ui, 'chkEnableTTS'):
                self.ui.chkEnableTTS.setChecked(tts_enabled)
            
            # TTS Hızı (50-200 aralığı, varsayılan 100)
            tts_speed = self.config.get('tts.speed', 100)
            if hasattr(self.ui, 'sliderTTSSpeed'):
                self.ui.sliderTTSSpeed.setValue(tts_speed)
            
            # Onay Bekleme Süresi
            confirm_timeout = self.config.get('tts.confirmation_timeout', 10)
            if hasattr(self.ui, 'spinConfirmationTimeout'):
                self.ui.spinConfirmationTimeout.setValue(confirm_timeout)
            
            # =====================================
            # GENEL AYARLAR (diğer tab'larda olabilir)
            # =====================================
            
            # Dil
            lang = self.config.get('app.language', 'tr')
            if hasattr(self.ui, 'comboLanguage'):
                lang_index = {'tr': 0, 'en': 1, 'de': 2}.get(lang, 0)
                self.ui.comboLanguage.setCurrentIndex(lang_index)
            
            # =====================================
            # TRADING AYARLARI
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
            
            # Paper Trading Bakiyesi
            paper_balance = self.config.get('trading.paper_balance', 10000.0)
            if hasattr(self.ui, 'spinPaperTradingBalance'):
                self.ui.spinPaperTradingBalance.setValue(paper_balance)
            
            # Pozisyon Modu
            position_mode = self.config.get('trading.position_mode', 'one-way')
            if hasattr(self.ui, 'comboPositionMode'):
                pos_index = {'one-way': 0, 'hedge': 1}.get(position_mode.lower(), 0)
                self.ui.comboPositionMode.setCurrentIndex(pos_index)
            
            logger.info("Preferences loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load preferences: {e}")
            QMessageBox.warning(self, "Uyarı", f"Ayarlar yüklenirken hata: {e}")
    
    def save_preferences(self):
        """Tüm ayarları kaydet."""
        try:
            old_model = self.config.get('whisper.model_size', 'tiny')
            
            # =====================================
            # WHISPER MODEL AYARLARI
            # =====================================
            
            # Model Boyutu
            if hasattr(self.ui, 'comboWhisperModel'):
                model_index = self.ui.comboWhisperModel.currentIndex()
                new_model = self.MODEL_SIZES.get(model_index, 'tiny')
                self.config.set('whisper.model_size', new_model)
            else:
                new_model = old_model
            
            # GPU Kullanımı
            if hasattr(self.ui, 'chkUseGPU'):
                self.config.set('whisper.use_gpu', self.ui.chkUseGPU.isChecked())
            
            # =====================================
            # WAKE WORD AYARLARI
            # =====================================
            
            # Wake Word
            if hasattr(self.ui, 'lineEditWakeWord'):
                wake_word = self.ui.lineEditWakeWord.text().strip()
                if not wake_word:
                    QMessageBox.warning(self, "Hata", "Wake word boş olamaz!")
                    return
                self.config.set('whisper.wake_word', wake_word)
            
            # Aktif Mod Süresi
            if hasattr(self.ui, 'spinActiveModeDuration'):
                self.config.set('whisper.active_mode_duration', 
                              self.ui.spinActiveModeDuration.value())
            
            # =====================================
            # MİKROFON AYARLARI
            # =====================================
            
            # Mikrofon
            if hasattr(self.ui, 'comboMicrophone'):
                mic_device = self.ui.comboMicrophone.currentData()
                self.config.set('whisper.microphone_device', mic_device)
            
            # Hassasiyet
            if hasattr(self.ui, 'sliderSensitivity'):
                self.config.set('whisper.sensitivity', 
                              self.ui.sliderSensitivity.value())
            
            # =====================================
            # TTS AYARLARI
            # =====================================
            
            # TTS Etkin
            if hasattr(self.ui, 'chkEnableTTS'):
                self.config.set('tts.enabled', self.ui.chkEnableTTS.isChecked())
            
            # TTS Hızı
            if hasattr(self.ui, 'sliderTTSSpeed'):
                self.config.set('tts.speed', self.ui.sliderTTSSpeed.value())
            
            # Onay Bekleme Süresi
            if hasattr(self.ui, 'spinConfirmationTimeout'):
                self.config.set('tts.confirmation_timeout', 
                              self.ui.spinConfirmationTimeout.value())
            
            # =====================================
            # GENEL AYARLAR
            # =====================================
            
            if hasattr(self.ui, 'comboLanguage'):
                lang_map = {0: 'tr', 1: 'en', 2: 'de'}
                lang = lang_map.get(self.ui.comboLanguage.currentIndex(), 'tr')
                self.config.set('app.language', lang)
            
            # =====================================
            # TRADING AYARLARI
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
            
            if hasattr(self.ui, 'spinPaperTradingBalance'):
                self.config.set('trading.paper_balance', 
                              self.ui.spinPaperTradingBalance.value())
            
            if hasattr(self.ui, 'comboPositionMode'):
                pos_map = {0: 'one-way', 1: 'hedge'}
                pos_mode = pos_map.get(
                    self.ui.comboPositionMode.currentIndex(), 'one-way')
                self.config.set('trading.position_mode', pos_mode)
            
            # =====================================
            # KAYDET
            # =====================================
            
            self.config.save()
            
            # Model değiştiyse uyar
            if old_model != new_model:
                logger.info(f"Whisper model changed: {old_model} -> {new_model}")
                self.model_changed.emit(new_model)
                QMessageBox.information(
                    self, 
                    "Model Değişikliği",
                    f"Whisper modeli '{new_model}' olarak değiştirildi.\n"
                    "Değişikliğin uygulanması için uygulamayı yeniden başlatın."
                )
            
            # Ayar değişiklik sinyali
            self.settings_changed.emit(self.get_current_settings())
            
            logger.info("Preferences saved successfully")
            QMessageBox.information(self, "Başarılı", "Ayarlar kaydedildi!")
            self.accept()
            
        except Exception as e:
            logger.error(f"Failed to save preferences: {e}")
            QMessageBox.critical(self, "Hata", f"Ayarlar kaydedilirken hata: {e}")
    
    def get_current_settings(self) -> dict:
        """Mevcut ayarları dictionary olarak döndür."""
        settings = {}
        
        if hasattr(self.ui, 'comboWhisperModel'):
            settings['model_size'] = self.MODEL_SIZES.get(
                self.ui.comboWhisperModel.currentIndex(), 'tiny')
        
        if hasattr(self.ui, 'chkUseGPU'):
            settings['use_gpu'] = self.ui.chkUseGPU.isChecked()
        
        if hasattr(self.ui, 'lineEditWakeWord'):
            settings['wake_word'] = self.ui.lineEditWakeWord.text().strip()
        
        if hasattr(self.ui, 'spinActiveModeDuration'):
            settings['active_mode_duration'] = self.ui.spinActiveModeDuration.value()
        
        if hasattr(self.ui, 'comboMicrophone'):
            settings['microphone_device'] = self.ui.comboMicrophone.currentData()
        
        if hasattr(self.ui, 'sliderSensitivity'):
            settings['sensitivity'] = self.ui.sliderSensitivity.value()
        
        if hasattr(self.ui, 'chkEnableTTS'):
            settings['tts_enabled'] = self.ui.chkEnableTTS.isChecked()
        
        if hasattr(self.ui, 'sliderTTSSpeed'):
            settings['tts_speed'] = self.ui.sliderTTSSpeed.value()
        
        if hasattr(self.ui, 'spinConfirmationTimeout'):
            settings['confirmation_timeout'] = self.ui.spinConfirmationTimeout.value()
        
        return settings
    
    def refresh_microphones(self):
        """Mikrofon listesini yenile."""
        current_device = None
        if hasattr(self.ui, 'comboMicrophone'):
            current_device = self.ui.comboMicrophone.currentData()
        
        self._populate_microphones()
        
        # Önceki seçimi geri yükle
        if current_device is not None and hasattr(self.ui, 'comboMicrophone'):
            for i in range(self.ui.comboMicrophone.count()):
                if self.ui.comboMicrophone.itemData(i) == current_device:
                    self.ui.comboMicrophone.setCurrentIndex(i)
                    break
