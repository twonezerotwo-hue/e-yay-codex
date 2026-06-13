"""
Paper Signal Chain Tracker — gözlemci / etiketleyici katman.

Bu modül paper trading sinyallerini multi-timeframe "chain" mantığıyla SINIFLANDIRIR
ve etiketler. Trade'i kim açacağına KARAR VERMEZ — açılış kararı tamamen mevcut
deterministik paper_trading_service akışına (pending_orders → manual_ready) aittir.
(CLAUDE.md System Boundary: "AI explains; deterministic code owns decisions".)

Tasarım kuralları:
  • Kendi state dosyası (data/signal_chain_state.json) — paper_trading_state.json'a
    ASLA dokunmaz. Bozuk/eksik dosya → boş chain seti. Paper state bütünlüğü için
    sıfır risk.
  • Best-effort — tüm çağrılar tick döngüsünde try/except ile sarılır; buradaki bir
    hata bir paper tick'ini ASLA bozamaz.
  • Additive — yeni davranış yalnızca etiket + bildirim üretir.

PAPER_SAFE / NO_EXECUTION — gerçek emir YOK.
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# paper_trading_service ile aynı data dizini (backend/data/), ama AYRI dosya.
_STATE_PATH = Path(__file__).resolve().parents[2] / "data" / "signal_chain_state.json"
_LOCK = threading.Lock()

# ── Signal level sabitleri ────────────────────────────────────────────────────
SINGLE   = "single_signal"
DUPLICATE = "same_timeframe_duplicate"
DOUBLE   = "double_timeframe_signal"
TRIPLE   = "triple_timeframe_confirmation"
CONFLICT = "timeframe_conflict"

# Seviye → onay penceresi (saniye). triple = 0 → mevcut pending zaten açıyor.
COUNTDOWN_WINDOWS: dict[str, int] = {SINGLE: 60, DOUBLE: 30, TRIPLE: 0}

# Seviye → bildirim tonu (frontend renk eşlemesi).
TONES: dict[str, str] = {
    SINGLE: "amber", DUPLICATE: "slate", DOUBLE: "cyan",
    TRIPLE: "emerald", CONFLICT: "red",
}

# Snapshot'ta "aktif" sayılma süresi ve dosyadan tamamen silinme süresi.
ACTIVE_TTL_SECONDS = 1800       # 30 dk içinde görülen chain'ler aktif
PRUNE_TTL_SECONDS = 6 * 3600    # 6 saatten eski chain'ler dosyadan düşer

# TF sıralama anahtarı — küçükten büyüğe (1h < 4h < 1d ...).
_TF_ORDER: dict[str, int] = {
    "1m": 1, "5m": 2, "15m": 3, "30m": 4, "1h": 5, "2h": 6,
    "4h": 7, "6h": 8, "8h": 9, "12h": 10, "1d": 11, "3d": 12, "1w": 13,
}


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(UTC)


def _norm_tf(tf: Any) -> str:
    return str(tf or "").strip().lower()


def _tf_sort_key(tf: str) -> int:
    return _TF_ORDER.get(_norm_tf(tf), 99)


def _norm_dir(direction: Any) -> str:
    d = str(direction or "").strip().lower()
    if d in ("bullish", "long", "up", "buy"):
        return "bullish"
    if d in ("bearish", "short", "down", "sell"):
        return "bearish"
    return "neutral"


def _dir_for_side(side: str) -> str:
    return "bullish" if str(side).upper() == "LONG" else "bearish"


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


# ── SignalChain state ─────────────────────────────────────────────────────────

@dataclass
class SignalChain:
    asset: str
    side: str  # "LONG" | "SHORT"
    status: str = "watching"  # watching | auto_opening | conflict | cancelled
    confirmed_timeframes: list[str] = field(default_factory=list)
    rejected_timeframes: list[str] = field(default_factory=list)
    duplicate_timeframes: list[str] = field(default_factory=list)
    conflict_timeframes: list[str] = field(default_factory=list)
    first_seen_at: str = ""
    last_seen_at: str = ""
    countdown_seconds: int = 0
    signal_level: str = SINGLE
    auto_open_reason: str = ""
    user_action: str = ""  # "" | "cancelled"
    experiment_labels: list[str] = field(default_factory=list)
    learning_labels: list[str] = field(default_factory=list)
    # ── İç alanlar (canlı countdown hesabı + bildirim) ──
    countdown_window: int = 0
    countdown_started_at: str = ""
    last_notification: dict[str, Any] = field(default_factory=dict)


_CHAIN_FIELD_NAMES = {f.name for f in fields(SignalChain)}


def _chain_from_dict(asset: str, d: dict[str, Any]) -> SignalChain:
    clean = {k: v for k, v in (d or {}).items() if k in _CHAIN_FIELD_NAMES}
    clean.setdefault("asset", asset)
    clean.setdefault("side", "LONG")
    return SignalChain(**clean)


def _load() -> dict[str, SignalChain]:
    if not _STATE_PATH.exists():
        return {}
    try:
        raw = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        logger.debug("signal_chain_tracker: load failed (corrupt?) → boş", exc_info=True)
        return {}
    out: dict[str, SignalChain] = {}
    for asset, d in (raw.get("chains") or {}).items():
        try:
            out[asset] = _chain_from_dict(asset, d)
        except Exception:
            continue
    return out


def _save(chains: dict[str, SignalChain]) -> None:
    try:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "chains": {a: asdict(c) for a, c in chains.items()},
            "updated_at": _now().isoformat(),
        }
        _STATE_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8",
        )
    except Exception:
        logger.debug("signal_chain_tracker: save failed (yok sayıldı)", exc_info=True)


# ── Bildirim üretimi (data-driven) ────────────────────────────────────────────

def _tf_display(timeframes: list[str]) -> list[str]:
    """Görüntüleme için TF listesi — büyükten küçüğe (1D + 4H + 1H)."""
    return [tf.upper() for tf in sorted(timeframes, key=_tf_sort_key, reverse=True)]


def _build_notification(
    chain: SignalChain, primary_tf: str, *, new_side: str | None = None,
) -> dict[str, Any]:
    asset = chain.asset
    side = chain.side
    level = chain.signal_level
    tfs = _tf_display(chain.confirmed_timeframes)
    tf_join = " + ".join(tfs) if tfs else (primary_tf.upper() if primary_tf else "")
    countdown = chain.countdown_window

    if level == SINGLE:
        text = (
            f"{asset} {side} {tf_join}: paper trade sinyali geldi. "
            f"{countdown} sn içinde iptal etmezsen işlem açılacak."
        )
        reason = "Tek timeframe sinyali"
    elif level == DOUBLE:
        text = (
            f"Double timeframe signal: {asset} {side} {tf_join} aynı yönde. "
            f"{countdown} sn içinde iptal etmezsen paper trade açılacak."
        )
        reason = "İki timeframe aynı yönde teyit verdi"
    elif level == TRIPLE:
        text = (
            f"Triple timeframe confirmation: {asset} {side} {tf_join}. "
            f"Paper trade otomatik açıldı."
        )
        reason = "Üç timeframe aynı yönde — en güçlü teyit"
    elif level == DUPLICATE:
        dup_tf = (primary_tf or (chain.duplicate_timeframes[-1] if chain.duplicate_timeframes else "")).upper()
        text = f"Yinelenen sinyal: {asset} {side} {dup_tf} tekrarlandı."
        reason = "Aynı timeframe tekrarı — yeni işlem açılmaz"
    elif level == CONFLICT:
        conflict_side = new_side or side
        new_tf = (primary_tf or (chain.conflict_timeframes[-1] if chain.conflict_timeframes else "")).upper()
        text = (
            f"Timeframe conflict: {asset} {side} ama {new_tf} {conflict_side}. "
            f"Paper trade beklemeye alındı."
        )
        reason = "Ters yönlü timeframe — işlem açılmaz, beklemede"
    else:
        text = f"{asset} {side} sinyali"
        reason = ""

    return {
        "level": level,
        "asset": asset,
        "side": side,
        "primary_tf": primary_tf.upper() if primary_tf else "",
        "timeframes": tfs,
        "countdown": countdown,
        "tone": TONES.get(level, "slate"),
        "reason": reason,
        "text": text,
        "at": chain.last_seen_at,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def observe(
    asset: str,
    side: str,
    primary_tf: str,
    tf_directions: dict[str, Any] | None = None,
    experiment_labels: list[str] | None = None,
    now: datetime | None = None,
) -> SignalChain:
    """Bir tick'te (asset, side) için sinyali gözlemle ve chain'i sınıflandır.

    Saf gözlemci — pozisyon AÇMAZ. Yalnızca chain seviyesini etiketler ve
    bildirim üretir.
    """
    now = now or _now()
    now_iso = now.isoformat()
    primary_tf = _norm_tf(primary_tf)
    want = _dir_for_side(side)
    opp = "bearish" if want == "bullish" else "bullish"

    tf_directions = tf_directions or {}
    agree = {_norm_tf(tf) for tf, d in tf_directions.items() if _norm_dir(d) == want}
    if primary_tf:
        agree.add(primary_tf)
    oppose = {_norm_tf(tf) for tf, d in tf_directions.items() if _norm_dir(d) == opp}
    agree.discard("")
    oppose.discard("")

    with _LOCK:
        chains = _load()
        chain = chains.get(asset)

        # ── Conflict: aynı asset için mevcut chain'in TERS yönünde sinyal ──
        if (
            chain is not None
            and chain.side != side
            and chain.confirmed_timeframes
            and chain.user_action != "cancelled"
        ):
            for tf in ([primary_tf] if primary_tf else []) + sorted(oppose):
                if tf and tf not in chain.conflict_timeframes:
                    chain.conflict_timeframes.append(tf)
            chain.signal_level = CONFLICT
            chain.status = "conflict"
            chain.countdown_window = 0
            chain.countdown_seconds = 0
            chain.countdown_started_at = now_iso
            chain.last_seen_at = now_iso
            if experiment_labels:
                chain.experiment_labels = list(experiment_labels)
            chain.last_notification = _build_notification(chain, primary_tf, new_side=side)
            chains[asset] = chain
            _save(chains)
            return chain

        # ── Yeni chain (yoksa ya da boş ters chain'in yerine) ──
        if chain is None or (chain.side != side and not chain.confirmed_timeframes):
            chain = SignalChain(
                asset=asset, side=side,
                first_seen_at=now_iso, last_seen_at=now_iso,
            )

        prev_confirmed = set(chain.confirmed_timeframes)
        new_tfs = agree - prev_confirmed

        # Aynı yönde gelen ters-TF bilgisini kaydet (chain'i çevirmez, sadece not).
        for tf in sorted(oppose):
            if tf and tf not in chain.conflict_timeframes:
                chain.conflict_timeframes.append(tf)

        if not new_tfs:
            # ── Duplicate: aynı TF tekrar, yeni TF yok ──
            if primary_tf:
                chain.duplicate_timeframes.append(primary_tf)
            chain.signal_level = DUPLICATE
            chain.last_seen_at = now_iso
            if experiment_labels:
                chain.experiment_labels = list(experiment_labels)
            chain.last_notification = _build_notification(chain, primary_tf)
            chains[asset] = chain
            _save(chains)
            return chain

        # ── Yeni TF teyidi → seviye yükselt ──
        chain.confirmed_timeframes = sorted(prev_confirmed | new_tfs, key=_tf_sort_key)
        if chain.user_action == "cancelled":
            chain.user_action = ""  # yeni teyit → yeniden aktif (rejected geçmişte kalır)
        count = len(chain.confirmed_timeframes)

        if count >= 3:
            chain.signal_level = TRIPLE
            chain.auto_open_reason = TRIPLE
            chain.status = "auto_opening"
            window = COUNTDOWN_WINDOWS[TRIPLE]
        elif count == 2:
            chain.signal_level = DOUBLE
            chain.status = "watching"
            window = COUNTDOWN_WINDOWS[DOUBLE]
        else:
            chain.signal_level = SINGLE
            chain.status = "watching"
            window = COUNTDOWN_WINDOWS[SINGLE]

        chain.countdown_window = window
        chain.countdown_seconds = window
        chain.countdown_started_at = now_iso
        chain.last_seen_at = now_iso
        if experiment_labels:
            chain.experiment_labels = list(experiment_labels)
        chain.last_notification = _build_notification(chain, primary_tf)
        chains[asset] = chain
        _save(chains)
        return chain


def apply_user_action(
    asset: str, action: str, now: datetime | None = None,
) -> SignalChain | None:
    """Kullanıcı aksiyonu uygula. 'cancel' → chain silinmez, watch memory'de kalır."""
    now = now or _now()
    with _LOCK:
        chains = _load()
        chain = chains.get(asset)
        if chain is None:
            return None
        if action == "cancel":
            chain.user_action = "cancelled"
            chain.status = "cancelled"
            for tf in chain.confirmed_timeframes:
                if tf not in chain.rejected_timeframes:
                    chain.rejected_timeframes.append(tf)
            chain.countdown_window = 0
            chain.countdown_seconds = 0
            chain.last_seen_at = now.isoformat()
        chains[asset] = chain
        _save(chains)
        return chain


