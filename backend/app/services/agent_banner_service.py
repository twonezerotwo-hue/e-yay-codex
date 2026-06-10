"""
FAZ 10.1 — Agent Banner Service.

Stored data'dan (snapshot/thesis/paper state/learning) dinamik,
işlem odaklı banner üretir.

Live market call YOK.
Uydurma/synthetic içerik YOK — veri yoksa "kayıt yok" döner.
Broker bağlantısı YOK.

FAZ 14 — News-aware headline:
  • Haber başlıkları sınıflandırılır (savaş/makro/kripto/metaller)
  • Fiyat sinyalleriyle çapraz teyit
  • Haber varsa headline pozisyon sayısına kilitlenmez
  • news_story, source_news_titles, generated_at eklendi

Üretilen banner:
  {
    "mode":                "waiting" | "managing_position" | "contradiction"
                         | "risk_alert" | "learning",
    "headline":            str,
    "main_view":           str,
    "top_signals":         [str, ...],
    "contradictions":      [str, ...],
    "watch_next":          [str, ...],
    "position_note":       str | None,
    "learning_note":       str | None,
    "updated_at":          str,
    "generated_at":        str,
    "news_story":          str,
    "source_news_titles":  [str, ...],
    -- FAZ 13 --
    "market_thought":      str,
    "price_story":         str,
    "event_story":         str,
    "event_calendar_note": str,
    "market_pricing_note": str,
    "next_trigger":        str,
  }

Mod önceliği: risk_alert > contradiction > managing_position > learning > waiting
Headline önceliği: anomaly > sanity_fail > major_news > major_move > position > waiting
"""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

from app.storage.agent_thesis_store import load_recent_agent_theses
from app.storage.auto_tune_store import read_overrides
from app.storage.hourly_snapshot_store import load_recent_hourly_snapshots
from app.storage.learning_candidate_store import load_recent_learning_candidates
from app.storage.mistake_memory_store import load_recent_mistake_memory
from app.storage.position_recheck_store import load_recent_position_rechecks
from app.storage.weekly_calibration_store import load_recent_weekly_calibrations

_log = logging.getLogger(__name__)

BannerMode = str   # "waiting" | "managing_position" | "contradiction" | "risk_alert" | "learning"


# ── Haber keyword setleri (FAZ 14 — news-aware headline) ──────────────────────

_KW_WAR = frozenset({
    "iran", "israel", "war", "missile", "helicopter", "attack", "hormuz",
    "hezbollah", "hamas", "drone", "strike", "bomb", "troops", "conflict",
    "invasion", "nuclear", "sanction", "military",
})
_KW_TRUMP  = frozenset({"trump", "white house", "tariff", "trade war"})
_KW_MACRO  = frozenset({"cpi", "fomc", "nfp", "fed rate", "inflation"})
_KW_CRYPTO = frozenset({"btc", "bitcoin", "eth", "ethereum", "crypto"})
_KW_METALS = frozenset({"gold", "silver", "xau", "xag"})
_KW_OIL    = frozenset({"oil", "brent", "crude", "opec"})
_KW_DXYVIX = frozenset({"dxy", "dollar index", "vix"})

_BEARISH_ACTIONS = frozenset({"SHORT", "AVOID", "SHORT_AWAIT"})
_BULLISH_ACTIONS = frozenset({"LONG", "LONG_AWAIT"})


# ── Haber sınıflandırma ────────────────────────────────────────────────────────

def _classify_headlines(news: list[dict]) -> dict:
    """
    Haber başlıklarını kategorize et.
    Returns: {war, trump, macro, crypto, metals, oil, dxy_vix, top_titles, has_news}
    """
    war = trump = macro = crypto = metals = oil = dxy_vix = False
    top_titles: list[str] = []

    high  = [n for n in news if str(n.get("relevance", "")).upper() == "HIGH"]
    mid   = [n for n in news if str(n.get("relevance", "")).upper() == "MEDIUM"]
    other = [n for n in news if n not in high and n not in mid]
    ordered = (high + mid + other)[:10]

    for n in ordered:
        title     = str(n.get("title") or "")
        title_low = title.lower()
        if title.strip() and len(top_titles) < 3:
            top_titles.append(title)
        if any(kw in title_low for kw in _KW_WAR):
            war = True
        if any(kw in title_low for kw in _KW_TRUMP):
            trump = True
        if any(kw in title_low for kw in _KW_MACRO):
            macro = True
        if any(kw in title_low for kw in _KW_CRYPTO):
            crypto = True
        if any(kw in title_low for kw in _KW_METALS):
            metals = True
        if any(kw in title_low for kw in _KW_OIL):
            oil = True
        if any(kw in title_low for kw in _KW_DXYVIX):
            dxy_vix = True

    return {
        "war": war, "trump": trump, "macro": macro,
        "crypto": crypto, "metals": metals, "oil": oil, "dxy_vix": dxy_vix,
        "top_titles": top_titles,
        "has_news": len(top_titles) > 0,
    }


