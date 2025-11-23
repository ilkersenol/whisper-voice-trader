"""
core/order_executor.py

OrderExecutor:
- Emir validasyonu (bakiye / kaldıraç / min-max boyut / sembol)
- Market & limit emir akışı
- Margin ve pozisyon boyutu hesaplama
- Kağıt (paper) / gerçek (real) toggle için altyapı
- DB kayıt ve durum takibi için hook noktaları

NOT:
- Gerçek exchange emir çağrıları ve kesin DB kolonları,
  ilgili modüller incelendikten sonra doldurulacak (TODO).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Literal

from utils.logger import get_logger
from utils import validators
from utils.config_manager import ConfigManager
from database.db_manager import DatabaseManager
from core.exchange_manager import get_exchange_manager, ExchangeManager


OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]
AmountType = Literal["usd", "qty"]  # usd: notional; qty: coin miktarı


class OrderValidationError(Exception):
    """Emir öncesi validasyon hataları için özel exception."""
    pass


class OrderExecutionError(Exception):
    """Emir gönderimi ya da exchange cevabı sırasında oluşan hatalar."""
    pass


class InsufficientBalanceError(OrderExecutionError):
    """Bakiye yetersiz olduğunda fırlatılır."""
    pass


@dataclass
class OrderParams:
    """
    Tek bir emir için parametreler.

    amount_type:
        - "usd": amount = USDT cinsinden notional
        - "qty": amount = coin miktarı (BTC, ETH vs.)
    """
    symbol: str
    side: OrderSide
    amount: float
    amount_type: AmountType
    leverage: int
    order_type: OrderType = "market"
    price: Optional[float] = None
    reduce_only: bool = False
    client_order_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderResult:
    """
    Emir sonucu için standart cevap.
    Exchange spesifik alanlar 'raw' içinde taşınır.
    """
    success: bool
    order_id: Optional[str] = None
    status: Optional[str] = None
    filled_qty: Optional[float] = None
    avg_price: Optional[float] = None
    error_message: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


class OrderExecutor:
    """
    Tüm emir akışının merkezi.

    Sorumluluklar:
    - Emir parametrelerini validate etmek
    - Pozisyon boyutunu ve gerekli marjı hesaplamak
    - Bakiye kontrolü yapmak
    - Paper/Real toggle'a göre ilgili engine / exchange’e yönlendirmek
    - DB kayıtları için hook sağlamak
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        config_manager: ConfigManager,
        exchange_manager: Optional[ExchangeManager] = None,
        paper_trading_engine: Any = None,
        logger=None,
    ) -> None:
        self.logger = logger or get_logger(__name__)
        self.db = db_manager
        self.config = config_manager
        self.exchange: ExchangeManager = exchange_manager or get_exchange_manager()
        self.paper_engine = paper_trading_engine

        # UI veya Preferences tarafından set edilecek flag
        self._paper_trading_enabled: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_paper_trading(self, enabled: bool) -> None:
        """
        Paper / Real toggle.

        NOT:
        - İleride buraya DB'deki settings tablosu ile sync eklenebilir.
        """
        self._paper_trading_enabled = enabled
        self.logger.info("Paper trading %s", "ON" if enabled else "OFF")

    def execute_market_order(self, params: OrderParams) -> OrderResult:
        """
        Market emirlerini çalıştırır.

        Beklenen:
        - params.order_type "market" olmalı.
        """
        if params.order_type != "market":
            raise OrderValidationError("execute_market_order sadece 'market' tipinde emirler için kullanılmalıdır.")

        return self._execute_order_internal(params)

    def execute_limit_order(self, params: OrderParams) -> OrderResult:
        """
        Limit emirlerini çalıştırır.

        Beklenen:
        - params.order_type "limit"
        - params.price dolu
        """
        if params.order_type != "limit":
            raise OrderValidationError("execute_limit_order sadece 'limit' tipinde emirler için kullanılmalıdır.")
        if params.price is None:
            raise OrderValidationError("Limit emir için price zorunludur.")

        return self._execute_order_internal(params)

    def get_order_status(self, order_id: str) -> OrderResult:
        """
        Belirli bir order_id için durum döndürür.

        NOT:
        - Burada hem DB hem de exchange tarafına bakmak gerekebilir.
        - Kesin DB kolonları ve ExchangeManager arayüzü görüldükten sonra doldurulacak.
        """
        # TODO: schema.sql ve ExchangeManager detaylarına göre implement edilecek.
        raise NotImplementedError("get_order_status henüz implement edilmedi (DB + Exchange entegrasyonu gerekli).")

    def cancel_order(self, order_id: str) -> bool:
        """
        Belirli bir emri iptal eder.

        NOT:
        - ExchangeManager'da cancel_order benzeri bir metod varsa buraya bağlanacak.
        """
        # TODO: ExchangeManager arayüzü netleştikten sonra implement edilecek.
        raise NotImplementedError("cancel_order henüz implement edilmedi (Exchange entegrasyonu gerekli).")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _execute_order_internal(self, params: OrderParams) -> OrderResult:
        """
        Ortak emir akışı:
        1. Validasyon
        2. Pozisyon boyutu & marj hesaplama
        3. Bakiye kontrolü
        4. Paper / Real karar
        5. Emir gönderimi
        6. DB kayıt
        """
        self.logger.debug("Order received: %s", params)

        try:
            valid_params = self.validate_order(params)
            qty, required_margin = self.calculate_position_size(
                amount=valid_params.amount,
                price=self._get_effective_price(valid_params),
                leverage=valid_params.leverage,
                amount_type=valid_params.amount_type,
            )

            self.check_balance(required_margin)

            if self._paper_trading_enabled and self.paper_engine is not None:
                result = self._execute_paper_order(valid_params, qty, required_margin)
            else:
                result = self._execute_real_order(valid_params, qty, required_margin)

            # DB kayıt (başarılı / başarısız her durumda loglanabilir)
            try:
                self.record_order(valid_params, result, required_margin, qty)
            except NotImplementedError:
                # Şema netleşene kadar kayıt zorunlu değil, sadece loglayalım
                self.logger.warning("record_order henüz implement edilmedi, DB kaydı atlandı.")

            return result

        except OrderValidationError as e:
            self.logger.error("Order validation error: %s", e)
            return OrderResult(success=False, error_message=str(e))
        except InsufficientBalanceError as e:
            self.logger.error("Insufficient balance: %s", e)
            return OrderResult(success=False, error_message=str(e))
        except OrderExecutionError as e:
            self.logger.error("Order execution error: %s", e)
            return OrderResult(success=False, error_message=str(e))
        except Exception as e:  # Son çare
            self.logger.exception("Unexpected error while executing order")
            return OrderResult(success=False, error_message=f"Unexpected error: {e}")

    def validate_order(self, params: OrderParams) -> OrderParams:
        """
        - Sembol formatı & geçerliliği
        - Kaldıraç aralığı
        - Miktar (pozitif, min/max vs.)
        - Fiyat validasyonu (limit emirler için)
        """
        # Symbol validation (utils.validators + ExchangeManager)
        validators.validate_symbol(params.symbol)  # utils tarafında mevcut
        if not self.exchange.validate_symbol(params.symbol):
            raise OrderValidationError(f"Geçersiz sembol: {params.symbol}")

        # Normalized symbol (örn: BTCUSDT)
        normalized_symbol = self.exchange.normalize_symbol(params.symbol)
        params.symbol = normalized_symbol

        # Leverage
        validators.validate_leverage(params.leverage)

        # Amount
        if params.amount <= 0:
            raise OrderValidationError("Amount pozitif olmalıdır.")
        validators.validate_quantity(params.amount)

        # Price (limit emirler için)
        if params.order_type == "limit":
            if params.price is None:
                raise OrderValidationError("Limit emir için price zorunludur.")
            if params.price <= 0:
                raise OrderValidationError("Price pozitif olmalıdır.")
            validators.validate_price(params.price)

        # Side
        if params.side not in ("buy", "sell"):
            raise OrderValidationError("Side sadece 'buy' veya 'sell' olabilir.")

        # Amount type
        if params.amount_type not in ("usd", "qty"):
            raise OrderValidationError("amount_type sadece 'usd' veya 'qty' olabilir.")

        return params

    def calculate_position_size(
        self,
        amount: float,
        price: float,
        leverage: int,
        amount_type: AmountType,
    ) -> tuple[float, float]:
        """
        Pozisyon boyutu ve gerekli marjı hesaplar.

        amount_type:
            - "usd": amount = notional (USDT)
            - "qty": amount = coin miktarı
        Dönen:
            (qty, required_margin)
        """
        if price <= 0:
            raise OrderValidationError("Fiyat sıfır veya negatif olamaz.")

        if amount_type == "usd":
            notional = amount
            qty = notional / price
        else:  # "qty"
            qty = amount
            notional = qty * price

        if qty <= 0 or notional <= 0:
            raise OrderValidationError("Hesaplanan miktar ya da notional geçersiz.")

        required_margin = notional / leverage
        self.logger.debug(
            "Position size calculated: qty=%s, notional=%s, required_margin=%s, leverage=%s",
            qty,
            notional,
            required_margin,
            leverage,
        )
        return qty, required_margin

    def check_balance(self, required_margin: float) -> None:
        """
        Gerekli marj için bakiye kontrolü.

        NOT:
        - ExchangeManager.get_balance() dönüş yapısı görülmeden
          burada sadece iskelet bırakıyoruz.
        - Detaylı implementasyon ExchangeManager incelendikten sonra yapılacak.
        """
        if required_margin <= 0:
            raise OrderValidationError("Gerekli marj sıfır veya negatif olamaz.")

        # TODO: ExchangeManager.get_balance() dönüş formatına göre netleştirilecek.
        # Şimdilik sadece iskelet + NotImplementedError yerine basit bir guard:
        balance_info = self.exchange.get_balance()
        # balance_info yapısını bilmediğimiz için,
        # burada sadece loglayıp gerçek kontrolü sonraya bırakıyoruz.
        self.logger.debug("Balance info (raw): %s", balance_info)

        # Bu satır, gerçek kontrol eklendiğinde kaldırılacak.
        # Şimdilik sadece fonksiyonun var olması için.
        # raise NotImplementedError("check_balance için balance yapısı net değil, sonra doldurulacak.")

    def record_order(
        self,
        params: OrderParams,
        result: OrderResult,
        required_margin: float,
        qty: float,
    ) -> None:
        """
        Emir ve sonucu orders tablosuna yazar.
        """
        try:
            order_data = {
                "exchange": self.exchange.active_exchange,
                "exchange_order_id": result.order_id,
                "symbol": params.symbol,
                "side": params.side,
                "type": params.order_type,
                "quantity": qty,
                "price": params.price,
                "stop_price": None,
                "leverage": params.leverage,
                "status": result.status or ("ERROR" if not result.success else "OK"),
                "filled_quantity": result.filled_qty,
                "average_fill_price": result.avg_price,
                "commission": None,
                "commission_asset": None,
                "position_id": None,
                "is_paper_trade": 1 if self._paper_trading_enabled else 0,
                "voice_command": params.extra.get("voice_command"),
            }

            order_id = self.db.insert_order(order_data)

            # Sistem loguna da yazalım
            self.db.insert_system_log(
                level="INFO" if result.success else "ERROR",
                message=f"Order recorded (order_id={order_id})",
                context={
                    "symbol": params.symbol,
                    "side": params.side,
                    "qty": qty,
                    "price": params.price,
                    "result": result.raw,
                }
            )

            return order_id

        except Exception as e:
            self.db.insert_system_log(
                level="ERROR",
                message="record_order failed",
                context={"error": str(e)}
            )
            raise


    def _execute_paper_order(
        self,
        params: OrderParams,
        qty: float,
        required_margin: float,
    ) -> OrderResult:
        """
        PaperTradingEngine üzerinden emir çalıştırma.

        NOT:
        - PaperTradingEngine arayüzü henüz yazılmadığı için burada da iskelet var.
        """
        if self.paper_engine is None:
            raise OrderExecutionError("Paper trading aktif ama paper_engine set edilmemiş.")

        # TODO: core/paper_trading_engine.py tasarımı tamamlanınca doldurulacak.
        raise NotImplementedError("_execute_paper_order, PaperTradingEngine hazır olduğunda implement edilecek.")

    def _execute_real_order(
        self,
        params: OrderParams,
        qty: float,
        required_margin: float,
    ) -> OrderResult:
        """
        Gerçek exchange (CCXT / ExchangeManager) üzerinden emir çalıştırma.

        NOT:
        - ExchangeManager'a 'create_order' benzeri bir giriş noktası
          eklendikten sonra burası doldurulacak.
        """
        # TODO: core/exchange_manager.py arayüzü genişletilip
        # CCXT order creation netleştiğinde implement edilecek.
        raise NotImplementedError("_execute_real_order, ExchangeManager order arayüzü netleşince implement edilecek.")

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------

    def _get_effective_price(self, params: OrderParams) -> float:
        """
        Margin hesabı için kullanılacak efektif fiyat:

        - Market emir → exchange.get_ticker() fiyatı
        - Limit emir → params.price
        """
        if params.order_type == "limit":
            if params.price is None:
                raise OrderValidationError("Limit emir için fiyat gerekli.")
            return params.price

        # Market emir → ticker
        ticker = self.exchange.get_ticker(params.symbol)
        # ticker yapısını bilmediğimiz için burada da genel bir yaklaşım:
        if isinstance(ticker, dict):
            # Binance/CCXT tarzı 'last' ya da 'price' field'larını dene
            price = ticker.get("last") or ticker.get("price") or ticker.get("close")
        else:
            price = None

        if not price or price <= 0:
            raise OrderExecutionError(f"Sembol için geçerli fiyat alınamadı: {params.symbol} (ticker={ticker})")

        return float(price)
