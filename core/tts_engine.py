# core/tts_engine.py
"""
Text-to-Speech Engine - pyttsx3 backend
Sesli geri bildirim için kullanılır.
"""

from typing import Optional, Callable
from threading import Thread, Lock
from queue import Queue
import time

# pyttsx3 OPSİYONEL
try:
    import pyttsx3
    _HAS_TTS = True
except ImportError:
    pyttsx3 = None
    _HAS_TTS = False


class TTSEngine:
    """
    Text-to-Speech motoru.
    - Asenkron konuşma (ayrı thread)
    - Kuyruk sistemi (birden fazla mesaj)
    - Dil ve hız ayarlanabilir
    """
    
    # Önceden tanımlı mesajlar (Türkçe)
    MESSAGES = {
        'tr': {
            'listening': 'Dinliyorum',
            'processing': 'İşleniyor',
            'command_received': 'Komut alındı',
            'order_success': 'İşlem başarılı',
            'order_failed': 'İşlem başarısız',
            'not_understood': 'Anlayamadım, tekrar söyler misiniz?',
            'wake_detected': 'Evet, dinliyorum',
            'timeout': 'Zaman aşımı, bekleme moduna geçiyorum',
            'error': 'Bir hata oluştu',
            'buy': 'Alış emri verildi',
            'sell': 'Satış emri verildi',
            'position_opened': 'Pozisyon açıldı',
            'position_closed': 'Pozisyon kapatıldı',
            'invalid_amount': 'Geçersiz miktar',
            'invalid_symbol': 'Geçersiz sembol',
            'confirm_order': 'Emri onaylıyor musunuz?',
            'cancelled': 'İptal edildi',
        },
        'en': {
            'listening': 'Listening',
            'processing': 'Processing',
            'command_received': 'Command received',
            'order_success': 'Order successful',
            'order_failed': 'Order failed',
            'not_understood': 'I did not understand, could you repeat?',
            'wake_detected': 'Yes, listening',
            'timeout': 'Timeout, entering standby mode',
            'error': 'An error occurred',
            'buy': 'Buy order placed',
            'sell': 'Sell order placed',
            'position_opened': 'Position opened',
            'position_closed': 'Position closed',
            'invalid_amount': 'Invalid amount',
            'invalid_symbol': 'Invalid symbol',
            'confirm_order': 'Do you confirm the order?',
            'cancelled': 'Cancelled',
        },
        'de': {
            'listening': 'Höre zu',
            'processing': 'Verarbeitung',
            'command_received': 'Befehl empfangen',
            'order_success': 'Auftrag erfolgreich',
            'order_failed': 'Auftrag fehlgeschlagen',
            'not_understood': 'Nicht verstanden, wiederholen Sie bitte?',
            'wake_detected': 'Ja, ich höre',
            'timeout': 'Zeitüberschreitung, wechsle in Standby',
            'error': 'Ein Fehler ist aufgetreten',
            'buy': 'Kaufauftrag erteilt',
            'sell': 'Verkaufsauftrag erteilt',
            'position_opened': 'Position eröffnet',
            'position_closed': 'Position geschlossen',
            'invalid_amount': 'Ungültiger Betrag',
            'invalid_symbol': 'Ungültiges Symbol',
            'confirm_order': 'Bestätigen Sie den Auftrag?',
            'cancelled': 'Abgebrochen',
        }
    }

    def __init__(
        self,
        enabled: bool = True,
        language: str = 'tr',
        rate: int = 150,
        volume: float = 1.0,
    ):
        self.enabled = enabled
        self.language = language
        self.rate = rate
        self.volume = volume
        
        self._engine = None
        self._lock = Lock()
        self._queue: Queue = Queue()
        self._running = False
        self._worker_thread: Optional[Thread] = None
        
        if _HAS_TTS and enabled:
            self._init_engine()
            self._start_worker()
    
    def _init_engine(self):
        """pyttsx3 motorunu başlat"""
        try:
            self._engine = pyttsx3.init()
            self._engine.setProperty('rate', self.rate)
            self._engine.setProperty('volume', self.volume)
            
            # Türkçe ses varsa seç
            voices = self._engine.getProperty('voices')
            for voice in voices:
                if self.language == 'tr' and 'turkish' in voice.name.lower():
                    self._engine.setProperty('voice', voice.id)
                    break
                elif self.language == 'en' and 'english' in voice.name.lower():
                    self._engine.setProperty('voice', voice.id)
                    break
                elif self.language == 'de' and 'german' in voice.name.lower():
                    self._engine.setProperty('voice', voice.id)
                    break
            
            print(f"[TTSEngine] Motor başlatıldı (dil: {self.language})")
        except Exception as e:
            print(f"[TTSEngine] Motor başlatılamadı: {e}")
            self._engine = None
    
    def _start_worker(self):
        """Arka plan worker thread'ini başlat"""
        if self._running:
            return
        
        self._running = True
        self._worker_thread = Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
    
    def _worker_loop(self):
        """Kuyruktan mesajları alıp konuşur"""
        while self._running:
            try:
                # Kuyruktan mesaj al (1 saniye timeout)
                text = self._queue.get(timeout=1.0)
                if text is None:  # Kapatma sinyali
                    break
                
                self._speak_sync(text)
                self._queue.task_done()
            except:
                continue
    
    def _speak_sync(self, text: str):
        """Senkron konuşma (internal)"""
        if not self._engine:
            return
        
        with self._lock:
            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as e:
                print(f"[TTSEngine] Konuşma hatası: {e}")
    
    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    
    def speak(self, text: str):
        """
        Metni sesli olarak söyle (asenkron).
        Kuyruğa ekler, worker thread işler.
        """
        if not self.enabled or not _HAS_TTS:
            print(f"[TTSEngine] (disabled) {text}")
            return
        
        self._queue.put(text)
    
    def speak_message(self, message_key: str):
        """
        Önceden tanımlı bir mesajı söyle.
        Örnek: speak_message('listening') → "Dinliyorum"
        """
        messages = self.MESSAGES.get(self.language, self.MESSAGES['tr'])
        text = messages.get(message_key, message_key)
        self.speak(text)
    
    def speak_order_confirmation(self, action: str, symbol: str, amount: str):
        """
        Emir onay mesajı oluştur ve söyle.
        Örnek: "Bitcoin'den 100 dolarlık alış emri"
        """
        if self.language == 'tr':
            text = f"{symbol}'den {amount} değerinde {action} emri"
        elif self.language == 'de':
            text = f"{action} Auftrag für {amount} {symbol}"
        else:
            text = f"{action} order for {amount} of {symbol}"
        
        self.speak(text)
    
    def set_enabled(self, enabled: bool):
        """TTS'i aç/kapat"""
        self.enabled = enabled
        if enabled and not self._running and _HAS_TTS:
            if not self._engine:
                self._init_engine()
            self._start_worker()
    
    def set_language(self, language: str):
        """Dil değiştir"""
        self.language = language
        if self._engine:
            self._init_engine()  # Sesi yeniden ayarla
    
    def set_rate(self, rate: int):
        """Konuşma hızını ayarla (50-300)"""
        self.rate = max(50, min(300, rate))
        if self._engine:
            self._engine.setProperty('rate', self.rate)
    
    def set_volume(self, volume: float):
        """Ses seviyesini ayarla (0.0-1.0)"""
        self.volume = max(0.0, min(1.0, volume))
        if self._engine:
            self._engine.setProperty('volume', self.volume)
    
    def stop(self):
        """TTS motorunu durdur"""
        self._running = False
        self._queue.put(None)  # Worker'ı durdur
        
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        
        if self._engine:
            try:
                self._engine.stop()
            except:
                pass
    
    def is_available(self) -> bool:
        """TTS kullanılabilir mi?"""
        return _HAS_TTS and self._engine is not None
    
    def get_available_voices(self) -> list:
        """Mevcut sesleri listele"""
        if not self._engine:
            return []
        
        voices = self._engine.getProperty('voices')
        return [{'id': v.id, 'name': v.name, 'languages': v.languages} for v in voices]


# Singleton instance
_tts_instance: Optional[TTSEngine] = None


def get_tts_engine(
    enabled: bool = True,
    language: str = 'tr',
    rate: int = 150,
    volume: float = 1.0,
) -> TTSEngine:
    """
    TTS Engine singleton'ını döndür.
    İlk çağrıda oluşturulur, sonraki çağrılarda aynı instance döner.
    """
    global _tts_instance
    
    if _tts_instance is None:
        _tts_instance = TTSEngine(
            enabled=enabled,
            language=language,
            rate=rate,
            volume=volume,
        )
    
    return _tts_instance


def cleanup_tts():
    """TTS Engine'i temizle"""
    global _tts_instance
    if _tts_instance:
        _tts_instance.stop()
        _tts_instance = None
