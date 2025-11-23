# 🎤 Whisper Voice Trader

Offline Whisper ses tanıma ile kontrol edilen profesyonel cryptocurrency futures trading botu.

## Özellikler

- 🎙️ Offline Whisper ses tanıma (wake word: "Whisper")
- 📊 Multi-exchange destekli (Binance, ByBit, KuCoin, MEXC, OKX)
- 🔒 AES-256 API key encryption
- 📈 Real-time market data (WebSocket)
- 💼 Paper trading simülasyonu
- 🌐 Çoklu dil desteği (TR/EN/DE)
- 🎨 Modern dark theme UI

## Kurulum

```bash
# Virtual environment oluştur
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Bağımlılıkları kur
pip install -r requirements.txt

# UI dosyalarını compile et
python scripts/compile_ui.py

# Database'i initialize et
python -c "from database.db_manager import get_db; get_db().initialize()"

# Uygulamayı çalıştır
python main.py
```

## Teknolojiler

- **UI:** PyQt5
- **Ses Tanıma:** OpenAI Whisper
- **Exchange API:** CCXT
- **Database:** SQLite
- **Encryption:** AES-256

## Geliştirme Durumu

✅ Gün 1: Project Setup & UI Compilation - TAMAMLANDI

## Lisans

Creagent Professional Trading Bot - v1.0.0