def _live_countdown(chain: SignalChain, now: datetime) -> int:
    window = int(chain.countdown_window or 0)
    if window <= 0:
        return 0
    started = _parse_iso(chain.countdown_started_at)
    if started is None:
        return window
    elapsed = (now - started).total_seconds()
    return max(0, int(round(window - elapsed)))


def context_for(asset: str) -> dict[str, Any]:
    """Açılan trade'in open_signal'ına damgalanacak kompakt chain bağlamı."""
    with _LOCK:
        chains = _load()
        chain = chains.get(asset)
        if chain is None:
            return {}
        return {
            "signal_chain_type": chain.signal_level,
            "side": chain.side,
            "confirmed_timeframes": list(chain.confirmed_timeframes),
            "rejected_before_open": list(chain.rejected_timeframes),
            "duplicate_count": len(chain.duplicate_timeframes),
            "conflict_count": len(chain.conflict_timeframes),
            "auto_open_reason": chain.auto_open_reason,
            "countdown_seconds": int(chain.countdown_seconds or 0),
        }


def snapshot(now: datetime | None = None) -> list[dict[str, Any]]:
    """Aktif chain'lerin salt-okunur görünümü (canlı countdown ile)."""
    now = now or _now()
    out: list[dict[str, Any]] = []
    with _LOCK:
        chains = _load()
        changed = False
        for asset in list(chains.keys()):
            chain = chains[asset]
            last_seen = _parse_iso(chain.last_seen_at)
            age = (now - last_seen).total_seconds() if last_seen else 0.0
            if age > PRUNE_TTL_SECONDS:
                del chains[asset]
                changed = True
                continue
            if age > ACTIVE_TTL_SECONDS:
                continue  # dosyada kalır ama aktif değil
            d = asdict(chain)
            d["countdown_seconds"] = _live_countdown(chain, now)
            out.append(d)
        if changed:
            _save(chains)
    # En güncel görülen önce
    out.sort(key=lambda c: c.get("last_seen_at") or "", reverse=True)
    return out
