"""
Sesli komut sistemini izole test eder.
Crash noktasını tespit etmek için detaylı log verir.
"""
import sys
import traceback

print("="*50)
print("VOICE DEBUG TEST")
print("="*50)

# 1. Import testi
print("\n[1] Import testi...")
try:
    import numpy as np
    print("    numpy OK")
    import sounddevice as sd
    print("    sounddevice OK")
    from faster_whisper import WhisperModel
    print("    faster_whisper OK")
    from PyQt5.QtCore import QThread, pyqtSignal
    print("    PyQt5 OK")
    import torch
    print(f"    torch OK - CUDA: {torch.cuda.is_available()}")
except Exception as e:
    print(f"    HATA: {e}")
    traceback.print_exc()
    sys.exit(1)

# 2. Model yükleme (ana thread)
print("\n[2] Model yükleme (ana thread)...")
try:
    model = WhisperModel("tiny", device="cuda", compute_type="float32")
    print("    Model yüklendi!")
except Exception as e:
    print(f"    HATA: {e}")
    traceback.print_exc()
    sys.exit(1)

# 3. Mikrofon kayıt
print("\n[3] Mikrofon testi (3 saniye)...")
print("    Bir şey söyle!")
try:
    audio = sd.rec(int(3 * 16000), samplerate=16000, channels=1, dtype="float32")
    sd.wait()
    audio = np.squeeze(audio)
    print(f"    Kayıt OK - shape: {audio.shape}")
except Exception as e:
    print(f"    HATA: {e}")
    traceback.print_exc()
    sys.exit(1)

# 4. Transcribe (ana thread)
print("\n[4] Transcribe (ana thread)...")
try:
    segments, info = model.transcribe(audio, language="tr")
    text = " ".join([s.text for s in segments])
    print(f"    Sonuç: '{text}'")
except Exception as e:
    print(f"    HATA: {e}")
    traceback.print_exc()
    sys.exit(1)

# 5. QThread içinde transcribe
print("\n[5] QThread içinde transcribe testi...")
from PyQt5.QtWidgets import QApplication

app = QApplication([])

class TestThread(QThread):
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    
    def __init__(self, model):
        super().__init__()
        self.model = model
        
    def run(self):
        try:
            print("    [Thread] Kayıt başlıyor...")
            audio = sd.rec(int(3 * 16000), samplerate=16000, channels=1, dtype="float32")
            sd.wait()
            audio = np.squeeze(audio)
            print(f"    [Thread] Kayıt OK - shape: {audio.shape}")
            
            print("    [Thread] Transcribe başlıyor...")
            segments, info = self.model.transcribe(audio, language="tr")
            text = " ".join([s.text for s in segments])
            print(f"    [Thread] Sonuç: '{text}'")
            self.finished_signal.emit(text)
        except Exception as e:
            print(f"    [Thread] HATA: {e}")
            traceback.print_exc()
            self.error_signal.emit(str(e))

def on_finished(text):
    print(f"\n[SONUÇ] QThread transcribe başarılı: '{text}'")
    app.quit()

def on_error(error):
    print(f"\n[HATA] QThread transcribe başarısız: {error}")
    app.quit()

print("    3 saniye içinde bir şey söyle!")
thread = TestThread(model)
thread.finished_signal.connect(on_finished)
thread.error_signal.connect(on_error)
thread.start()

# 10 saniye timeout
from PyQt5.QtCore import QTimer
QTimer.singleShot(15000, lambda: (print("\n[TIMEOUT]"), app.quit()))

app.exec_()

print("\n" + "="*50)
print("TEST TAMAMLANDI")
print("="*50)