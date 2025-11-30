# core/wake_word_listener.py
"""
Wake Word Listener - Sürekli Dinleme Sistemi
"Whisper" kelimesi algılandığında aktif moda geçer.
"""

from typing import Optional, Callable
import threading
import time
import traceback

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, QTimer

# sounddevice OPSİYONEL
try:
    import sounddevice as sd
    _HAS_SD = True
except ImportError:
    sd = None
    _HAS_SD = False


class WakeWordListener(QThread):
    """
    Sürekli dinleme + Wake Word algılama sistemi.
    
    Çalışma Modu:
    ┌─────────────────────────────────────────────────────┐
    │  PASİF MOD (Sürekli Dinleme)                        │
    │  - Kısa ses parçaları alır (1-2 saniye)             │
    │  - Sadece wake word'ü arar                          │
    │  - Düşük CPU kullanımı                              │
    │                                                     │
    │         ↓ Wake word algılandı                       │
    │                                                     │
    │  AKTİF MOD (active_duration saniye)                 │
    │  - TTS: "Dinliyorum..."                             │
    │  - Tam komut beklenir                               │
    │  - Komut işlenir veya timeout → Pasif moda dön     │
    └─────────────────────────────────────────────────────┘
    """
    
    # Sinyaller
    wake_word_detected = pyqtSignal()           # Wake word algılandı
    command_ready = pyqtSignal(str)              # Tam komut hazır (aktif mod transcript)
    status_changed = pyqtSignal(str)             # "passive" | "active" | "processing"
    error_occurred = pyqtSignal(str)             # Hata mesajı
    
    # Modlar
    MODE_PASSIVE = "passive"
    MODE_ACTIVE = "active"
    MODE_PROCESSING = "processing"
    
    def __init__(
        self,
        whisper_engine,
        wake_word: str = "Whisper",
        active_duration: float = 15.0,    # Aktif mod süresi (saniye)
        passive_chunk_duration: float = 2.0,  # Pasif modda her chunk süresi
        active_chunk_duration: float = 5.0,   # Aktif modda dinleme süresi
        sample_rate: int = 16_000,
        device: Optional[int] = None,
        tts_engine=None,
        parent=None,
    ):
        super().__init__(parent)
        
        self.whisper_engine = whisper_engine
        self.wake_word = wake_word.lower().strip()
        self.active_duration = active_duration
        self.passive_chunk_duration = passive_chunk_duration
        self.active_chunk_duration = active_chunk_duration
        self.sample_rate = sample_rate
        self.device = device
        self.tts_engine = tts_engine
        
        self._stop_event = threading.Event()
        self._mode = self.MODE_PASSIVE
        self._active_mode_start_time: Optional[float] = None
        
        # Wake word varyasyonları
        self._wake_variants = self._generate_wake_variants(wake_word)
    
    def _generate_wake_variants(self, wake_word: str) -> list:
        """
        Wake word için olası varyasyonları oluştur.
        Whisper bazen farklı yazabilir: "whisper", "visper", "wisper", vb.
        """
        base = wake_word.lower().strip()
        variants = [base]
        
        # Türkçe karakterli versiyonlar
        if base == "whisper":
            variants.extend([
                "visper", "wisper", "whispar", "vısper",
                "fısper", "fisper", "whisperr", "whısper",
                "wispır", "vispır", "vıspar", "wispar"
            ])
        
        # Ekstra varyasyonlar (kullanıcı farklı wake word seçerse)
        # Başında/sonunda boşluk olabilir
        variants.extend([f" {v}" for v in variants])
        variants.extend([f"{v} " for v in variants])
        
        return list(set(variants))
    
    def set_wake_word(self, wake_word: str):
        """Wake word'ü değiştir"""
        self.wake_word = wake_word.lower().strip()
        self._wake_variants = self._generate_wake_variants(wake_word)
    
    def stop(self):
        """Dinlemeyi durdur"""
        self._stop_event.set()
    
    def get_mode(self) -> str:
        """Mevcut modu döndür"""
        return self._mode
    
    def run(self):
        """Ana dinleme döngüsü"""
        if not _HAS_SD:
            self.error_occurred.emit(
                "Mikrofon modülü (sounddevice) yüklü değil. "
                "Lütfen 'pip install sounddevice' komutunu çalıştırın."
            )
            return
        
        print("[WakeWordListener] Sürekli dinleme başlatılıyor...")
        self._mode = self.MODE_PASSIVE
        self.status_changed.emit(self._mode)
        
        while not self._stop_event.is_set():
            try:
                if self._mode == self.MODE_PASSIVE:
                    self._passive_mode_iteration()
                elif self._mode == self.MODE_ACTIVE:
                    self._active_mode_iteration()
                else:
                    # Processing modunda bekle
                    time.sleep(0.1)
                    
            except Exception as e:
                error_msg = f"WakeWordListener hatası: {e}\n{traceback.format_exc()}"
                print(f"[WakeWordListener] {error_msg}")
                self.error_occurred.emit(str(e))
                time.sleep(1.0)  # Hata sonrası bekle
        
        print("[WakeWordListener] Dinleme durduruldu.")
        self._mode = self.MODE_PASSIVE
        self.status_changed.emit(self._mode)
    
    def _passive_mode_iteration(self):
        """
        Pasif mod: Kısa ses parçaları alıp wake word ara
        """
        # Kısa kayıt al
        frames = int(self.passive_chunk_duration * self.sample_rate)
        
        try:
            recording = sd.rec(
                frames,
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                device=self.device,
            )
            sd.wait()
        except Exception as e:
            print(f"[WakeWordListener] Kayıt hatası: {e}")
            time.sleep(0.5)
            return
        
        if self._stop_event.is_set():
            return
        
        audio = np.squeeze(recording)
        
        # Ses seviyesi kontrolü (çok sessizse transcribe etme)
        rms = np.sqrt(np.mean(audio**2))
        if rms < 0.01:  # Sessizlik eşiği
            return
        
        # Whisper ile transcribe
        try:
            text = self.whisper_engine.transcribe_ndarray(
                audio, sample_rate=self.sample_rate
            )
            text = (text or "").lower().strip()
            
            if text:
                print(f"[WakeWordListener] Pasif mod transcript: '{text}'")
            
            # Wake word kontrolü
            if self._contains_wake_word(text):
                print(f"[WakeWordListener] Wake word algılandı!")
                self._enter_active_mode()
                
        except Exception as e:
            print(f"[WakeWordListener] Transcribe hatası: {e}")
    
    def _contains_wake_word(self, text: str) -> bool:
        """Metinde wake word var mı?"""
        text_lower = text.lower()
        for variant in self._wake_variants:
            if variant in text_lower:
                return True
        return False
    
    def _enter_active_mode(self):
        """Aktif moda geç"""
        self._mode = self.MODE_ACTIVE
        self._active_mode_start_time = time.time()
        
        self.status_changed.emit(self._mode)
        self.wake_word_detected.emit()
        
        # TTS ile "Dinliyorum" de
        if self.tts_engine:
            self.tts_engine.speak_message('wake_detected')
        
        print(f"[WakeWordListener] AKTİF MOD ({self.active_duration}s)")
    
    def _active_mode_iteration(self):
        """
        Aktif mod: Tam komut dinle
        """
        # Timeout kontrolü
        elapsed = time.time() - self._active_mode_start_time
        if elapsed >= self.active_duration:
            print("[WakeWordListener] Aktif mod timeout")
            self._exit_active_mode(timeout=True)
            return
        
        # Komut için daha uzun kayıt al
        remaining = self.active_duration - elapsed
        duration = min(self.active_chunk_duration, remaining)
        frames = int(duration * self.sample_rate)
        
        self._mode = self.MODE_PROCESSING
        self.status_changed.emit(self._mode)
        
        try:
            print(f"[WakeWordListener] Komut dinleniyor ({duration:.1f}s)...")
            recording = sd.rec(
                frames,
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                device=self.device,
            )
            sd.wait()
        except Exception as e:
            print(f"[WakeWordListener] Kayıt hatası: {e}")
            self._mode = self.MODE_ACTIVE
            return
        
        if self._stop_event.is_set():
            return
        
        audio = np.squeeze(recording)
        
        # Whisper ile transcribe
        try:
            text = self.whisper_engine.transcribe_ndarray(
                audio, sample_rate=self.sample_rate
            )
            text = (text or "").strip()
            
            if text:
                print(f"[WakeWordListener] Aktif mod transcript: '{text}'")
                
                # Wake word'ü metinden çıkar
                clean_text = self._remove_wake_word(text)
                
                if clean_text:
                    # Komut bulundu!
                    self.command_ready.emit(clean_text)
                    self._exit_active_mode(timeout=False)
                else:
                    # Sadece wake word söylenmiş, beklemeye devam
                    self._mode = self.MODE_ACTIVE
                    self.status_changed.emit(self._mode)
            else:
                # Boş transcript
                self._mode = self.MODE_ACTIVE
                self.status_changed.emit(self._mode)
                
        except Exception as e:
            print(f"[WakeWordListener] Transcribe hatası: {e}")
            self._mode = self.MODE_ACTIVE
    
    def _remove_wake_word(self, text: str) -> str:
        """Metinden wake word'ü çıkar"""
        text_lower = text.lower()
        result = text
        
        for variant in self._wake_variants:
            if variant in text_lower:
                # Case-insensitive replace
                idx = text_lower.find(variant)
                if idx >= 0:
                    result = text[:idx] + text[idx + len(variant):]
                    text_lower = result.lower()
        
        return result.strip()
    
    def _exit_active_mode(self, timeout: bool = False):
        """Aktif moddan çık, pasif moda dön"""
        self._mode = self.MODE_PASSIVE
        self._active_mode_start_time = None
        
        self.status_changed.emit(self._mode)
        
        if timeout and self.tts_engine:
            self.tts_engine.speak_message('timeout')
        
        print("[WakeWordListener] PASİF MODA dönüldü")


