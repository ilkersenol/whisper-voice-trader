from pathlib import Path
from typing import Optional, Tuple, List
import threading

import numpy as np
from faster_whisper import WhisperModel  # offline Whisper (zorunlu)

# Torch OPSIYONEL: sadece varsa GPU tespiti için kullanacağız
try:
    import torch  # type: ignore
    _HAS_TORCH = True
except ImportError:
    torch = None  # type: ignore
    _HAS_TORCH = False


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
    Offline Whisper (faster-whisper) motoru.
    - Modeli lazy-load eder (ilk kullanımda yükler, sonra cache)
    - GPU/CPU cihazını otomatik seçer
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
        self._model: Optional[WhisperModel] = None
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

    def _get_or_load_model(self) -> WhisperModel:
        """
        Modeli ilk erişimde yükler, sonra bellekte tutar.
        Thread-safe.
        """
        with self._model_lock:
            if self._model is not None:
                return self._model

            device, compute_type = self._detect_device()
            self._device = device
            self._compute_type = compute_type

            # faster-whisper: WhisperModel(model_size, device, compute_type, download_root)
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
        - Kullanıcı GPU istiyorsa ve torch kuruluysa → cuda/float16 (mümkünse)
        - Aksi halde → cpu/int8
        Torch yoksa veya hata verirse sessizce CPU'ya düşer.
        """
        # Kullanıcı GPU istiyor VE torch gerçekten kuruluysa dene
        if self.settings.use_gpu and _HAS_TORCH:
            try:
                if torch.cuda.is_available():  # type: ignore[attr-defined]
                    return "cuda", "float16"
            except Exception:
                # Torch bozuk veya CUDA hatalıysa CPU fallback
                pass

        # Varsayılan / fallback: CPU
        # faster-whisper dökümantasyonu CPU için genelde int8 öneriyor.
        return "cpu", "int8"
