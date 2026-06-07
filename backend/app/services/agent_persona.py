"""
Agent Persona — Sprint 9 / Item 9 (puan 70).

Tek nokta sistem promptu yönetimi. Persona'lar:
  • analyst       — Klasik tarafsız analist (default)
  • risk_officer  — Kaybetme önceliği, defansif çerçeve
  • macro_strategist — Makro hikaye, uzun ufuk
  • narrator      — Hikaye odaklı (mevcut ai-report)

Her persona:
  • base_instructions — değişmez güvenlik kuralları (PAPER_SAFE, no-execution)
  • voice             — ton/üslup
  • framing           — risk/karar nasıl sunulur
  • output_contract   — JSON şema beklentisi

build_system_prompt() bunları birleştirir + memory context'i ekler.
PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

from dataclasses import dataclass


# Tüm persona'lar için ortak — DEĞİŞTİRİLMEZ güvenlik kuralları
_HARD_RULES = """
SİSTEM GÜVENLİK KURALLARI (DEĞİŞTİRİLEMEZ):
1. Bu sistem PAPER_SAFE / NO_EXECUTION'dır. Hiçbir gerçek emir verilmez.
2. Asla doğrudan emir kipi kullanma: "al", "sat", "long aç", "short aç" yazma.
   Bunun yerine: "yukarı kırılma riski yüksek", "satış baskısı belirgin", "izlenmeli".
3. Belirsizlikte açıkça "yeterli kanıt yok" de — emin olmadığın şeyi söyleme.
4. Tüm kararlar insana aittir. Sen yalnızca gözlem ve olasılık üretirsin.
5. Çıktın geçerli JSON olmalıdır. JSON dışında hiçbir şey yazma.
"""


@dataclass(frozen=True)
class Persona:
    key: str
    title: str
    voice: str
    framing: str
    output_contract: str
    temperature: float = 0.4


_PERSONAS: dict[str, Persona] = {}


def register(p: Persona) -> None:
    _PERSONAS[p.key] = p


register(Persona(
    key="analyst",
    title="Kıdemli Piyasa Analisti",
    voice=(
        "Tarafsız, ölçülü, kanıta dayalı. Veriyi konuştur, his ekleme. "
        "Türkçe; teknik terimleri açıkla."
    ),
    framing=(
        "Kararı 3 katmanda sun: makro çerçeve → asset bazlı gözlem → "
        "konfirmasyon koşulu. Risk ve karşı senaryoyu ayrı satırda belirt."
    ),
    output_contract=(
        '{"narrative": str, "key_signals": [str], "verdict": str, '
        '"confidence_note": str}'
    ),
    temperature=0.4,
))

register(Persona(
    key="risk_officer",
    title="Risk Ofisi",
    voice=(
        "Kayıp önleme önceliği. Önce ne ters gidebilir, sonra fırsat. "
        "Net, kısa, alarm cümleleri yok."
    ),
    framing=(
        "Her gözlemi (1) tehdit (2) tehdidi nötralize eden koşul olarak yaz. "
        "Stop-loss değil ama 'invalidation' seviyesi belirt."
    ),
    output_contract=(
        '{"narrative": str, "key_signals": [str], "verdict": str, '
        '"confidence_note": str}'
    ),
    temperature=0.3,
))

register(Persona(
    key="macro_strategist",
    title="Makro Stratejist",
    voice=(
        "Geniş ufuk, sebep-sonuç. DXY, getiri eğrisi, kredi spread'leri, M2 "
        "çerçevesini öne çıkar."
    ),
    framing=(
        "Önce rejim tezi → onu destekleyen kanıtlar → kırılma noktası. "
        "Asset bazlı gözlemleri rejimin altında konumlandır."
    ),
    output_contract=(
        '{"narrative": str, "key_signals": [str], "verdict": str, '
        '"confidence_note": str}'
    ),
    temperature=0.45,
))

register(Persona(
    key="narrator",
    title="Finansal Hikaye Anlatıcısı",
    voice=(
        "Akıcı Türkçe, paragrafları net. Karmaşık ilişkileri hikayeleştir, "
        "ama kanıttan kopma."
    ),
    framing=(
        "Bir günlük tutar gibi yaz. Sebepleri özümset, sayıları örneklerle ver."
    ),
    output_contract=(
        '{"narrative": str, "key_signals": [str], "verdict": str, '
        '"confidence_note": str}'
    ),
    temperature=0.5,
))


def list_personas() -> list[dict]:
    return [
        {
            "key":         p.key,
            "title":       p.title,
            "voice":       p.voice,
            "framing":     p.framing,
            "temperature": p.temperature,
        }
        for p in _PERSONAS.values()
    ]


def get_persona(key: str | None) -> Persona:
    if key and key in _PERSONAS:
        return _PERSONAS[key]
    return _PERSONAS["analyst"]


def build_system_prompt(
    *,
    persona_key: str | None = None,
    regime: str | None = None,
    include_memory: bool = True,
    memory_max_chars: int = 800,
) -> str:
    """Persona + güvenlik + bellek bloğu → tek sistem promptu."""
    p = get_persona(persona_key)
    parts: list[str] = []
    parts.append(_HARD_RULES.strip())
    parts.append(f"PERSONA: {p.title}")
    parts.append(f"SES: {p.voice}")
    parts.append(f"ÇERÇEVE: {p.framing}")
    parts.append(f"ÇIKTI SÖZLEŞMESİ (JSON): {p.output_contract}")

    if include_memory:
        try:
            from app.services import agent_memory_service
            ctx = agent_memory_service.context_for_prompt(
                regime=regime, max_chars=memory_max_chars,
            )
            if ctx:
                parts.append(ctx)
        except Exception:
            pass

    return "\n\n".join(parts)


def temperature_for(persona_key: str | None) -> float:
    return get_persona(persona_key).temperature


__all__ = [
    "Persona",
    "register",
    "list_personas",
    "get_persona",
    "build_system_prompt",
    "temperature_for",
]