def _asset_action_for(signals: list[dict], code: str) -> str:
    for s in signals:
        if str(s.get("asset_code") or "").upper() == code.upper():
            return str(s.get("asset_action") or "").upper()
    return ""


def _build_news_story(
    news_cls: dict,
    asset_signals: list[dict],
    macro_layer: dict,
) -> str:
    """
    Haber + fiyat teyidi sentezi — tek cümle.
    Spec kuralları sırayla uygulanır.
    Kaynak/haber yoksa boş string döner.
    """
    if not news_cls.get("has_news"):
        return ""

    brent_action  = _asset_action_for(asset_signals, "BRENT")
    btc_action    = _asset_action_for(asset_signals, "BTCUSD")
    eth_action    = _asset_action_for(asset_signals, "ETHUSD")
    gold_action   = _asset_action_for(asset_signals, "XAUUSD")
    silver_action = _asset_action_for(asset_signals, "XAGUSD")
    vix_action    = _asset_action_for(asset_signals, "VIX")

    brent_up    = brent_action in _BULLISH_ACTIONS
    brent_down  = brent_action in _BEARISH_ACTIONS
    vix_up      = vix_action in _BULLISH_ACTIONS
    crypto_down = (btc_action in _BEARISH_ACTIONS) or (eth_action in _BEARISH_ACTIONS)
    metals_down = (gold_action in _BEARISH_ACTIONS) and (silver_action in _BEARISH_ACTIONS)

    dxy_high = False
    m = re.search(r"\((\d+\.\d+)\)", str(macro_layer.get("dxy_signal") or ""))
    if m:
        dxy_high = float(m.group(1)) > 104

    risk_up = brent_up or vix_up or dxy_high

    # Kural 1: savaş + risk fiyatlaması teyit
    if news_cls["war"] and risk_up:
        return "Savaş başlığı risk fiyatlamasını canlı tutuyor; Brent/DXY/VIX yukarı baskısı var."

    # Kural 2: savaş + Brent düşüyor
    if news_cls["war"] and brent_down:
        return (
            "Haber akışı riskli ama Brent geri çekiliyor; "
            "piyasa şimdilik tam panik fiyatlamıyor."
        )

    # Kural 3: savaş var, fiyat teyidi zayıf
    if news_cls["war"]:
        return "Jeopolitik başlık var; Brent veya VIX'te güçlü teyit henüz yok."

    # Kural 4: kripto düşüyor
    if news_cls["crypto"] and crypto_down:
        return "BTC/ETH zayıf; risk iştahı kripto tarafında bozulmuş."

    # Kural 5: metaller birlikte düşüyor
    if news_cls["metals"] and metals_down:
        return "Gold/Silver birlikte zayıf; hedge talebi çözülüyor veya dolar baskısı artıyor."

    # Kural 6: Trump + DXY/VIX
    if news_cls["trump"] and (dxy_high or vix_up):
        return "Makro stres fiyatlaması canlı; Trump haberi DXY/VIX yukarı taşıyor."

    # Kural 7: CPI/FOMC/NFP haberi
    if news_cls["macro"]:
        return "Makro veri haberi var; piyasa Fed beklentisini yeniden fiyatlıyor olabilir."

    # Kural 8: enerji haberi + Brent yüksek
    if news_cls["oil"] and brent_up:
        return "Enerji haberi Brent'i yukarı taşıyor; maliyet/risk baskısı artabilir."

    # Kural 9: haber var fiyat teyidi yok
    return "Haber var, fakat fiyat teyidi zayıf; tek başına trade sebebi değil."


