import sqlite3
from pathlib import Path

# trading.db yolu
db_path = Path(__file__).parent.parent / "data" / "database" / "trading.db"
print(f"Using DB: {db_path}")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Eski tabloyu sil
cur.execute("DROP TABLE IF EXISTS voice_commands")
conn.commit()
conn.close()

print("voice_commands tablosu silindi. Programı yeniden çalıştırdığınızda tablo yeni şemayla otomatik oluşacak.")
