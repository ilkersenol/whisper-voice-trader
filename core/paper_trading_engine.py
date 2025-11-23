"""
core/paper_trading_engine.py

Gerçek emir göndermeden, borsa davranışını taklit eden basit kağıt (paper) trade motoru.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from utils.logger import get_logger


class PaperTradingEngine:
    """
    Çok basit bir paper trading motoru.

    - Gerçek borsaya emir göndermez.
    - Emirleri anında tamamen dolmuş kabul eder (market/limit fark etmiyor).
    - Şimdilik internal pozisyon/bakiye takibi yapmıyor, sadece OrderResult üretmek için
      ccxt benzeri bir order dict'i döndürüyor.
    """

    def __init__(self, logger=None) -> None:
        self.logger = logger or get_logger(__name__)
        self._order_counter: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute_order(self, params: Any, qty: float, price: float) -> Dict[str, Any]:
        """
        Paper emir oluşturur ve ccxt create_order çıktısına benzeyen bir dict döndürür.

        Args:
            params: OrderExecutor.OrderParams örneği (symbol, side, order_type, price vs. içerir)
            qty: Emir miktarı
            price: İşlem fiyatı (market için son fiyat, limit için limit fiyat)

        Returns:
            dict: ccxt order formatına yakın bir sözlük
        """
        self._order_counter += 1
        order_id = f"paper-{self._order_counter}"

        symbol = getattr(params, "symbol", None)
        side = getattr(params, "side", None)
        order_type = getattr(params, "order_type", None)

        notional = qty * price

        order = {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "status": "closed",
            "amount": qty,
            "filled": qty,
            "price": price,
            "average": price,
            "cost": notional,
            "timestamp": int(time.time() * 1000),
            "info": {
                "mode": "paper",
            },
        }

        self.logger.info(
            "Paper order created: id=%s side=%s qty=%s symbol=%s price=%s cost=%s",
            order_id,
            side,
            qty,
            symbol,
            price,
            notional,
        )

        return order
