# Whisper Voice Trader – Geliştirme Notları

## 1. Şu anki durum
- Git + GitHub + VPS senkronizasyonu kuruldu.
- OrderExecutor'ın çekirdek emir motoru tamamlandı.
- Paper Trading Engine eklendi ve OrderExecutor ile entegre edildi.
- RiskManager eklendi ve OrderExecutor'a bağlandı (max_notional_usd & max_leverage çalışır durumda).
- DB helper fonksiyonları (orders, trade_history, system_logs) hazır.
- ExchangeManager.create_order + gerçek emir akışı tamamlandı.

## 2. Bu oturumda tamamlananlar
- Paper trading entegrasyonu tamamlandı.
- RiskManager modülü oluşturuldu.
- Risk limitleri (max_notional_usd, max_leverage) OrderExecutor akışına dahil edildi.
- _execute_order_internal() risk + balance + paper/real akışı ile güncellendi.

## 3. Bir sonraki yapılacaklar
1) UI tarafında Paper/Real Trading toggle eklenmesi.
2) UI → OrderExecutor bağlanması (Buy/Sell click handler → OrderParams).
3) UI risk ayarları ekranı (risk.max_notional_usd / risk.max_leverage).
4) Pozisyon yönetimi altyapısının başlatılması (PositionManager).
5) Emir geçmişi & trade geçmişi UI entegrasyonu.
