"""
Report Journal — AI analist raporlarını günlük olarak kaydeder ve okur.
Öğrenme döngüsü: yeni rapor oluşturulmadan önce geçmiş raporlar okunur,
fiyat gerçekleşmeleri ile karşılaştırılır.
Token-minimal format.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

_DIR = Path(__file__).resolve().parents[2] / "data" / "ai_reports"

# Journalda tutulacak varlık kodları — sadece en önemliler
_SNAP_CODES = frozenset({
    "BTC-USD", "GC=F", "SI=F", "CL=F", "DX-Y.NYB",
    "SPY", "TLT", "HYG",
})


@dataclass
class JournalEntry:
    date: str                   # "2025-05-31"
    generated_at: str
    decision: str               # BEKLE / AÇIL / KÜÇÜLT / KAPAT
    regime: str                 # RISK_ON / DEFENSIVE / ...
    verdict: str                # tek cümle sonuç
    key_signals: list[str]      # ["BTC.D↑57%...", ...]
    snapshot: dict[str, float]  # {"BTC-USD": 87000, "GC=F": 2380}


# ---------------------------------------------------------------------------
# Kaydet
# ---------------------------------------------------------------------------

def save(
    decision: str,
    regime: str,
    verdict: str,
    key_signals: list[str],
    assets: list[dict],
) -> None:
    """Bugünün raporunu JSON'a yaz. Gün içinde tekrar çağrılırsa üzerine yazar."""
    _DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    snapshot: dict[str, float] = {}
    for a in assets:
        code = a.get("asset_code", "")
        v = a.get("value")
        if code in _SNAP_CODES and v is not None:
            try:
                snapshot[code] = round(float(v), 2)
            except (TypeError, ValueError):
                pass

    entry = {
        "date": today,
        "generated_at": datetime.now(UTC).isoformat(),
        "decision": decision,
        "regime": regime,
        "verdict": verdict,
        "key_signals": key_signals[:6],   # max 6 kaydedilir
        "snapshot": snapshot,
    }
    (_DIR / f"{today}.json").write_text(
        json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Yükle
# ---------------------------------------------------------------------------

def load_recent(n: int = 5) -> list[JournalEntry]:
    """Son n günün raporunu yükle (bugün hariç). En yeni önce."""
    if not _DIR.exists():
        return []
    today = date.today().isoformat()
    files = sorted(
        [f for f in _DIR.glob("*.json") if f.stem != today],
        reverse=True,
    )
    out: list[JournalEntry] = []
    for f in files[:n]:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            out.append(JournalEntry(
                date=d["date"],
                generated_at=d.get("generated_at", ""),
                decision=d.get("decision", ""),
                regime=d.get("regime", ""),
                verdict=d.get("verdict", ""),
                key_signals=d.get("key_signals", []),
                snapshot=d.get("snapshot", {}),
            ))
        except Exception:  # noqa: BLE001
            continue
    return out


# ---------------------------------------------------------------------------
# Öğrenme bloğu — token-minimal
# ---------------------------------------------------------------------------

def build_learning_block(
    entries: list[JournalEntry],
    current_assets: list[dict],
) -> str:
    """
    Geçmiş raporlar ile bugünkü fiyatları karşılaştıran kompakt metin.
    ~150-250 token hedef.
    """
    if not entries:
        return ""

    # Bugünkü fiyat haritası
    now_prices: dict[str, float] = {}
    for a in current_assets:
        v = a.get("value")
        code = a.get("asset_code", "")
        if v is not None:
            try:
                now_prices[code] = round(float(v), 1)
            except (TypeError, ValueError):
                pass

    lines = ["─── GEÇMİŞ RAPORLAR & GERÇEKLEŞEN ───"]
    today_dt = date.today()

    for e in entries:
        try:
            days_ago = (today_dt - date.fromisoformat(e.date)).days
        except ValueError:
            days_ago = "?"

        # Fiyat delta'ları
        deltas: list[str] = []
        for code, old_v in e.snapshot.items():
            new_v = now_prices.get(code)
            if new_v is not None and old_v > 0:
                pct = (new_v - old_v) / old_v * 100
                sign = "+" if pct >= 0 else ""
                short = code.replace("-USD", "").replace("=F", "")
                deltas.append(f"{short}:{sign}{pct:.1f}%")

        delta_str = " ".join(deltas[:5]) or "veri yok"
        sigs = " | ".join(e.key_signals[:2])

        lines.append(
            f"[{e.date} / {days_ago}g] {e.decision} · {e.regime}\n"
            f"  Öngörü: {e.verdict[:120]}\n"
            f"  Sinyal: {sigs}\n"
            f"  Gerçekleşen: {delta_str}"
        )

    lines += [
        "─────────────────────────────────────",
        "YENİ RAPORDA: Her geçmiş öngörüyü yukarıdaki Δ ile karşılaştır.",
        "Tuttu → referans ver. Yanıldı → kısa kabul et, düzelt. MAX 2 cümle/rapor.",
    ]
    return "\n".join(lines)


__all__ = [name for name in globals() if not name.startswith("_")]