class ContinuousVoiceController:
    """
    Sürekli dinleme sistemini yöneten üst seviye controller.
    MainWindow ile entegrasyon için kullanılır.
    """
    
    def __init__(
        self,
        whisper_engine,
        tts_engine=None,
        config_manager=None,
        parent=None,
    ):
        self.whisper_engine = whisper_engine
        self.tts_engine = tts_engine
        self.config = config_manager
        self.parent = parent
        
        self._listener: Optional[WakeWordListener] = None
        self._is_running = False
        
        # Callbacks
        self.on_wake_word: Optional[Callable] = None
        self.on_command: Optional[Callable[[str], None]] = None
        self.on_status_change: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
    
    def start(self):
        """Sürekli dinlemeyi başlat"""
        if self._is_running:
            return
        
        # Config'den ayarları al
        wake_word = "Whisper"
        active_duration = 15.0
        
        if self.config:
            wake_word = self.config.get('whisper.wake_word', 'Whisper')
            active_duration = self.config.get('whisper.active_mode_duration', 15)
        
        self._listener = WakeWordListener(
            whisper_engine=self.whisper_engine,
            wake_word=wake_word,
            active_duration=active_duration,
            tts_engine=self.tts_engine,
            parent=self.parent,
        )
        
        # Sinyalleri bağla
        self._listener.wake_word_detected.connect(self._on_wake_detected)
        self._listener.command_ready.connect(self._on_command_ready)
        self._listener.status_changed.connect(self._on_status_changed)
        self._listener.error_occurred.connect(self._on_error)
        
        self._listener.start()
        self._is_running = True
        print("[ContinuousVoiceController] Sürekli dinleme başlatıldı")
    
    def stop(self):
        """Sürekli dinlemeyi durdur"""
        if not self._is_running:
            return
        
        if self._listener:
            self._listener.stop()
            self._listener.wait(3000)  # 3 saniye bekle
            
            # Sinyalleri ayır
            try:
                self._listener.wake_word_detected.disconnect()
                self._listener.command_ready.disconnect()
                self._listener.status_changed.disconnect()
                self._listener.error_occurred.disconnect()
            except:
                pass
            
            self._listener = None
        
        self._is_running = False
        print("[ContinuousVoiceController] Sürekli dinleme durduruldu")
    
    def is_running(self) -> bool:
        """Dinleme aktif mi?"""
        return self._is_running
    
    def get_mode(self) -> str:
        """Mevcut modu döndür"""
        if self._listener:
            return self._listener.get_mode()
        return "stopped"
    
    def _on_wake_detected(self):
        """Wake word algılandığında"""
        if self.on_wake_word:
            self.on_wake_word()
    
    def _on_command_ready(self, command: str):
        """Komut hazır olduğunda"""
        if self.on_command:
            self.on_command(command)
    
    def _on_status_changed(self, status: str):
        """Durum değiştiğinde"""
        if self.on_status_change:
            self.on_status_change(status)
    
    def _on_error(self, message: str):
        """Hata oluştuğunda"""
        if self.on_error:
            self.on_error(message)
