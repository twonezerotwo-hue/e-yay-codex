"""
Paper Account Archive — hesap sıfırlamadan önce state arşivle + memory finalize.

archive_and_finalize_paper_state(state_snapshot, reason) -> dict

Adımlar:
  1. Mevcut paper trading state'ini JSON arşiv dosyasına yaz.
  2. Kapalı trade'leri mistake_memory'ye finalize et (duplicate önle).
  3. learning / mistake_memory / calibration / auto_tune dosyalarına DOKUNMA.

Garantiler:
  • Paper trading state'ini değiştirmez (reset bu fonksiyonu çağıranın sorumluluğu).
  • PAPER_SAFE / NO_EXECUTION — gerçek emir yok.
  • Arşiv dizini yoksa oluşturulur.
  • Mevcut JSONL dosyaları (mistake_memory, learning_candidates vb.) silinmez.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ARCHIVE_DIR = (
    Path(__file__).resolve().parents[2] / "data" / "paper_trading_archives"
)

# Korunan veri dosyaları (silinmez — sadece bilgi amaçlı liste)
_PROTECTED_FILES = [
    "mistake_memory.jsonl",
    "learning_candidates.jsonl",
    "position_rechecks.jsonl",
    "weekly_calibrations.jsonl",
    "auto_tune_overrides.json",
    "signal_attribution.jsonl",
    "agent_theses.jsonl",
    "hourly_snapshots.jsonl",
]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _ts_for_filename() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _save_archive(state_snapshot: dict[str, Any], reason: str) -> str:
    """
    State snapshot'ını arşiv JSON dosyasına yazar.

    Returns:
        Arşiv dosyasının tam yolu (string).
    """
    _ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ts = _ts_for_filename()
    fname = f"paper_state_archive_{ts}.json"
    path = _ARCHIVE_DIR / fname

    archive_payload = {
        "archived_at":         _utc_now_iso(),
        "archive_reason":      reason,
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
        "state_snapshot":      state_snapshot,
    }

    path.write_text(
        json.dumps(archive_payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("paper_account_archive: arşiv yazıldı → %s", path)
    return str(path)


def _finalize_closed_trades(
    closed_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Kapalı trade'leri mistake_memory'ye finalize eder.
    Daha önce finalize edilmişleri atlar (duplicate önleme).

    Returns:
        {"finalized": int, "skipped": int, "failed": int, "memory_ids": [...]}
    """
    from app.services.mistake_memory_service import (  # noqa: PLC0415
        build_mistake_memory,
    )
    from app.storage.mistake_memory_store import (  # noqa: PLC0415
        load_finalized_fingerprints,
        save_mistake_memory,
    )
    from app.storage.learning_candidate_store import (  # noqa: PLC0415
        load_recent_learning_candidates,
    )
    from app.storage.position_recheck_store import (  # noqa: PLC0415
        load_recent_position_rechecks,
    )
    from app.services.mistake_memory_service import _trade_fingerprint  # noqa: PLC0415

    existing_fps = load_finalized_fingerprints()
    all_candidates = load_recent_learning_candidates(limit=1000)
    all_rechecks   = load_recent_position_rechecks(limit=1000)

    finalized   = 0
    skipped     = 0
    failed      = 0
    memory_ids: list[str] = []

    for trade in closed_trades:
        fp = _trade_fingerprint(trade)
        if fp in existing_fps:
            skipped += 1
            continue

        # Matching candidates (aynı pair + yakın entry fiyatı)
        pair_up = str(trade.get("pair") or "").upper()
        candidates = [
            c for c in all_candidates
            if str(c.get("pair") or "").upper() == pair_up
        ]
        rechecks = [
            r for r in all_rechecks
            if str(r.get("pair") or "").upper() == pair_up
        ]

        try:
            memory = build_mistake_memory(trade, candidates, rechecks)
            if memory.get("status") == "not_created":
                failed += 1
                logger.warning(
                    "paper_account_archive: finalize başarısız — %s: %s",
                    trade.get("pair"), memory.get("reason"),
                )
                continue

            mid = save_mistake_memory(memory)
            existing_fps.add(fp)   # bellek içi dedup
            memory_ids.append(mid)
            finalized += 1
        except Exception:  # noqa: BLE001
            failed += 1
            logger.exception(
                "paper_account_archive: finalize exception — pair=%s", trade.get("pair")
            )

    return {
        "finalized":   finalized,
        "skipped":     skipped,
        "failed":      failed,
        "memory_ids":  memory_ids,
    }


def archive_and_finalize_paper_state(
    state_snapshot: dict[str, Any],
    reason: str = "fresh_paper_account_keep_learning_memory",
) -> dict[str, Any]:
    """
    Mevcut paper trading state'ini arşivle ve kapalı trade'leri finalize et.

    Bu fonksiyon state'i SIFIRLAMAZ — reset çağıranın sorumluluğundadır.
    Tüm learning / memory / calibration / auto_tune JSONL dosyaları korunur.

    Args:
        state_snapshot:  get_snapshot() veya _load_state().__dict__ çıktısı.
        reason:          Arşiv dosyasına yazılacak sebep etiketi.

    Returns:
        {
            "archive_path": str,
            "finalize_result": {finalized, skipped, failed, memory_ids},
            "protected_files": [...],
            "decision_permission": "NO_EXECUTION",
            "execution_mode": "PAPER_SAFE",
        }
    """
    # 1. Arşiv
    archive_path = _save_archive(state_snapshot, reason)

    # 2. Kapalı trade'leri finalize et
    closed_trades: list[dict[str, Any]] = (
        state_snapshot.get("closed_trades")
        or state_snapshot.get("trade_history")
        or state_snapshot.get("trades")
        or []
    )
    finalize_result = _finalize_closed_trades(closed_trades)

    logger.info(
        "paper_account_archive: finalize tamamlandı — "
        "finalized=%d skipped=%d failed=%d",
        finalize_result["finalized"],
        finalize_result["skipped"],
        finalize_result["failed"],
    )

    return {
        "archive_path":        archive_path,
        "finalize_result":     finalize_result,
        "protected_files":     _PROTECTED_FILES,
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
    }