def _news_headline_short(news_cls: dict, asset_signals: list[dict], macro_layer: dict) -> str:
    """Headline'a inline eklenecek kısa özet (nokta/noktalı virgül öncesi). Yoksa boş."""
    if not news_cls.get("has_news"):
        return ""
    story = _build_news_story(news_cls, asset_signals, macro_layer)
    if not story:
        return ""
    short = re.split(r"[;.]", story)[0].strip()
    return short[:80]


# ── Veri toplama ──────────────────────────────────────────────────────────────

def _collect_context() -> dict[str, Any]:
    """
    Tüm store'lardan taze veri toplar.
    Her kaynak kendi hatasını sessizce yönetir — banner crash etmez.
    """
    ctx: dict[str, Any] = {
        "open_positions":    [],
        "anomaly_active":    False,
        "anomaly_reasons":   [],
        "latest_snapshot":   None,
        "prev_snapshot":     None,
        "snapshot_decision": None,
        "prev_decision":     None,
        "snapshot_report":   {},
        "latest_thesis":     None,
        "thesis_safe":       None,
        "thesis_issues":     [],
        "thesis_reasons":    [],
        "thesis_contradictions": [],
        "thesis_watchlist":  [],
        "thesis_market_view": {},
        "thesis_asset_bias": {},
        "latest_recheck":    None,
        "candidates":        [],
        "latest_memory":     None,
        "latest_calibration": None,
        "active_overrides":  [],
        # FAZ 14 — haber farkındalığı
        "news_headlines":    [],
        "asset_signals":     [],
        "macro_layer":       {},
        "news_classification": {},
        "now":               datetime.now(UTC).isoformat(),
    }

    # ── Paper trading ─────────────────────────────────────────────────────────
    try:
        from app.services.paper_trading_service import get_snapshot  # noqa: PLC0415
        snap = get_snapshot()
        ctx["open_positions"] = snap.get("open_positions") or []
        anomaly = snap.get("state_anomaly") or {}
        ctx["anomaly_active"]  = bool(anomaly.get("active", False))
        ctx["anomaly_reasons"] = anomaly.get("reasons") or []
    except Exception:
        _log.debug("agent_banner: paper_trading_service unavailable")

    # ── Hourly snapshots ──────────────────────────────────────────────────────
    try:
        snaps = load_recent_hourly_snapshots(limit=2)
        if snaps:
            ctx["latest_snapshot"]   = snaps[-1]
            report = snaps[-1].get("report") or {}
            ctx["snapshot_decision"] = report.get("decision")
            ctx["snapshot_report"]   = report
        if len(snaps) >= 2:
            ctx["prev_snapshot"] = snaps[-2]
            prev_report = snaps[-2].get("report") or {}
            ctx["prev_decision"] = prev_report.get("decision")
    except Exception:
        _log.debug("agent_banner: hourly_snapshot_store unavailable")

    # ── Agent thesis ──────────────────────────────────────────────────────────
    try:
        theses = load_recent_agent_theses(limit=1)
        if theses:
            t = theses[-1]
            ctx["latest_thesis"] = t
            sanity = t.get("thesis_sanity") or {}
            safe_val = sanity.get("safe_for_context")
            ctx["thesis_safe"]           = bool(safe_val) if safe_val is not None else None
            ctx["thesis_issues"]         = sanity.get("issues") or []
            ctx["thesis_reasons"]        = t.get("strongest_reasons") or []
            ctx["thesis_contradictions"] = t.get("main_contradictions") or []
            ctx["thesis_watchlist"]      = t.get("watchlist") or []
            ctx["thesis_market_view"]    = t.get("market_view") or {}
            ctx["thesis_asset_bias"]     = t.get("asset_bias") or {}
    except Exception:
        _log.debug("agent_banner: agent_thesis_store unavailable")

    # ── Position recheck ──────────────────────────────────────────────────────
    try:
        rechecks = load_recent_position_rechecks(limit=1)
        if rechecks:
            ctx["latest_recheck"] = rechecks[-1]
    except Exception:
        _log.debug("agent_banner: position_recheck_store unavailable")

    # ── Learning candidates ───────────────────────────────────────────────────
    try:
        ctx["candidates"] = load_recent_learning_candidates(limit=5)
    except Exception:
        _log.debug("agent_banner: learning_candidate_store unavailable")

    # ── Mistake memory ────────────────────────────────────────────────────────
    try:
        memories = load_recent_mistake_memory(limit=1)
        if memories:
            ctx["latest_memory"] = memories[-1]
    except Exception:
        _log.debug("agent_banner: mistake_memory_store unavailable")

    # ── Weekly calibration ────────────────────────────────────────────────────
    try:
        cals = load_recent_weekly_calibrations(limit=1)
        if cals:
            ctx["latest_calibration"] = cals[-1]
    except Exception:
        _log.debug("agent_banner: weekly_calibration_store unavailable")

    # ── Auto tune overrides ───────────────────────────────────────────────────
    try:
        overrides_data = read_overrides()
        overrides_map  = overrides_data.get("overrides") or {}
        for target, conditions in overrides_map.items():
            if not isinstance(conditions, dict):
                continue
            for condition, value in conditions.items():
                ctx["active_overrides"].append({
                    "target":    target,
                    "condition": condition,
                    "value":     value,
                })
    except Exception:
        _log.debug("agent_banner: auto_tune_store unavailable")

    # ── FAZ 14 — Haber sınıflandırması (snapshot_report'tan) ──────────────────
    _rep = ctx.get("snapshot_report") or {}
    ctx["news_headlines"] = list(_rep.get("news_headlines") or [])
    ctx["asset_signals"]  = list(_rep.get("asset_signals") or [])
    ctx["macro_layer"]    = dict(_rep.get("macro_layer") or {})
    if ctx["news_headlines"]:
        ctx["news_classification"] = _classify_headlines(ctx["news_headlines"])

    return ctx


