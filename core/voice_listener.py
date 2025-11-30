"""
Voice Listener with Wake Word System
=====================================
İki modlu sesli komut sistemi:

1. PASİF MOD (Sürekli Dinleme):
   - Düşük CPU kullanımı
   - Sadece wake word (varsayılan: "Whisper") bekler
   - Kısa ses parçaları analiz edilir

2. AKTİF MOD:
   - Wake word algılandığında tetiklenir
   - TTS: "Dinliyorum..."
   - Tam komut beklenir (ör: "Al BTC 100 dolar")
   - Timeout (varsayılan: 15 sn) sonrası pasif moda döner
"""
from typing import Optional, Callable, List
from enum import Enum
import threading
import traceback
import time
from dataclasses import dataclass

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, QTimer

# sounddevice OPSİYONEL
try:
    import sounddevice as sd
    _HAS_SD = True
except ImportError:
    sd = None
    _HAS_SD = False

from utils.logger import get_logger

logger = get_logger(__name__)


class ListenerMode(Enum):
    """Dinleyici modları."""
    IDLE = "idle"           # Durdurulmuş
    PASSIVE = "passive"     # Sürekli dinleme, wake word bekliyor
    ACTIVE = "active"       # Komut dinleme modu
    PROCESSING = "processing"  # İşleniyor


@dataclass 
class ListenerSettings:
    """Dinleyici ayarları."""
    wake_word: str = "Whisper"              # Uyandırma kelimesi
    wake_word_variants: List[str] = None    # Alternatif yazımlar
    active_mode_duration: int = 15          # Aktif mod süresi (saniye)
    passive_chunk_duration: float = 2.0     # Pasif modda chunk süresi
    active_chunk_duration: float = 5.0      # Aktif modda chunk süresi
    sample_rate: int = 16000
    device: Optional[int] = None            # Mikrofon cihazı (-1 = varsayılan)
    sensitivity: int = 5                    # Ses hassasiyeti (1-10)
    
    def __post_init__(self):
        # Wake word varyantları
        if self.wake_word_variants is None:
            # Türkçe telaffuz varyantları
            self.wake_word_variants = [
                self.wake_word.lower(),
                "vispır", "visper", "wisper", "vısper",
                "whisper", "wispır", "hvisper",
            ]
        
        # Device -1 ise None yap (varsayılan mikrofon)
        if self.device == -1:
            self.device = None


