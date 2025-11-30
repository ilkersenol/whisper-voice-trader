# core/command_parser.py
"""
Command Parser - Doğal Dil → Trading Komutları
"Al BTC 100 dolar" → OrderParams(side=BUY, symbol=BTCUSDT, amount=100)
"""

import re
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"


@dataclass
class ParsedCommand:
    """Ayrıştırılmış komut"""
    action: str                    # "buy", "sell", "close", "cancel", "status", "balance"
    side: Optional[OrderSide] = None
    symbol: Optional[str] = None   # "BTCUSDT", "ETHUSDT", vb.
    amount: Optional[float] = None # USD cinsinden miktar
    leverage: Optional[int] = None
    order_type: OrderType = OrderType.MARKET
    price: Optional[float] = None  # Limit order için
    raw_text: str = ""             # Orijinal metin
    confidence: float = 1.0        # Ayrıştırma güvenilirliği (0-1)
    

class CommandParser:
    """
    Türkçe/İngilizce sesli komutları trading parametrelerine çevirir.
    
    Desteklenen Komutlar:
    - "Al BTC 100 dolar" → BUY BTCUSDT 100 USD
    - "Sat ETH 50 dolar" → SELL ETHUSDT 50 USD
    - "Bitcoin al 200 dolar" → BUY BTCUSDT 200 USD
    - "Pozisyonu kapat" → CLOSE position
    - "Emri iptal et" → CANCEL order
    - "Bakiye" → Show balance
    - "Durum" → Show status
    """
    
    # Kripto para isimleri → Sembol eşleştirme
    CRYPTO_ALIASES = {
        # Bitcoin
        'bitcoin': 'BTCUSDT',
        'btc': 'BTCUSDT',
        'bitkoyn': 'BTCUSDT',
        'bit': 'BTCUSDT',
        
        # Ethereum
        'ethereum': 'ETHUSDT',
        'eth': 'ETHUSDT',
        'eter': 'ETHUSDT',
        'eterium': 'ETHUSDT',
        
        # Binance Coin
        'bnb': 'BNBUSDT',
        'binance': 'BNBUSDT',
        
        # Solana
        'solana': 'SOLUSDT',
        'sol': 'SOLUSDT',
        
        # XRP
        'xrp': 'XRPUSDT',
        'ripple': 'XRPUSDT',
        
        # Dogecoin
        'doge': 'DOGEUSDT',
        'dogecoin': 'DOGEUSDT',
        'doj': 'DOGEUSDT',
        
        # Cardano
        'ada': 'ADAUSDT',
        'cardano': 'ADAUSDT',
        
        # Polkadot
        'dot': 'DOTUSDT',
        'polkadot': 'DOTUSDT',
        
        # Avalanche
        'avax': 'AVAXUSDT',
        'avalanche': 'AVAXUSDT',
        
        # Chainlink
        'link': 'LINKUSDT',
        'chainlink': 'LINKUSDT',
        
        # Litecoin
        'ltc': 'LTCUSDT',
        'litecoin': 'LTCUSDT',
        
        # Polygon
        'matic': 'MATICUSDT',
        'polygon': 'MATICUSDT',
    }
    
    # Aksiyon kelimeleri (Türkçe + İngilizce)
    BUY_KEYWORDS = [
        'al', 'satın al', 'satınal', 'buy', 'long', 'uzun',
        'aç', 'pozisyon aç', 'gir', 'alım', 'alalım'
    ]
    
    SELL_KEYWORDS = [
        'sat', 'sell', 'short', 'kısa', 'açığa sat',
        'satış', 'satalım'
    ]
    
    CLOSE_KEYWORDS = [
        'kapat', 'pozisyon kapat', 'close', 'çık', 'çıkış',
        'pozisyonu kapat', 'kapatalım', 'kapat pozisyonu'
    ]
    
    CANCEL_KEYWORDS = [
        'iptal', 'iptal et', 'cancel', 'vazgeç', 'sil',
        'emri iptal', 'emri iptal et', 'order iptal'
    ]
    
    STATUS_KEYWORDS = [
        'durum', 'status', 'pozisyon', 'pozisyonlar',
        'açık pozisyon', 'ne var', 'göster'
    ]
    
    BALANCE_KEYWORDS = [
        'bakiye', 'balance', 'para', 'hesap', 'cüzdan',
        'ne kadar', 'sermaye'
    ]
    
    # Miktar kalıpları
    AMOUNT_PATTERNS = [
        r'(\d+(?:[.,]\d+)?)\s*(?:dolar|dollar|\$|usd|usdt)',
        r'(\d+(?:[.,]\d+)?)\s*(?:tl|lira|türk lirası)',
        r'(\d+(?:[.,]\d+)?)\s*(?:euro|€|eur)',
        r'(\d+)\s*(?:k|bin)',  # "5k" veya "5 bin"
        r'(\d+(?:[.,]\d+)?)',  # Sadece sayı
    ]
    
    # Türkçe sayı kelimeleri
    NUMBER_WORDS = {
        'bir': 1, 'iki': 2, 'üç': 3, 'dört': 4, 'beş': 5,
        'altı': 6, 'yedi': 7, 'sekiz': 8, 'dokuz': 9, 'on': 10,
        'yirmi': 20, 'otuz': 30, 'kırk': 40, 'elli': 50,
        'altmış': 60, 'yetmiş': 70, 'seksen': 80, 'doksan': 90,
        'yüz': 100, 'bin': 1000,
    }
    
    def __init__(self, default_symbol: str = "BTCUSDT"):
        self.default_symbol = default_symbol
    
    def parse(self, text: str) -> Optional[ParsedCommand]:
        """
        Metni ayrıştır ve ParsedCommand döndür.
        Tanınamayan komutlar için None döner.
        """
        if not text:
            return None
        
        # Metni normalize et
        text = self._normalize_text(text)
        original_text = text
        
        # Aksiyonu belirle
        action = self._detect_action(text)
        if not action:
            return None
        
        # Temel komut oluştur
        cmd = ParsedCommand(
            action=action,
            raw_text=original_text,
        )
        
        # Aksiyon tipine göre ek bilgileri çıkar
        if action in ("buy", "sell"):
            cmd.side = OrderSide.BUY if action == "buy" else OrderSide.SELL
            cmd.symbol = self._extract_symbol(text)
            cmd.amount = self._extract_amount(text)
            
            # Sembol bulunamadıysa varsayılanı kullan
            if not cmd.symbol:
                cmd.symbol = self.default_symbol
                cmd.confidence *= 0.8
            
            # Miktar bulunamadıysa güvenilirliği düşür
            if not cmd.amount:
                cmd.confidence *= 0.5
        
        elif action == "close":
            cmd.symbol = self._extract_symbol(text)
        
        return cmd
    
    def _normalize_text(self, text: str) -> str:
        """Metni normalize et"""
        text = text.lower().strip()
        
        # Türkçe karakterleri koru ama bazı varyasyonları düzelt
        replacements = {
            '\u0131': 'i',  # ı → i (bazı durumlarda karışabilir)
            '\u2018': "'",  # ' → '
            '\u2019': "'",  # ' → '
            '\u201c': '"',  # " → "
            '\u201d': '"',  # " → "
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Fazla boşlukları temizle
        text = ' '.join(text.split())
        
        return text
    
    def _detect_action(self, text: str) -> Optional[str]:
        """Aksiyon türünü belirle"""
        text_lower = text.lower()
        
        # Öncelik sırasına göre kontrol et
        for keyword in self.CLOSE_KEYWORDS:
            if keyword in text_lower:
                return "close"
        
        for keyword in self.CANCEL_KEYWORDS:
            if keyword in text_lower:
                return "cancel"
        
        for keyword in self.BUY_KEYWORDS:
            if keyword in text_lower:
                return "buy"
        
        for keyword in self.SELL_KEYWORDS:
            if keyword in text_lower:
                return "sell"
        
        for keyword in self.STATUS_KEYWORDS:
            if keyword in text_lower:
                return "status"
        
        for keyword in self.BALANCE_KEYWORDS:
            if keyword in text_lower:
                return "balance"
        
        return None
    
    def _extract_symbol(self, text: str) -> Optional[str]:
        """Kripto sembolünü çıkar"""
        text_lower = text.lower()
        
        # Önce tam eşleşme ara
        for alias, symbol in self.CRYPTO_ALIASES.items():
            # Kelime sınırlarını kontrol et
            pattern = r'\b' + re.escape(alias) + r'\b'
            if re.search(pattern, text_lower):
                return symbol
        
        # Bulunamadıysa None döndür
        return None
    
    def _extract_amount(self, text: str) -> Optional[float]:
        """Miktar bilgisini çıkar"""
        text_lower = text.lower()
        
        # Önce yazılı sayıları çevir
        text_converted = self._convert_word_numbers(text_lower)
        
        # Miktar kalıplarını dene
        for pattern in self.AMOUNT_PATTERNS:
            match = re.search(pattern, text_converted)
            if match:
                amount_str = match.group(1)
                # Virgülü noktaya çevir
                amount_str = amount_str.replace(',', '.')
                try:
                    amount = float(amount_str)
                    
                    # "k" veya "bin" için çarp
                    if 'k' in text_lower or 'bin' in text_lower:
                        # Eğer sayı zaten 1000+ değilse
                        if amount < 1000:
                            amount *= 1000
                    
                    return amount
                except ValueError:
                    continue
        
        return None
    
    def _convert_word_numbers(self, text: str) -> str:
        """Yazılı sayıları rakama çevir"""
        result = text
        
        # Basit tek kelime sayıları
        for word, num in self.NUMBER_WORDS.items():
            result = re.sub(r'\b' + word + r'\b', str(num), result)
        
        # Bileşik sayılar (örn: "yüz elli" → "150")
        # Bu daha karmaşık, basit versiyonu kullan
        
        return result
    
    def format_command_summary(self, cmd: ParsedCommand) -> str:
        """Komut özetini insan okunabilir formatta döndür"""
        if cmd.action == "buy":
            return f"📈 ALIŞ: {cmd.symbol} - {cmd.amount or '?'} USD"
        elif cmd.action == "sell":
            return f"📉 SATIŞ: {cmd.symbol} - {cmd.amount or '?'} USD"
        elif cmd.action == "close":
            symbol_str = cmd.symbol or "tüm pozisyonlar"
            return f"🔒 KAPAT: {symbol_str}"
        elif cmd.action == "cancel":
            return "❌ EMİR İPTAL"
        elif cmd.action == "status":
            return "📊 DURUM SORGULA"
        elif cmd.action == "balance":
            return "💰 BAKİYE SORGULA"
        else:
            return f"❓ Bilinmeyen komut: {cmd.action}"


class CommandValidator:
    """Komut doğrulama"""
    
    MIN_AMOUNT = 1.0        # Minimum işlem tutarı (USD)
    MAX_AMOUNT = 100000.0   # Maksimum işlem tutarı (USD)
    
    VALID_SYMBOLS = [
        'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
        'DOGEUSDT', 'ADAUSDT', 'DOTUSDT', 'AVAXUSDT', 'LINKUSDT',
        'LTCUSDT', 'MATICUSDT',
    ]
    
    @classmethod
    def validate(cls, cmd: ParsedCommand) -> Tuple[bool, List[str]]:
        """
        Komutu doğrula.
        Returns: (is_valid, error_messages)
        """
        errors = []
        
        if not cmd:
            return False, ["Komut ayrıştırılamadı"]
        
        # Alış/Satış için doğrulama
        if cmd.action in ("buy", "sell"):
            # Sembol kontrolü
            if cmd.symbol and cmd.symbol not in cls.VALID_SYMBOLS:
                errors.append(f"Geçersiz sembol: {cmd.symbol}")
            
            # Miktar kontrolü
            if cmd.amount is not None:
                if cmd.amount < cls.MIN_AMOUNT:
                    errors.append(f"Miktar çok düşük: {cmd.amount} USD (min: {cls.MIN_AMOUNT})")
                elif cmd.amount > cls.MAX_AMOUNT:
                    errors.append(f"Miktar çok yüksek: {cmd.amount} USD (max: {cls.MAX_AMOUNT})")
            else:
                errors.append("Miktar belirtilmedi")
        
        # Güvenilirlik kontrolü
        if cmd.confidence < 0.5:
            errors.append("Komut belirsiz, lütfen tekrar deneyin")
        
        return len(errors) == 0, errors


# Test için örnek kullanım
if __name__ == "__main__":
    parser = CommandParser()
    
    test_commands = [
        "Al BTC 100 dolar",
        "Bitcoin sat 50 dolar",
        "Ethereum al 200 USD",
        "Sat ETH 75 dolar",
        "Pozisyonu kapat",
        "Bakiye ne kadar",
        "Durum göster",
        "Al 500 dolar",  # Sembol yok
        "Bitcoin al",    # Miktar yok
    ]
    
    print("=" * 60)
    print("Command Parser Test")
    print("=" * 60)
    
    for text in test_commands:
        print(f"\nGiriş: \"{text}\"")
        cmd = parser.parse(text)
        
        if cmd:
            print(f"  Aksiyon: {cmd.action}")
            print(f"  Sembol: {cmd.symbol}")
            print(f"  Miktar: {cmd.amount}")
            print(f"  Güven: {cmd.confidence:.0%}")
            print(f"  Özet: {parser.format_command_summary(cmd)}")
            
            # Doğrulama
            is_valid, errors = CommandValidator.validate(cmd)
            if not is_valid:
                print(f"  ⚠️ Hatalar: {', '.join(errors)}")
        else:
            print("  ❌ Komut tanınamadı")
