"""
Agent Output Guard — Sprint 1 / Item 7.

"AI karar vermez" kuralını response seviyesinde enforce eder.

Kontroller:
  1. Schema guard: dict response'larda decision_permission ve final_decision alanları
     zorunlu olur ve sabitlenir (SIGNAL_ONLY_NOT_FINAL / False).
  2. Text guard: serbest metin response'larda imperative karar dili tespiti.
     Bulunursa violation log + safety footer iliştirilir.

Bu modül text bloklamaz — sadece işaretler ve footer ekler.
Çünkü agent legitim olarak "consensus bullish görünüyor" diyebilmeli;
yasak olan "şimdi LONG aç" gibi imperative komutlar.
"""
from __future__ import annotations

import logging
import re
from typing import Any

_log = logging.getLogger(__name__)

# ── İmperative karar dili (TR/EN) ────────────────────────────────────────────
# Pattern'lar word-boundary ile sarılı — false positive azaltır.
_DECISION_PATTERNS: tuple[tuple[str, str], ...] = (
    # EN imperative
    (r"\b(buy|sell|go long|go short)\s+(now|immediately|asap)\b", "EN_IMPERATIVE_EXEC"),
    (r"\b(execute|place)\s+(this\s+)?(trade|order|buy|sell)\b",   "EN_EXEC_VERB"),
    (r"\bopen\s+(a\s+)?(long|short)\s+position\b",                "EN_OPEN_POSITION"),
    (r"\b(close|exit)\s+(your|the)\s+position\s+now\b",           "EN_CLOSE_NOW"),
    # TR imperative
    (r"\b(şimdi|hemen)\s+(al|sat)\b",                              "TR_IMPERATIVE_NOW"),
    (r"\b(long|short|alış|satış)\s+(aç|gir)\b",                    "TR_OPEN_POS"),
    (r"\bpozisyon\s+(aç|kapat)\s+(şimdi|hemen)\b",                 "TR_POS_NOW"),
    (r"\b(al|sat)\s+emri\s+(ver|gönder|aç)\b",                     "TR_ORDER_VERB"),
    (r"\btavsiyem\s+(al|sat|long|short)\b",                        "TR_RECOMMEND_EXEC"),
)

SAFETY_FOOTER = (
    "\n\n---\n"
    "⚠️ Bu çıktı sadece **analiz/sinyal**'dir, **karar değildir**. "
    "Tüm işlem kararları kullanıcıya aittir. PAPER_SAFE · NO_EXECUTION."
)

CANONICAL_DECISION_PERMISSION = "SIGNAL_ONLY_NOT_FINAL"


def detect_decision_language(text: str) -> list[str]:
    """Metinde imperative karar dili pattern'lerini tespit et."""
    if not text:
        return []
    hits: list[str] = []
    for pattern, label in _DECISION_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            hits.append(label)
    return hits


def guard_text(text: str, *, source: str = "unknown") -> tuple[str, list[str]]:
    """Metni validate et + safety footer ekle.

    Returns: (sanitized_text, violations)
      • sanitized_text: orijinal metin + (eğer yoksa) safety footer
      • violations: tespit edilen pattern label listesi

    Asla metni reddetmez — sadece işaretler ve footer ekler.
    Çağıran isterse violations boş olmadığında 4xx döndürmeyi tercih edebilir.
    """
    if not text:
        return text, []
    violations = detect_decision_language(text)
    if violations:
        _log.warning(
            "agent_output_guard · imperative_decision_language · source=%s · hits=%s",
            source, violations,
        )
    sanitized = text
    # Footer zaten varsa tekrar ekleme
    if "PAPER_SAFE" not in sanitized and "SIGNAL_ONLY_NOT_FINAL" not in sanitized:
        sanitized = sanitized + SAFETY_FOOTER
    return sanitized, violations


def enforce_schema(response: dict[str, Any], *, source: str = "unknown") -> dict[str, Any]:
    """Dict response'a karar yetkisi alanlarını sabitle.

    Çağıran tarafın değerleri override edemez — bu fonksiyon her zaman:
      decision_permission = "SIGNAL_ONLY_NOT_FINAL"
      final_decision      = False
      execution_authority = "human"
    set eder.
    """
    if not isinstance(response, dict):
        return response  # idempotent — dict değilse dokunma

    existing_perm = response.get("decision_permission")
    if existing_perm and existing_perm != CANONICAL_DECISION_PERMISSION:
        _log.warning(
            "agent_output_guard · decision_permission_override · source=%s · was=%s",
            source, existing_perm,
        )

    existing_final = response.get("final_decision")
    if existing_final is True:
        _log.warning(
            "agent_output_guard · final_decision_blocked · source=%s",
            source,
        )

    response["decision_permission"] = CANONICAL_DECISION_PERMISSION
    response["final_decision"]      = False
    response["execution_authority"] = "human"
    response["safety_mode"]         = "PAPER_SAFE / NO_EXECUTION"
    return response


def guard_response(
    response: dict[str, Any],
    *,
    text_fields: tuple[str, ...] = ("text", "summary", "analysis", "narrative"),
    source: str = "unknown",
) -> dict[str, Any]:
    """Hem schema'yı sabitle hem listelenen metin alanlarına text guard uygula."""
    response = enforce_schema(response, source=source)
    violations_seen: list[str] = []
    for f in text_fields:
        v = response.get(f)
        if isinstance(v, str):
            new_text, hits = guard_text(v, source=f"{source}.{f}")
            response[f] = new_text
            violations_seen.extend(hits)
    if violations_seen:
        response.setdefault("guard_warnings", []).extend(violations_seen)
    return response


__all__ = [
    "detect_decision_language",
    "guard_text",
    "enforce_schema",
    "guard_response",
    "SAFETY_FOOTER",
    "CANONICAL_DECISION_PERMISSION",
]
