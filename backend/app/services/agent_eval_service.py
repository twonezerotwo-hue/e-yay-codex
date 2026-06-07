"""
Agent Eval Harness — Sprint 4 / Item 4 (puan 95).

"Agent geçmişte ne kadar doğru tahmin etti?" sorusunun cevaplanabilmesi için
audit log'tan geriye dönük puanlama yapar.

Ölçüler:
  • direction_accuracy: bullish → fiyat yükseldi mi? bearish → düştü mü?
  • confidence_calibration: HIGH band kararlar gerçekten daha doğru mu?
  • abstention_quality: abstain edilen anlarda agent agresif olsa hata yapar mıydı?
  • brier_like: olasılık tahmini ile gerçek sonucun karesel hatası

Kayıt kaynakları:
  • Audit log (in-memory ring + JSONL append) — agent kararları
  • Core snapshot cache — karar anındaki kanıtlar
  • RealMarketProvider — şimdiki fiyatlar (gerçek sonuç)

Eval sonuçları kalıcı bir JSONL dosyaya yazılır: data/agent_evals.jsonl

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import json
import threading
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.services import agent_audit_log, core_snapshot_cache

_EVAL_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "agent_evals.jsonl"
_RING: deque[dict[str, Any]] = deque(maxlen=500)
_LOCK = threading.Lock()


@dataclass
class EvalResult:
    eval_id: str
    audit_id: int | None
    snapshot_id: str | None
    endpoint: str
    evaluated_at: str
    decision: str | None
    confidence_band: str | None
    confidence_pct: float | None
    abstained: bool
    # Karar anı → şimdi karşılaştırması
    horizon_hours: float | None
    direction_correct: bool | None
    realized_delta_pct: float | None
    # Skor
    score: float | None              # -1.0 .. +1.0
    brier_like: float | None         # 0.0 (mükemmel) .. 1.0 (en kötü)
    calibration_bucket: str | None   # HIGH/MODERATE/LOW
    reasons: list[str] = field(default_factory=list)


# ────────────────────────────────────────────────────────────────────────────
# Karar yorumlayıcı
# ────────────────────────────────────────────────────────────────────────────

def _decision_to_direction(decision: str | None) -> int | None:
    """Decision metnini -1 / 0 / +1 yön skoruna çevir.

    bullish/long/risk-on/buy → +1
    bearish/short/risk-off/sell → -1
    neutral/hold/abstain → 0
    """
    if not decision:
        return None
    d = str(decision).lower()
    if any(k in d for k in ("bullish", "risk-on", "risk_on", "long", "buy", "alış", "yükseliş")):
        return +1
    if any(k in d for k in ("bearish", "risk-off", "risk_off", "short", "sell", "satış", "düşüş")):
        return -1
    if any(k in d for k in ("neutral", "hold", "wait", "izle", "nötr")):
        return 0
    return None


def _direction_from_realized(delta_pct: float | None, threshold_pct: float = 0.3) -> int | None:
    """Gerçekleşen fiyat değişimi → yön. ±threshold içi → 0 (yatay)."""
    if delta_pct is None:
        return None
    if delta_pct > threshold_pct:
        return +1
    if delta_pct < -threshold_pct:
        return -1
    return 0


# ────────────────────────────────────────────────────────────────────────────
# Gerçekleşmiş fiyat al
# ────────────────────────────────────────────────────────────────────────────

def _get_now_prices() -> dict[str, float]:
    """Şimdiki fiyatları RealMarketProvider üzerinden topla. Hata olursa boş döner."""
    try:
        from app.providers.real_market_provider import RealMarketProvider
        rp = RealMarketProvider()
        out: dict[str, float] = {}
        for snap in rp.fetch_market_snapshots():
            sym = getattr(snap, "asset_symbol", None) or getattr(snap, "symbol", None)
            val = getattr(snap, "value", None) or getattr(snap, "price", None)
            if sym and val is not None:
                try:
                    out[str(sym)] = float(val)
                except Exception:
                    continue
        return out
    except Exception:
        return {}


def _snapshot_anchor_prices(snapshot: dict[str, Any] | None) -> dict[str, float]:
    """Snapshot evidence'tan o anki fiyatları çıkar — best-effort."""
    if not snapshot:
        return {}
    ev = snapshot.get("evidence") or {}
    out: dict[str, float] = {}
    # Symbol listesi varsa, fiyatı yoksa hayır — kanıt değeri zaten anchor sayılır
    # En çok kullandığımız format: {"snapshots": ["BTC", "XAU", "GLD"]}
    # Bu tek başına fiyat vermez. Bu nedenle "evidence.prices" ararız.
    p = ev.get("prices")
    if isinstance(p, dict):
        for k, v in p.items():
            try:
                out[str(k)] = float(v)
            except Exception:
                continue
    return out