# ── Mod belirleme ─────────────────────────────────────────────────────────────

def _detect_mode(ctx: dict[str, Any]) -> BannerMode:
    """
    Öncelik: risk_alert > contradiction > managing_position > learning > waiting
    """
    if ctx["anomaly_active"]:
        return "risk_alert"
    if ctx["thesis_safe"] is False:
        return "contradiction"
    if ctx["open_positions"]:
        return "managing_position"
    if ctx["candidates"]:
        return "learning"
    return "waiting"


# ── Top signals ───────────────────────────────────────────────────────────────

def _extract_top_signals(ctx: dict[str, Any], mode: BannerMode) -> list[str]:
    """En fazla 3 somut sinyal. Uydurma YOK."""
    signals: list[str] = []

    for reason in ctx["thesis_reasons"][:3]:
        if isinstance(reason, str) and reason.strip():
            signals.append(reason.strip())
        elif isinstance(reason, dict):
            text = reason.get("reason") or reason.get("text") or reason.get("description") or ""
            if text.strip():
                signals.append(str(text).strip())
        if len(signals) >= 3:
            break

    if len(signals) < 3 and ctx["latest_calibration"]:
        perf = (ctx["latest_calibration"].get("performance") or {})
        wr = perf.get("win_rate")
        pf = perf.get("profit_factor")
        if wr is not None:
            signals.append(f"Son kalibrasyon: win rate %{wr * 100:.0f}")
        if pf is not None and len(signals) < 3:
            signals.append(f"Profit factor {pf:.2f}")

    if not signals and ctx["snapshot_decision"]:
        signals.append(f"Son snapshot kararı: {ctx['snapshot_decision']}")

    if not signals:
        signals.append("kayıt yok")

    return signals[:3]


# ── Contradictions ────────────────────────────────────────────────────────────

def _extract_contradictions(ctx: dict[str, Any]) -> list[str]:
    """Thesis + advanced technical çelişkileri. Uydurma YOK."""
    result: list[str] = []
    for item in ctx["thesis_contradictions"][:2]:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
        elif isinstance(item, dict):
            msg = item.get("message") or item.get("text") or item.get("description") or ""
            if msg.strip():
                result.append(str(msg).strip())

    try:
        from app.services.advanced_technical_context import (  # noqa: PLC0415
            build_advanced_technical_context,
        )
        for pos in (ctx.get("open_positions") or [])[:3]:
            pair = (pos.get("pair") or "").upper()
            if not pair:
                continue
            adv = build_advanced_technical_context(pair, "")
            if not adv.get("available"):
                continue
            for c in adv.get("contradictions") or []:
                msg = f"[{pair}] {c}"
                if msg not in result:
                    result.append(msg)
            if len(result) >= 4:
                break
    except Exception:  # noqa: BLE001
        pass

    return result[:4]


# ── Watch next ────────────────────────────────────────────────────────────────

