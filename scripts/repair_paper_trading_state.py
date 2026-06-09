#!/usr/bin/env python3
"""
Paper Trading State Repair — CLI.

Bozuk realized_pnl/equity'i sağlıklı trade'lerden yeniden hesaplar.
Apply modunda önce backup alır, sonra state'i düzeltir.

PAPER_SAFE / NO_EXECUTION — sadece JSON state dosyasıyla iş yapar.

Örnekler:
    python scripts/repair_paper_trading_state.py --dry-run
    python scripts/repair_paper_trading_state.py --apply
    python scripts/repair_paper_trading_state.py --apply --backend-url http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Proje kökünü PYTHONPATH'e ekle (backend/ altındaki paketleri import edebilmek için)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services import paper_trading_service as pts  # noqa: E402


def _print(payload: dict, *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(payload, ensure_ascii=False, default=str))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Sadece rapor üret, state'i değiştirme")
    group.add_argument("--apply", action="store_true", help="Backup al + state'i düzelt")
    parser.add_argument("--no-pretty", action="store_true", help="Çıktıyı tek satır JSON ver")
    args = parser.parse_args()

    result = pts.repair_state(dry_run=args.dry_run)
    _print(result, pretty=not args.no_pretty)

    if result.get("status") == "repair_not_safe":
        print(
            "\n[!] Repair güvenli değil: tüm closed trade kayıtları bozuk. "
            "Önce hard reset gerekli:\n"
            "    curl -X POST http://127.0.0.1:8000/api/v1/trading/state/reset",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
