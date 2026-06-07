"""
Event Calendar Service — Olay Takvimi.

Yaklaşan piyasa katalizörlerini config/event_calendar.yaml'dan okur,
bugünden itibaren kaç gün kaldığını hesaplar ve RegimeReport'a ekler.
Hiçbir zaman trade execution üretmez — PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

import yaml

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

ImportanceCode = Literal["CRITICAL", "HIGH", "MEDIUM"]
CategoryCode = Literal["FED", "MACRO", "ENERGY", "CRYPTO", "EQUITY", "GEOPOLITICAL"]


@dataclass(frozen=True)
class CatalystEvent:
    id: str
    date: str              # ISO 8601: YYYY-MM-DD
    name: str
    category: CategoryCode
    importance: ImportanceCode
    expectation: str
    market_impact: str
    days_until: int        # negative = geçmişte (gösterilmez)


# ---------------------------------------------------------------------------
# Calendar loader
# ---------------------------------------------------------------------------

_DEFAULT_CALENDAR_PATH = (
    Path(__file__).resolve().parents[3] / "config" / "event_calendar.yaml"
)


class EventCalendarService:
    """
    Takvimi YAML'dan okur, önümüzdeki N günü filtreler ve sıralar.
    Offline/test ortamlarında custom yaml_path inject edilebilir.
    """

    def __init__(self, yaml_path: Path | None = None) -> None:
        self._path = yaml_path or _DEFAULT_CALENDAR_PATH

    def fetch_upcoming(
        self,
        horizon_days: int = 120,
        max_events: int = 20,
        reference_date: date | None = None,
    ) -> tuple[CatalystEvent, ...]:
        """
        Bugünden `horizon_days` içindeki etkinlikleri döndürür.
        CRITICAL önce, aynı importance içinde tarihe göre sıralı.
        """
        today = reference_date or datetime.now(UTC).date()

        try:
            raw = self._path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)
            raw_events: list[dict] = data.get("events", [])
        except Exception:  # noqa: BLE001
            return ()

        events: list[CatalystEvent] = []

        for ev in raw_events:
            try:
                ev_date = date.fromisoformat(ev["date"])
            except (KeyError, ValueError):
                continue

            days_until = (ev_date - today).days
            if days_until < 0 or days_until > horizon_days:
                continue

            events.append(CatalystEvent(
                id=ev.get("id", ""),
                date=ev["date"],
                name=ev.get("name", ""),
                category=ev.get("category", "MACRO"),
                importance=ev.get("importance", "MEDIUM"),
                expectation=ev.get("expectation", ""),
                market_impact=ev.get("market_impact", ""),
                days_until=days_until,
            ))

        events.sort(key=lambda e: e.days_until)  # yakın tarihten uzağa
        return tuple(events[:max_events])


__all__ = [name for name in globals() if not name.startswith("_")]