def _extract_watch_next(ctx: dict[str, Any]) -> list[str]:
    """Takip edilecek seviyeler/pariteler."""
    watches: list[str] = []

    for item in ctx["thesis_watchlist"][:3]:
        if isinstance(item, str):
            watches.append(item)
        elif isinstance(item, dict):
            pair = item.get("pair") or item.get("asset") or ""
            note = item.get("note") or item.get("reason") or ""
            if pair:
                watches.append(f"{pair}" + (f" ({note})" if note else ""))

    for pos in ctx["open_positions"][:2]:
        pair = pos.get("pair", "")
        side = pos.get("side", "")
        pnl  = pos.get("pnl_pct")
        if pair and f"{pair}" not in " ".join(watches):
            pnl_str = f" PnL {pnl:+.1f}%" if pnl is not None else ""
            watches.append(f"{pair} {side}{pnl_str} — pozisyon izle")

    if not watches and ctx["snapshot_decision"]:
        watches.append(f"Sinyal bekle — son karar: {ctx['snapshot_decision']}")
    return watches[:3]


# ── Position note ─────────────────────────────────────────────────────────────

def _build_position_note(ctx: dict[str, Any]) -> str | None:
    """Açık pozisyon varsa kısa recheck özeti."""
    if not ctx["open_positions"]:
        return None

    parts: list[str] = []
    for pos in ctx["open_positions"][:4]:
        pair  = pos.get("pair", "?")
        side  = pos.get("side", "?")
        entry = pos.get("entry_price")
        pnl   = pos.get("pnl_pct")
        entry_str = f"@{entry:.0f}" if entry is not None else ""
        pnl_str   = f" PnL {pnl:+.1f}%" if pnl is not None else ""
        parts.append(f"{pair} {side}{entry_str}{pnl_str}")

    recheck = ctx["latest_recheck"]
    if recheck:
        summary = recheck.get("summary") or {}
        rec = summary.get("recommendation") or summary.get("action") or ""
        if rec:
            parts.append(f"Recheck: {rec}")

    return " | ".join(parts) if parts else None


# ── Learning note ─────────────────────────────────────────────────────────────

def _build_learning_note(ctx: dict[str, Any]) -> str | None:
    """Learning candidate / memory / override notu."""
    parts: list[str] = []

    candidates = ctx["candidates"]
    if candidates:
        candidate_pairs = []
        for c in candidates[:3]:
            p = c.get("pair") or c.get("candidate_pair") or ""
            if p:
                candidate_pairs.append(p)
        if candidate_pairs:
            parts.append(f"{len(candidates)} öğrenme adayı: {', '.join(candidate_pairs)}")
        else:
            parts.append(f"{len(candidates)} öğrenme adayı takipte")

    memory = ctx["latest_memory"]
    if memory:
        final_summary = memory.get("final_summary") or {}
        lesson = final_summary.get("main_lesson") or ""
        if lesson:
            parts.append(f"Son ders: {lesson[:80]}")

    overrides = ctx["active_overrides"]
    if overrides:
        ov     = overrides[0]
        target = ov.get("target", "")
        cond   = ov.get("condition", "")
        val    = ov.get("value", "")
        if target:
            parts.append(f"Yeni işlemlerde {target} kuralı uygulanıyor ({cond}={val})")
        else:
            parts.append(f"{len(overrides)} auto tune override aktif")

    return "; ".join(parts) if parts else None


# ── Banner üreticileri (moda göre) ────────────────────────────────────────────

def _banner_risk_alert(ctx: dict[str, Any]) -> tuple[str, str]:
    reasons    = ctx["anomaly_reasons"]
    reason_str = reasons[0] if reasons else "bilinmiyor"
    open_count = len(ctx["open_positions"])
    headline = f"⚠️ Sistem Uyarısı — paper trading anomalisi aktif ({reason_str})"
    main_view = (
        f"Yeni işlem açılmıyor. Açık pozisyon sayısı: {open_count}. "
        "Anomali giderilmeden yeni trade alınmaz. "
        "Dashboard'da 'Onar' veya 'Sıfırla' kullan."
    )
    return headline, main_view


def _banner_contradiction(ctx: dict[str, Any]) -> tuple[str, str]:
    issues   = ctx["thesis_issues"]
    critical = [i for i in issues if i.get("severity") == "critical"]
    first    = critical[0] if critical else (issues[0] if issues else {})
    code     = first.get("code") or "bilinmiyor"
    msg      = first.get("message") or ""
    headline  = "⚡ Agent thesis güvenli context değil"
    main_view = f"Sanity fail — {code}: {msg}" if msg else f"Sanity fail — {code}"
    if not issues:
        main_view = "Thesis sanity kontrolü başarısız. Yeni snapshot bekleniyor."
    return headline, main_view