# ────────────────────────────────────────────────────────────────────────────
# Puanlama
# ────────────────────────────────────────────────────────────────────────────

def _avg_delta_pct(anchor: dict[str, float], now: dict[str, float]) -> float | None:
    """Anchor → şimdi ortalama % değişim. Hiç ortak sembol yoksa None."""
    common = [s for s in anchor if s in now]
    if not common:
        return None
    deltas = []
    for s in common:
        a = anchor[s]
        n = now[s]
        if a is None or n is None or a == 0:
            continue
        deltas.append(((n - a) / a) * 100.0)
    if not deltas:
        return None
    return sum(deltas) / len(deltas)


def _brier_like(predicted_dir: int | None, realized_dir: int | None) -> float | None:
    """Predicted ve realized -1/0/+1 → [0,1] arası karesel hata.

    Mükemmel uyum 0, ters uyum 1.0.
    """
    if predicted_dir is None or realized_dir is None:
        return None
    # -1,0,+1 değerlerini [0,0.5,1] olasılıklarına eşle
    def _p(x: int) -> float:
        return {-1: 0.0, 0: 0.5, 1: 1.0}[x]
    return (_p(predicted_dir) - _p(realized_dir)) ** 2


def _audit_to_decision(audit_entry: dict[str, Any]) -> str | None:
    """Audit output_hash'i ham karar metnini içermiyor; output_payload da hash'lenmiş.

    Audit zamanında output_payload'a 'decision' ya da 'status' veriliyor — onu kullanırız.
    Eski formatla uyum için extra alanını da tararız.
    """
    out = audit_entry.get("output_payload") or audit_entry.get("extra", {}).get("output_payload")
    if isinstance(out, dict):
        d = out.get("decision") or out.get("status")
        if d:
            return str(d)
    return None


def evaluate_audit_entry(
    audit: dict[str, Any],
    *,
    now_prices: dict[str, float] | None = None,
    min_horizon_minutes: float = 5.0,
) -> EvalResult | None:
    """Tek bir audit kaydını puanla. Çok yeni karar veya kanıt eksikse None."""
    snapshot_id = audit.get("snapshot_id")
    endpoint = audit.get("endpoint", "?")
    audit_id = audit.get("id")
    conf = audit.get("confidence") or {}
    abstained = bool(conf.get("abstain"))
    decision_text = _audit_to_decision(audit) or audit.get("decision")
    confidence_band = conf.get("confidence_band") or conf.get("band")
    confidence_pct = conf.get("confidence_pct")

    # Zaman aralığı yeterli mi?
    try:
        ts = datetime.fromisoformat(audit["timestamp"].replace("Z", "+00:00"))
    except Exception:
        return None
    now = datetime.now(UTC)
    age_minutes = (now - ts).total_seconds() / 60.0
    if age_minutes < min_horizon_minutes:
        return None  # Henüz çok erken, eval anlamsız

    # Anchor fiyat ve şimdiki fiyat
    snap = core_snapshot_cache.get_snapshot(snapshot_id) if snapshot_id else None
    anchor = _snapshot_anchor_prices(snap)
    now_p = now_prices if now_prices is not None else _get_now_prices()
    realized_delta = _avg_delta_pct(anchor, now_p)

    predicted_dir = _decision_to_direction(decision_text)
    realized_dir = _direction_from_realized(realized_delta)

    reasons: list[str] = []
    direction_correct: bool | None = None
    score: float | None = None
    brier = _brier_like(predicted_dir, realized_dir)

    if abstained:
        # Agent karar vermedi → "abstention quality" kavramı:
        # Eğer fiyat hareketi kuvvetli olsaydı (|delta| > 1%), abstention "kötü" sayılır
        if realized_delta is not None and abs(realized_delta) > 1.0:
            reasons.append("abstain_when_strong_move_happened")
            score = -0.25  # Hafif eksi: fırsatı kaçırdı
        else:
            reasons.append("abstain_in_quiet_market_ok")
            score = +0.25  # Hafif artı: gereksiz risk almadı
        direction_correct = None
    else:
        if predicted_dir is None:
            reasons.append("decision_parse_failed")
        elif realized_dir is None:
            reasons.append("no_anchor_or_realized_data")
        else:
            direction_correct = (predicted_dir == realized_dir)
            # Score: -1..+1
            if direction_correct:
                score = +1.0 if predicted_dir != 0 else +0.5
            else:
                # Ters yön daha kötü, yan-trend tahmin etmek daha hafif yanlış
                if predicted_dir == 0 or realized_dir == 0:
                    score = -0.5
                else:
                    score = -1.0
            reasons.append(
                f"predicted={predicted_dir} realized={realized_dir} delta_pct={realized_delta:.2f}"
                if realized_delta is not None else f"predicted={predicted_dir} realized={realized_dir}"
            )

    eval_id = f"eval_{audit_id or 0}_{ts.strftime('%Y%m%dT%H%M%S')}"
    return EvalResult(
        eval_id=eval_id,
        audit_id=audit_id,
        snapshot_id=snapshot_id,
        endpoint=endpoint,
        evaluated_at=now.isoformat(),
        decision=decision_text,
        confidence_band=confidence_band,
        confidence_pct=float(confidence_pct) if confidence_pct is not None else None,
        abstained=abstained,
        horizon_hours=round(age_minutes / 60.0, 3),
        direction_correct=direction_correct,
        realized_delta_pct=round(realized_delta, 4) if realized_delta is not None else None,
        score=score,
        brier_like=round(brier, 4) if brier is not None else None,
        calibration_bucket=str(confidence_band) if confidence_band else None,
        reasons=reasons,
    )


