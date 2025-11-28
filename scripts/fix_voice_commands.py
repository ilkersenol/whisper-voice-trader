import sqlite3
from pathlib import Path

db_path = Path('E:/VSCODE/WhisperVoiceTrader/data/database/trading.db')
db_path.parent.mkdir(parents=True, exist_ok=True)

# Eski dosyayı sil
if db_path.exists():
    db_path.unlink()
    print("Eski veritabani silindi.")

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# voice_commands tablosu (main.py'nin beklediği yapıda)
cursor.execute('''
CREATE TABLE IF NOT EXISTS voice_commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    phrase TEXT NOT NULL,
    language TEXT DEFAULT 'tr',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Varsayılan komutları ekle
default_commands = [
    ('BUY', 'al', 'tr'),
    ('BUY', 'satin al', 'tr'),
    ('BUY', 'long', 'tr'),
    ('SELL', 'sat', 'tr'),
    ('SELL', 'short', 'tr'),
    ('STOP', 'durdur', 'tr'),
    ('STOP', 'iptal', 'tr'),
]

cursor.executemany('INSERT OR IGNORE INTO voice_commands (category, phrase, language) VALUES (?, ?, ?)', default_commands)

conn.commit()
conn.close()

print('voice_commands tablosu olusturuldu!')
print('Varsayilan komutlar eklendi!')
print('Simdi ana uygulamayi calistirabilirsiniz.')