def _banner_managing_position(ctx: dict[str, Any]) -> tuple[str, str]:
    """
    Pozisyon yönetim modu.
    Haber varsa headline sadece pozisyon sayısı değildir.
    """
    positions    = ctx["open_positions"]
    news_cls     = ctx.get("news_classification") or {}
    asset_signals = ctx.get("asset_signals") or []
    macro_layer   = ctx.get("macro_layer") or {}
    news_short    = _news_headline_short(news_cls, asset_signals, macro_layer)

    if len(positions) == 1:
        p       = positions[0]
        pair    = p.get("pair", "?")
        side    = p.get("side", "?")
        pnl     = p.get("pnl_pct")
        pnl_str = f" PnL {pnl:+.1f}%" if pnl is not None else ""
        if news_short:
            headline = f"📊 {pair} {side}{pnl_str} yönetimde; {news_short}."
        else:
            headline = f"📊 {pair} {side}{pnl_str} — pozisyon yönetimde"
    else:
        pairs    = [p.get("pair", "?") for p in positions[:4]]
        pair_str = ", ".join(pairs)
        if news_short:
            headline = f"📊 {len(positions)} pozisyon ({pair_str}); {news_short}."
        else:
            headline = f"📊 {len(positions)} açık pozisyon — {pair_str}"

    view_parts: list[str] = []
    mv = ctx["thesis_market_view"]
    if mv:
        stance = mv.get("stance") or mv.get("regime") or mv.get("primary_bias") or ""
        if stance:
            view_parts.append(f"Piyasa duruşu: {stance}")

    recheck = ctx["latest_recheck"]
    if recheck:
        summary = recheck.get("summary") or {}
        rec     = summary.get("recommendation") or summary.get("action") or ""
        pair_r  = recheck.get("pair", "")
        if rec:
            view_parts.append(f"{pair_r} recheck: {rec}")

    if (ctx["prev_decision"] and ctx["snapshot_decision"]
            and ctx["prev_decision"] != ctx["snapshot_decision"]):
        view_parts.append(
            f"Snapshot kararı değişti: {ctx['prev_decision']} → {ctx['snapshot_decision']}"
        )
    elif ctx["snapshot_decision"]:
        view_parts.append(f"Son snapshot kararı: {ctx['snapshot_decision']}")

    main_view = ". ".join(view_parts) if view_parts else "Pozisyon takibi devam ediyor."
    return headline, main_view


def _banner_learning(ctx: dict[str, Any]) -> tuple[str, str]:
    """Öğrenme adayı izleme modu. Haber varsa headline'a eklenir."""
    candidates = ctx["candidates"]
    pairs: list[str] = []
    for c in candidates[:3]:
        p = c.get("pair") or c.get("candidate_pair") or ""
        if p:
            pairs.append(p)
    pair_str = ", ".join(pairs) if pairs else f"{len(candidates)} aday"

    news_cls     = ctx.get("news_classification") or {}
    asset_signals = ctx.get("asset_signals") or []
    macro_layer   = ctx.get("macro_layer") or {}
    news_short    = _news_headline_short(news_cls, asset_signals, macro_layer)

    if news_short:
        headline = f"🧠 {len(candidates)} öğrenme adayı ({pair_str}); {news_short}."
    else:
        headline = f"🧠 {len(candidates)} öğrenme adayı izleniyor: {pair_str}"

    view_parts: list[str] = []
    cal = ctx["latest_calibration"]
    if cal:
        perf = cal.get("performance") or {}
        wr   = perf.get("win_rate")
        if wr is not None:
            view_parts.append(f"Win rate: %{wr * 100:.0f}")
        eq = cal.get("sample", {}).get("evidence_quality") or ""
        if eq:
            view_parts.append(f"Kanıt kalitesi: {eq}")

    mv = ctx["thesis_market_view"]
    if mv:
        stance = mv.get("stance") or mv.get("regime") or mv.get("primary_bias") or ""
        if stance:
            view_parts.append(f"Piyasa duruşu: {stance}")

    main_view = ". ".join(view_parts) if view_parts else "Pozisyon yok, öğrenme takipte."
    return headline, main_view


