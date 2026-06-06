# LEGACY — Snapshot-Replay Diagnostics

Bu klasördeki `snapshot_replay_source_*` dosyaları (50+ adet) eski mimari
"A sistemi"nin diagnostic katmanına aittir ve **canlı karar yolunda kullanılmamaktadır.**

## Canlı ürün (Sistem B)

```
real_market_provider.py   ← yfinance + CoinGecko + FRED + Stooq
   ↓
regime_report_service.py  ← 4 katmanlı makro rejim analizi
consensus_engine.py       ← Multi-TF consensus skorlaması
   ↓
paper_trading_service.py  ← SL/TP + Manuel Kapat + Öğrenme motoru
learning_engine.py        ← Fingerprint tabanlı WIN/LOSS öğrenmesi
auto_weight_trainer.py    ← Her 5 kapanışta ağırlık kalibrasyonu
```

## Bu dosyalar ne yapıyor?

`snapshot_replay_source_*` → Snapshot'ların kaynak kalitesini
field seviyesinde denetliyor (naming, contract, drift, timing).
Gerçek bir piyasa kararı üretmiyor.

## Sonraki adım

Bu dosyalar `backend/legacy/` klasörüne taşınacak.
Önce snapshot_replay API'nin frontend kullanımı doğrulanmalı.

**Son güncelleme: Haziran 2026**
