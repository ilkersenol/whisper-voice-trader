"""Preferences Dialog Controller"""
from PyQt5.QtWidgets import QDialog, QMessageBox
from ui.generated.ui_preferences_dialog import Ui_PreferencesDialog
from utils.config_manager import ConfigManager
from utils.logger import get_logger

logger = get_logger(__name__)


class PreferencesController(QDialog):
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
    
    def load_preferences(self):
        """Load current preferences"""
        try:
            # Language
            lang = self.config.get('app.language', 'tr')
            if lang == 'tr':
                self.ui.comboLanguage.setCurrentIndex(0)
            elif lang == 'en':
                self.ui.comboLanguage.setCurrentIndex(1)
            
            # Wake word
            wake = self.config.get('whisper.wake_word', 'Whisper')
            self.ui.lineEditWakeWord.setText(wake)
            
            # GPU
            gpu = self.config.get('whisper.use_gpu', True)
            self.ui.checkBoxGPU.setChecked(gpu)
            
            # TTS
            tts = self.config.get('tts.enabled', True)
            self.ui.checkBoxTTS.setChecked(tts)
            
            # Paper trading
            paper = self.config.get('trading.paper_trading', True)
            self.ui.checkBoxPaperTrading.setChecked(paper)
            
            # Leverage
            leverage = self.config.get('trading.default_leverage', 10)
            self.ui.spinBoxLeverage.setValue(leverage)
            
            logger.info("Preferences loaded")
        except Exception as e:
            logger.error(f"Failed to load preferences: {e}")
    
    def save_preferences(self):
        """Save preferences"""
        try:
            # Language
            lang_idx = self.ui.comboLanguage.currentIndex()
            lang = 'tr' if lang_idx == 0 else 'en'
            self.config.set('app.language', lang)
            
            # Wake word
            wake = self.ui.lineEditWakeWord.text().strip()
            if not wake:
                QMessageBox.warning(self, "Error", "Wake word cannot be empty")
                return
            self.config.set('whisper.wake_word', wake)
            
            # GPU
            self.config.set('whisper.use_gpu', self.ui.checkBoxGPU.isChecked())
            
            # TTS
            self.config.set('tts.enabled', self.ui.checkBoxTTS.isChecked())
            
            # Paper trading
            self.config.set('trading.paper_trading', self.ui.checkBoxPaperTrading.isChecked())
            
            # Leverage
            self.config.set('trading.default_leverage', self.ui.spinBoxLeverage.value())
            
            # Save to file
            self.config.save()
            
            QMessageBox.information(self, "Success", "Preferences saved!")
            logger.info("Preferences saved")
            self.accept()
        except Exception as e:
            logger.error(f"Save error: {e}")
            QMessageBox.critical(self, "Error", str(e))