def _banner_waiting(ctx: dict[str, Any]) -> tuple[str, str]:
    """
    Bekleme modu.
    Haber varsa → headline haberi yansıtır.
    Yoksa → thesis stance veya snapshot kararı.
    Yasak: "mixed", "piyasa izleniyor", "uygun sinyal bekliyorum".
    """
    news_cls     = ctx.get("news_classification") or {}
    asset_signals = ctx.get("asset_signals") or []
    macro_layer   = ctx.get("macro_layer") or {}
    news_short    = _news_headline_short(news_cls, asset_signals, macro_layer)

    view_parts: list[str] = []
    mv = ctx["thesis_market_view"]
    if mv:
        stance = mv.get("stance") or mv.get("regime") or mv.get("primary_bias") or ""
        if stance:
            view_parts.append(f"Piyasa duruşu: {stance}")
    if ctx["snapshot_decision"]:
        if ctx["prev_decision"] and ctx["prev_decision"] != ctx["snapshot_decision"]:
            view_parts.append(
                f"Karar değişti: {ctx['prev_decision']} → {ctx['snapshot_decision']}"
            )
        else:
            view_parts.append(f"Son karar: {ctx['snapshot_decision']}")

    if news_short:
        headline = f"🔍 Pozisyon yok — {news_short}."
    elif view_parts:
        headline = view_parts[0]
    else:
        headline = (
            "Thesis mevcut — sinyal bekleniyor" if ctx["latest_thesis"]
            else "kayıt yok"
        )

    main_view = ". ".join(view_parts) if view_parts else (
        "Uygun koşullar bekleniyor."
        if ctx["latest_thesis"]
        else "Henüz snapshot veya thesis kaydı yok."
    )
    return headline, main_view


# ── Ana builder ───────────────────────────────────────────────────────────────

def build_agent_banner() -> dict[str, Any]:
    """
    Tüm stored data'dan dinamik banner üretir.

    Canlı market/broker çağrısı yapmaz.
    Uydurma içerik üretmez — veri yoksa "kayıt yok" döner.
    """
    ctx  = _collect_context()
    mode = _detect_mode(ctx)

    if mode == "risk_alert":
        headline, main_view = _banner_risk_alert(ctx)
    elif mode == "contradiction":
        headline, main_view = _banner_contradiction(ctx)
    elif mode == "managing_position":
        headline, main_view = _banner_managing_position(ctx)
    elif mode == "learning":
        headline, main_view = _banner_learning(ctx)
    else:
        headline, main_view = _banner_waiting(ctx)

    # FAZ 13 — Event calendar + piyasa fikri
    event_ctx: dict[str, Any] = {}
    try:
        from app.services.event_calendar_context import (  # noqa: PLC0415
            build_event_calendar_context as _build_event_ctx,
        )
        event_ctx = _build_event_ctx(ctx.get("snapshot_report") or {})
    except Exception:  # noqa: BLE001
        _log.debug("agent_banner: event_calendar_context unavailable")

    # FAZ 14 — news_story
    news_cls      = ctx.get("news_classification") or {}
    asset_signals = ctx.get("asset_signals") or []
    macro_layer   = ctx.get("macro_layer") or {}
    news_story = ""
    try:
        news_story = _build_news_story(news_cls, asset_signals, macro_layer)
    except Exception:  # noqa: BLE001
        pass

    return {
        "mode":                mode,
        "headline":            headline,
        "main_view":           main_view,
        "top_signals":         _extract_top_signals(ctx, mode),
        "contradictions":      _extract_contradictions(ctx),
        "watch_next":          _extract_watch_next(ctx),
        "position_note":       _build_position_note(ctx),
        "learning_note":       _build_learning_note(ctx),
        "updated_at":          ctx["now"],
        "generated_at":        ctx["now"],
        "source_news_titles":  news_cls.get("top_titles") or [],
        "news_story":          news_story,
        # FAZ 13 — piyasa fikri alanları
        "market_thought":      event_ctx.get("market_thought", ""),
        "price_story":         event_ctx.get("price_story", ""),
        "event_story":         event_ctx.get("event_story", ""),
        "event_calendar_note": event_ctx.get("event_calendar_note", ""),
        "market_pricing_note": event_ctx.get("market_pricing_note", ""),
        "next_trigger":        event_ctx.get("next_trigger", ""),
    }
