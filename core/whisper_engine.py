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
    - Numpy audio buffer alıp transcript üretir
    - Torch / faster-whisper import hataları uygulamayı ÇÖKERTMEZ
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_load_model(self):
        """
        Modeli ilk erişimde yükler, sonra bellekte tutar.
        Burada faster-whisper import edilir ki import hatası
        tüm uygulamayı değil sadece sesli komutu etkilesin.
        """
        with self._model_lock:
            if self._model is not None:
                return self._model

            # >>> BURADA LAZY IMPORT <<<
            try:
                from faster_whisper import WhisperModel
            except Exception as e:
                # Buradan atılan hata VoiceListener içinde yakalanacak
                raise RuntimeError(
                    "Whisper motoru (faster-whisper) yüklenemedi. "
                    "Python 3.12 ile uyumlu bir faster-whisper / ctranslate2 / "
                    "Torch kurulumu gereklidir.\n\n"
                    f"Teknik detay: {e}"
                ) from e

            device, compute_type = self._detect_device()
            self._device = device
            self._compute_type = compute_type

            self._model = WhisperModel(
                self.settings.model_size,
                device=device,
                compute_type=compute_type,
                download_root=str(self.models_dir),
            )
            return self._model

    def _detect_device(self) -> Tuple[str, str]:
        """
        Cihaz seçimi:
        - Kullanıcı GPU istiyorsa → torch import etmeyi DENE
        - Herhangi bir hata alırsak (ImportError, OSError, DLL hatası vs.)
          sessizce CPU'ya düş.
        """
        if self.settings.use_gpu:
            try:
                import torch  # type: ignore

                if torch.cuda.is_available():  # type: ignore[attr-defined]
                    return "cuda", "float16"
            except Exception:
                # Torch kurulu değil / bozuk / DLL hatası → CPU fallback
                pass

        # Varsayılan / fallback: CPU
        return "cpu", "int8"
