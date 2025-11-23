# Python console'da test et:
from database.db_manager import get_db

db = get_db()

# Kayıtlı exchange'leri listele
configured = db.get_configured_exchanges()
print(f"Configured exchanges: {configured}")

# Binance keys'i yükle
keys = db.load_api_keys('binance', decrypt=True)
if keys:
    print(f"API Key: {keys['api_key'][:20]}...")
    print(f"Secret: {keys['secret_key'][:20]}...")
    print("✅ Keys saved and decrypted successfully")
else:
    print("❌ No keys found")