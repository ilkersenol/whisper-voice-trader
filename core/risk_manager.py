"""
core/risk_manager.py

Basit risk yönetim katmanı.
- Ayarlar `settings` tablosundan okunur (DatabaseManager.get_setting)
- Limitler sadece AYARLANMIŞSA uygulanır (yoksa o kural pasif kalır)
- İhlalde hem log yazar hem RiskLimitError fırlatır
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any

from utils.logger import get_logger
from database.db_manager import DatabaseManager


@dataclass
class OrderRiskContext:
    """Emir bazlı risk değerlendirme bilgileri."""
    symbol: str
    side: str
    notional_usd: float
    leverage: int
    is_paper: bool


class RiskLimitError(Exception):
    """Herhangi bir risk limiti ihlal edildiğinde atılan hata."""


class RiskManager:
    """Risk kontrollerini yöneten sınıf.

    NOT:
    - Limit değerleri DB'deki `settings` tablosundan okunur.
    - Bir ayar tanımlı değilse, o kural uygulanmaz.
      Örn: risk.max_notional_usd yoksa, max notional kontrolü yapılmaz.
    """

    def __init__(self, db_manager: DatabaseManager, logger=None) -> None:
        self.db = db_manager
        self.logger = logger or get_logger(__name__)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def check_order_risk(self, ctx: OrderRiskContext) -> None:
        """Tek bir emir için risk kontrollerini çalıştırır."""

        # 1) Maksimum notional limiti (USDT cinsinden)
        max_notional = self._get_float_setting("risk.max_notional_usd")
        if max_notional is not None and ctx.notional_usd > max_notional:
            msg = (
                f"Emir notional'ı risk limitini aşıyor: "
                f"notional={ctx.notional_usd:.2f} USDT, limit={max_notional:.2f} USDT"
            )
            self._log_risk_event(
                level="RISK",
                message="Max notional limit exceeded",
                context={
                    "symbol": ctx.symbol,
                    "side": ctx.side,
                    "notional_usd": ctx.notional_usd,
                    "limit_usd": max_notional,
                    "is_paper": ctx.is_paper,
                },
            )
            raise RiskLimitError(msg)

        # 2) Maksimum kaldıraç limiti
        max_leverage = self._get_float_setting("risk.max_leverage")
        if max_leverage is not None and ctx.leverage > max_leverage:
            msg = (
                f"Kaldıraç risk limitini aşıyor: leverage={ctx.leverage}, "
                f"limit={int(max_leverage)}"
            )
            self._log_risk_event(
                level="RISK",
                message="Max leverage limit exceeded",
                context={
                    "symbol": ctx.symbol,
                    "side": ctx.side,
                    "notional_usd": ctx.notional_usd,
                    "leverage": ctx.leverage,
                    "limit_leverage": max_leverage,
                    "is_paper": ctx.is_paper,
                },
            )
            raise RiskLimitError(msg)

        # İleride: günlük kayıp limiti, max açık pozisyon sayısı vb. buraya eklenebilir.

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_float_setting(self, key: str) -> Optional[float]:
        """Settings tablosundan float değer okur. Hatalıysa None döner."""
        try:
            value = self.db.get_setting(key)
        except Exception as e:
            self.logger.warning("Risk ayarı okunamadı (%s): %s", key, e)
            return None

        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            self.logger.warning(
                "Risk ayarı sayı formatında değil: %s = %r (yok sayılıyor)", key, value
            )
            return None

    def _log_risk_event(self, level: str, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Risk olayını hem logger'a hem de mümkünse DB'ye yazar."""
        self.logger.info("[RISK] %s - %s", level, message)

        # DB tarafı opsiyonel: system_logs tablosu varsa yaz, yoksa sessiz geç
        try:
            self.db.insert_system_log(level=level, message=message, context=context or {})
        except Exception as e:
            # system_logs tablosu yoksa veya başka bir hata varsa, sadece uyarı logla
            self.logger.warning("Risk event DB'ye yazılamadı: %s", e)