class VoiceListener(QThread):
    """
    Wake Word destekli sesli komut dinleyicisi.
    
    Sinyaller:
        - wake_word_detected: Wake word algılandı
        - command_received: Komut metni alındı (aktif modda)
        - mode_changed: Mod değişti (idle/passive/active/processing)
        - error_occurred: Hata oluştu
        - audio_level: Ses seviyesi (0-100, UI için)
    
    Kullanım:
        listener = VoiceListener(whisper_engine, settings)
        listener.wake_word_detected.connect(on_wake)
        listener.command_received.connect(on_command)
        listener.start_passive_listening()  # Sürekli dinlemeyi başlat
    """
    
    # Sinyaller
    wake_word_detected = pyqtSignal()           # Wake word algılandı
    command_received = pyqtSignal(str)          # Komut metni
    mode_changed = pyqtSignal(str)              # Mod değişikliği
    error_occurred = pyqtSignal(str)            # Hata
    audio_level = pyqtSignal(int)               # Ses seviyesi (0-100)
    transcript_ready = pyqtSignal(str)          # Eski API uyumluluğu
    status_changed = pyqtSignal(str)            # Eski API uyumluluğu
    
    def __init__(
        self,
        whisper_engine,
        settings: Optional[ListenerSettings] = None,
        tts_engine=None,
        parent=None,
    ):
        super().__init__(parent)
        self.whisper_engine = whisper_engine
        self.settings = settings or ListenerSettings()
        self.tts_engine = tts_engine
        
        # Durum
        self._mode = ListenerMode.IDLE
        self._stop_event = threading.Event()
        self._active_mode_timer: Optional[QTimer] = None
        self._active_mode_start: float = 0
        
        # Thread-safe erişim
        self._lock = threading.Lock()
        
        logger.info("[VoiceListener] Başlatıldı")
    
    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    
    @property
    def mode(self) -> ListenerMode:
        """Mevcut mod."""
        return self._mode
    
    @property
    def is_listening(self) -> bool:
        """Dinleme aktif mi?"""
        return self._mode in (ListenerMode.PASSIVE, ListenerMode.ACTIVE)
    
    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    
    def start_passive_listening(self):
        """Sürekli dinlemeyi başlat (pasif mod)."""
        if not _HAS_SD:
            self.error_occurred.emit(
                "Mikrofon modülü (sounddevice) yüklü değil. "
                "pip install sounddevice"
            )
            return
        
        self._stop_event.clear()
        self._set_mode(ListenerMode.PASSIVE)
        
        if not self.isRunning():
            self.start()
        
        logger.info("[VoiceListener] Pasif dinleme başlatıldı")
    
    def stop_listening(self):
        """Dinlemeyi durdur."""
        self._stop_event.set()
        self._set_mode(ListenerMode.IDLE)
        logger.info("[VoiceListener] Dinleme durduruldu")
    
    def activate(self):
        """Aktif moda geç (wake word algılandığında çağrılır)."""
        self._set_mode(ListenerMode.ACTIVE)
        self._active_mode_start = time.time()
        
        # TTS ile bildir
        if self.tts_engine:
            self.tts_engine.speak_message('wake_detected')
        
        logger.info("[VoiceListener] Aktif mod başladı")
    
    def deactivate(self):
        """Pasif moda dön."""
        if self._mode == ListenerMode.ACTIVE:
            self._set_mode(ListenerMode.PASSIVE)
            
            # TTS ile bildir
            if self.tts_engine:
                self.tts_engine.speak_message('timeout')
            
            logger.info("[VoiceListener] Pasif moda dönüldü (timeout)")
    
    def stop(self):
        """Thread'i durdur."""
        self._stop_event.set()
        self._set_mode(ListenerMode.IDLE)
        self.wait(2000)  # 2 saniye bekle
    
    # ------------------------------------------------------------------
    # Thread Implementation
    # ------------------------------------------------------------------
    
    def run(self):
        """Ana thread döngüsü."""
        logger.info("[VoiceListener] Thread başladı")
        
        while not self._stop_event.is_set():
            try:
                if self._mode == ListenerMode.PASSIVE:
                    self._passive_loop()
                elif self._mode == ListenerMode.ACTIVE:
                    self._active_loop()
                else:
                    # IDLE modunda bekle
                    time.sleep(0.1)
                    
            except Exception as e:
                error_msg = f"VoiceListener hatası: {e}"
                logger.error(f"{error_msg}\n{traceback.format_exc()}")
                self.error_occurred.emit(error_msg)
                time.sleep(1.0)  # Hata sonrası biraz bekle
        
        logger.info("[VoiceListener] Thread sonlandı")
    
    def _passive_loop(self):
        """
        Pasif mod döngüsü.
        Kısa ses parçaları alıp wake word arıyor.
        """
        chunk_duration = self.settings.passive_chunk_duration
        frames = int(chunk_duration * self.settings.sample_rate)
        
        # Device kontrolü - None veya -1 ise varsayılan kullan
        device = self.settings.device
        if device == -1:
            device = None
        
        try:
            # Kısa kayıt al
            recording = sd.rec(
                frames,
                samplerate=self.settings.sample_rate,
                channels=1,
                dtype="float32",
                device=device,
            )
            sd.wait()
            
            if self._stop_event.is_set():
                return
            
            audio = np.squeeze(recording)
            
            # Ses seviyesi hesapla ve emit et
            level = self._calculate_audio_level(audio)
            self.audio_level.emit(level)
            
            # Hassasiyete göre eşik hesapla (1-10 → 15-1 eşik)
            # Düşük hassasiyet = yüksek eşik, yüksek hassasiyet = düşük eşik
            threshold = max(1, 16 - self.settings.sensitivity)
            
            # Sessizse atla (CPU tasarrufu)
            if level < threshold:
                return
            
            # Transcribe
            text = self.whisper_engine.transcribe_ndarray(
                audio, sample_rate=self.settings.sample_rate
            )
            
            if text:
                text_lower = text.lower().strip()
                logger.debug(f"[Passive] Algılanan: '{text}'")
                
                # Wake word kontrolü
                if self._check_wake_word(text_lower):
                    logger.info(f"[VoiceListener] Wake word algılandı: '{text}'")
                    self.wake_word_detected.emit()
                    self.activate()
                    
        except Exception as e:
            logger.error(f"[Passive] Hata: {e}")
    
    def _active_loop(self):
        """
        Aktif mod döngüsü.
        Tam komut dinleme - daha uzun süre.
        """
        # Timeout kontrolü
        elapsed = time.time() - self._active_mode_start
        if elapsed >= self.settings.active_mode_duration:
            self.deactivate()
            return
        
        chunk_duration = self.settings.active_chunk_duration
        frames = int(chunk_duration * self.settings.sample_rate)
        
        # Device kontrolü - None veya -1 ise varsayılan kullan
        device = self.settings.device
        if device == -1:
            device = None
        
        try:
            self._set_mode(ListenerMode.ACTIVE)
            
            # Kayıt al
            logger.debug(f"[Active] {chunk_duration}sn kayıt alınıyor...")
            recording = sd.rec(
                frames,
                samplerate=self.settings.sample_rate,
                channels=1,
                dtype="float32",
                device=device,
            )
            sd.wait()
            
            if self._stop_event.is_set():
                return
            
            audio = np.squeeze(recording)
            
            # Ses seviyesi
            level = self._calculate_audio_level(audio)
            self.audio_level.emit(level)
            
            # Hassasiyete göre eşik
            threshold = max(1, 16 - self.settings.sensitivity)
            
            # Sessizse timeout'a doğru devam et
            if level < threshold:
                logger.debug("[Active] Sessizlik algılandı")
                return
            
            # Transcribe
            self._set_mode(ListenerMode.PROCESSING)
            
            text = self.whisper_engine.transcribe_ndarray(
                audio, sample_rate=self.settings.sample_rate
            )
            
            if text and text.strip():
                text = text.strip()
                logger.info(f"[Active] Komut alındı: '{text}'")
                
                # Wake word'ü temizle (varsa)
                command = self._remove_wake_word(text)
                
                if command:
                    # Komut alındı, emit et ve pasif moda dön
                    self.command_received.emit(command)
                    self.transcript_ready.emit(command)  # Eski API
                    
                    # TTS ile onayla
                    if self.tts_engine:
                        self.tts_engine.speak_message('command_received')
                    
                    self._set_mode(ListenerMode.PASSIVE)
                else:
                    # Sadece wake word söylenmiş, aktif modda kal
                    self._set_mode(ListenerMode.ACTIVE)
            else:
                self._set_mode(ListenerMode.ACTIVE)
                
        except Exception as e:
            logger.error(f"[Active] Hata: {e}")
            self._set_mode(ListenerMode.ACTIVE)
    
    # ------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------
    
    def _set_mode(self, mode: ListenerMode):
        """Modu değiştir ve sinyal gönder."""
        with self._lock:
            if self._mode != mode:
                self._mode = mode
                self.mode_changed.emit(mode.value)
                self.status_changed.emit(mode.value)  # Eski API
                logger.debug(f"[VoiceListener] Mod değişti: {mode.value}")
    
    def _check_wake_word(self, text: str) -> bool:
        """Wake word var mı kontrol et."""
        text_lower = text.lower()
        
        # Ana wake word
        if self.settings.wake_word.lower() in text_lower:
            return True
        
        # Varyantlar
        for variant in self.settings.wake_word_variants:
            if variant in text_lower:
                return True
        
        return False
    
    def _remove_wake_word(self, text: str) -> str:
        """Metinden wake word'ü kaldır."""
        text_lower = text.lower()
        result = text
        
        # Ana wake word'ü kaldır
        wake_lower = self.settings.wake_word.lower()
        if wake_lower in text_lower:
            # Case-insensitive replace
            import re
            result = re.sub(re.escape(wake_lower), '', result, flags=re.IGNORECASE)
        
        # Varyantları kaldır
        for variant in self.settings.wake_word_variants:
            if variant in text_lower:
                import re
                result = re.sub(re.escape(variant), '', result, flags=re.IGNORECASE)
        
        return result.strip()
    
    def _calculate_audio_level(self, audio: np.ndarray) -> int:
        """
        Ses seviyesini 0-100 arasında hesapla.
        """
        if audio is None or audio.size == 0:
            return 0
        
        # RMS hesapla
        rms = np.sqrt(np.mean(audio ** 2))
        
        # dB'ye çevir ve normalize et
        if rms > 0:
            db = 20 * np.log10(rms + 1e-10)
            # -60dB ile 0dB arasını 0-100'e map et
            level = int(max(0, min(100, (db + 60) * 100 / 60)))
        else:
            level = 0
        
        return level
    
    # ------------------------------------------------------------------
    # Legacy API (Geriye uyumluluk)
    # ------------------------------------------------------------------
    
    def start_listening(self):
        """Eski API - start_passive_listening'e yönlendir."""
        self.start_passive_listening()
    
    def listen_once(self, duration: float = 5.0):
        """
        Tek seferlik dinleme (eski API).
        Aktif modu simüle eder.
        """
        if not _HAS_SD:
            self.error_occurred.emit("sounddevice yüklü değil")
            return
        
        # Device kontrolü
        device = self.settings.device
        if device == -1:
            device = None
        
        try:
            self.status_changed.emit("listening")
            
            frames = int(duration * self.settings.sample_rate)
            recording = sd.rec(
                frames,
                samplerate=self.settings.sample_rate,
                channels=1,
                dtype="float32",
                device=device,
            )
            sd.wait()
            
            audio = np.squeeze(recording)
            
            self.status_changed.emit("transcribing")
            
            text = self.whisper_engine.transcribe_ndarray(
                audio, sample_rate=self.settings.sample_rate
            )
            
            self.transcript_ready.emit(text or "")
            self.status_changed.emit("idle")
            
        except Exception as e:
            self.error_occurred.emit(str(e))
            self.status_changed.emit("idle")


# Yardımcı fonksiyon - mikrofon listesi
def get_microphone_list() -> list:
    """Kullanılabilir mikrofonları listele."""
    if not _HAS_SD:
        return []
    
    try:
        devices = sd.query_devices()
        microphones = []
        
        for i, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                microphones.append({
                    'index': i,
                    'name': dev['name'],
                    'channels': dev['max_input_channels'],
                    'sample_rate': dev['default_samplerate'],
                })
        
        return microphones
    except:
        return []
