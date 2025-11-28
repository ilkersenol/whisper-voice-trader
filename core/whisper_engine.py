from pathlib import Path
from typing import Optional, Tuple, List
import threading

import numpy as np


class WhisperSettings:
    """
    Ses / model ayarları.
    Preferences dialog + ConfigManager ile doldurulacak.
    """
    def __init__(
        self,
        model_size: str = "tiny",   # "tiny", "base", "small", ...
        use_gpu: bool = True,       # Kullanıcı GPU kullan seçmiş mi?
        language: str = "tr",
    ):
        self.model_size = model_size
        self.use_gpu = use_gpu
        self.language = language


class WhisperEngine:
    """
    Offline Whisper motoru (faster-whisper backend).
    - Modeli lazy-load eder (ilk kullanımda yükler, sonra cache)
    - GPU/CPU cihazını otomatik seçer
    - GPU compute type'ı karta göre otomatik belirler
    - Numpy audio buffer alıp transcript üretir
    """

    def __init__(
        self,
        settings: WhisperSettings,
        models_dir: Optional[Path] = None,
    ):
        self.settings = settings

        # Model klasörü: <project_root>/data/whisper_models
        if models_dir is not None:
            self.models_dir = Path(models_dir)
        else:
            self.models_dir = (
                Path(__file__)
                .resolve()
                .parent  # core/
                .parent  # project root
                / "data"
                / "whisper_models"
            )
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self._model_lock = threading.Lock()
        self._model = None
        self._device: Optional[str] = None
        self._compute_type: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transcribe_ndarray(self, audio: np.ndarray, sample_rate: int) -> str:
        """
        Mono float32 numpy array + sample_rate alır, transcript döndürür.
        Not: Blocking çalışır; bu yüzden genelde ayrı thread içinde çağırılmalı.
        """
        if audio is None or audio.size == 0:
            return ""

        # Stereo geldiyse mono'ya çevir
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        # float32 değilse çevir
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        model = self._get_or_load_model()

        segments, info = model.transcribe(
            audio=audio,
            language=self.settings.language,
            beam_size=5,
        )

        texts: List[str] = []
        for segment in segments:
            if segment.text:
                texts.append(segment.text.strip())

        return " ".join(texts).strip()

    def get_device_info(self) -> dict:
        """Mevcut cihaz bilgisini döndürür."""
        return {
            "device": self._device,
            "compute_type": self._compute_type,
            "model_size": self.settings.model_size,
            "gpu_enabled": self.settings.use_gpu,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_load_model(self):
        """
        Modeli ilk erişimde yükler, sonra bellekte tutar.
        """
        with self._model_lock:
            if self._model is not None:
                return self._model

            try:
                from faster_whisper import WhisperModel
            except Exception as e:
                raise RuntimeError(
                    "Whisper motoru (faster-whisper) yüklenemedi. "
                    "Lütfen 'pip install faster-whisper' komutunu çalıştırın.\n\n"
                    f"Teknik detay: {e}"
                ) from e

            device, compute_type = self._detect_device()
            self._device = device
            self._compute_type = compute_type

            print(f"[WhisperEngine] Model yükleniyor: {self.settings.model_size}")
            print(f"[WhisperEngine] Device: {device}, Compute Type: {compute_type}")

            self._model = WhisperModel(
                self.settings.model_size,
                device=device,
                compute_type=compute_type,
                download_root=str(self.models_dir),
            )
            
            print(f"[WhisperEngine] Model başarıyla yüklendi!")
            return self._model

    def _detect_device(self) -> Tuple[str, str]:
        """
        Cihaz ve compute type seçimi:
        - GPU isteniyorsa → CUDA kontrol et
        - GPU varsa → kartın float16 desteğini kontrol et
        - Destekliyorsa float16, değilse float32
        - GPU yoksa veya hata olursa → CPU + int8
        """
        if self.settings.use_gpu:
            try:
                import torch

                if torch.cuda.is_available():
                    # GPU bilgisini al
                    gpu_name = torch.cuda.get_device_name(0).lower()
                    compute_capability = torch.cuda.get_device_capability(0)
                    
                    print(f"[WhisperEngine] GPU algılandı: {gpu_name}")
                    print(f"[WhisperEngine] Compute Capability: {compute_capability}")
                    
                    # Compute Capability 7.0+ olan kartlar float16 destekler
                    # GTX 1050 = 6.1, RTX 2060+ = 7.5+, RTX 3060+ = 8.6+
                    if compute_capability[0] >= 7:
                        print("[WhisperEngine] float16 desteği var, kullanılıyor.")
                        return "cuda", "float16"
                    else:
                        print("[WhisperEngine] float16 desteği yok, float32 kullanılıyor.")
                        return "cuda", "float32"
                        
            except Exception as e:
                print(f"[WhisperEngine] GPU algılama hatası: {e}")
                print("[WhisperEngine] CPU moduna geçiliyor.")

        # Varsayılan / fallback: CPU
        return "cpu", "int8"