# ────────────────────────────────────────────────────────────────────────────
# Toplu run + persistans
# ────────────────────────────────────────────────────────────────────────────

def run_eval_pass(
    *,
    limit: int = 100,
    endpoint: str | None = None,
    min_horizon_minutes: float = 5.0,
    persist: bool = True,
) -> dict[str, Any]:
    """Audit log'taki son kayıtları sırayla puanla."""
    audits = agent_audit_log.get_recent(limit=limit, endpoint=endpoint)
    now_prices = _get_now_prices()
    results: list[EvalResult] = []
    for a in audits:
        r = evaluate_audit_entry(a, now_prices=now_prices, min_horizon_minutes=min_horizon_minutes)
        if r is not None:
            results.append(r)

    # Persist + ring buffer
    if persist:
        try:
            _EVAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with _EVAL_LOG_PATH.open("a", encoding="utf-8") as h:
                for r in results:
                    h.write(json.dumps(asdict(r), ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass

    with _LOCK:
        for r in results:
            _RING.append(asdict(r))

    # Memory'ye otomatik ders çıkar — Sprint 7 hook
    try:
        from app.services import agent_memory_service
        for r in results:
            agent_memory_service.auto_lesson_from_eval(asdict(r))
    except Exception:
        pass

    return _summarize_results(results)


def _summarize_results(results: list[EvalResult]) -> dict[str, Any]:
    n = len(results)
    if n == 0:
        return {
            "status":   "ok",
            "count":    0,
            "summary":  "no_evaluable_audits",
            "results":  [],
        }
    scored = [r for r in results if r.score is not None]
    correct = [r for r in results if r.direction_correct is True]
    wrong = [r for r in results if r.direction_correct is False]
    abst = [r for r in results if r.abstained]
    avg_score = (sum(r.score for r in scored) / len(scored)) if scored else None
    avg_brier = None
    bsc = [r.brier_like for r in results if r.brier_like is not None]
    if bsc:
        avg_brier = sum(bsc) / len(bsc)

    # Confidence calibration: band → hit rate
    cal: dict[str, dict[str, Any]] = {}
    for r in results:
        b = r.calibration_bucket or "UNKNOWN"
        c = cal.setdefault(b, {"total": 0, "correct": 0, "wrong": 0, "abstain": 0})
        c["total"] += 1
        if r.direction_correct is True:
            c["correct"] += 1
        elif r.direction_correct is False:
            c["wrong"] += 1
        if r.abstained:
            c["abstain"] += 1
    for b, c in cal.items():
        decided = c["correct"] + c["wrong"]
        c["hit_rate"] = (c["correct"] / decided) if decided else None

    return {
        "status":            "ok",
        "count":             n,
        "scored_count":      len(scored),
        "correct_count":     len(correct),
        "wrong_count":       len(wrong),
        "abstain_count":     len(abst),
        "hit_rate":          (len(correct) / max(1, len(correct) + len(wrong))) if (correct or wrong) else None,
        "avg_score":         round(avg_score, 4) if avg_score is not None else None,
        "avg_brier":         round(avg_brier, 4) if avg_brier is not None else None,
        "calibration":       cal,
        "results":           [asdict(r) for r in results],
    }


def get_recent_evals(limit: int = 50) -> list[dict[str, Any]]:
    with _LOCK:
        items = list(_RING)
    items.reverse()
    return items[:max(1, min(limit, 500))]


def stats() -> dict[str, Any]:
    with _LOCK:
        items = list(_RING)
    return {
        "total":      len(items),
        "ring_max":   _RING.maxlen,
        "log_file":   str(_EVAL_LOG_PATH),
    }


__all__ = [
    "EvalResult",
    "evaluate_audit_entry",
    "run_eval_pass",
    "get_recent_evals",
    "stats",
]
