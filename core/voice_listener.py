# core/voice_listener.py

from typing import Optional
import threading

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

# sounddevice OPSİYONEL, ama bu dosya için gerekli
try:
    import sounddevice as sd  # type: ignore
    _HAS_SD = True
except ImportError:
    sd = None  # type: ignore
    _HAS_SD = False


class VoiceListener(QThread):
    """
    Basit 'konuş ve bekle' tipi dinleyici.
    - duration saniye mikrofon kaydı alır
    - WhisperEngine ile transcript üretir
    - transcript_ready sinyalini yayar
    """

    transcript_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    status_changed = pyqtSignal(str)  # "idle" | "listening" | "transcribing"

    def __init__(
        self,
        whisper_engine,
        duration: float = 5.0,
        sample_rate: int = 16_000,
        device: Optional[int] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.whisper_engine = whisper_engine
        self.duration = duration
        self.sample_rate = sample_rate
        self.device = device
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        if not _HAS_SD:
            self.error_occurred.emit(
                "Mikrofon modülü (sounddevice) yüklü değil. Lütfen 'pip install sounddevice' komutunu çalıştırın."
            )
            return

        try:
            self.status_changed.emit("listening")

            frames = int(self.duration * self.sample_rate)

            recording = sd.rec(
                frames,
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                device=self.device,
            )
            sd.wait()  # bu thread içinde bloklanması sorun değil

            if self._stop_event.is_set():
                self.status_changed.emit("idle")
                return

            audio = np.squeeze(recording)

            self.status_changed.emit("transcribing")

            text = self.whisper_engine.transcribe_ndarray(
                audio, sample_rate=self.sample_rate
            )

            if self._stop_event.is_set():
                self.status_changed.emit("idle")
                return

            self.transcript_ready.emit(text or "")
            self.status_changed.emit("idle")

        except Exception as e:
            self.status_changed.emit("idle")
            self.error_occurred.emit(str(e))
