"""Best-effort enrichment hatalarını GÖRÜNÜR audit warning'lerine çevirir.

Sistemde "try/except → sessiz default" ile yutulan enrichment hataları
gözlemlenemiyordu. Bu küçük yardımcı, böyle bir hatayı:
  • logger.warning ile loglar,
  • standart bir warning dict olarak döner (endpoint response'una eklenebilir),
böylece sistem ÇALIŞMAYA DEVAM eder (çağıran default davranışına döner) ama hata
artık görünür olur.

Standart format:
  {"source", "severity", "reason", "message", "recoverable"}

PAPER_SAFE / NO_EXECUTION — yalnızca gözlemlenebilirlik; karar/trade etkilemez.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def make_audit_warning(
    source: str,
    reason: str,
    message: str,
    *,
    severity: str = "warning",
    recoverable: bool = True,
) -> dict[str, Any]:
    """Standart audit warning objesi üret + logla.

    Çağıran taraf bu dict'i bir audit_warnings listesine ekler ve kendi default
    davranışına devam eder; endpoint her durumda 200 kalır.
    """
    warning: dict[str, Any] = {
        "source":      source,
        "severity":    severity,
        "reason":      reason,
        "message":     str(message)[:300],
        "recoverable": recoverable,
    }
    logger.warning(
        "audit_warning · source=%s · reason=%s · recoverable=%s · %s",
        source, reason, recoverable, warning["message"],
    )
    return warning
