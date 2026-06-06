#!/usr/bin/env python3
"""
E-YAY BrainChain — Otomatik Takvim Güncelleyici
Her Pazar çalıştır: LaunchAgent com.eyay.calendar.update (09:00)

Strateji:
  1. BLS tarihleri — 2026 TAMAMEN HARDCODED (bls.gov/schedule/2026/)
       CPI ve PPI tarihleri NFP'ye bağımlı DEĞİL; BLS'nin kendi takvimi vardır.
       Tatil günleri: NFP federal tatile denk gelirse BLS öne alır (4 Tem 2026 → NFP 2 Tem).
  2. FOMC — hardcoded 2026-2027 (Fed yıllık yayımlar)
       Güncelleme: yılda bir → https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
  3. BLS 2027 — yaklaşık formül (BLS resmi takvim yayımlandığında elle güncelle)
  4. Statik: Jackson Hole (3. haftanın Cuması = Powell konuşma günü)

Geçmiş olaylar (>7 gün) otomatik temizlenir.
Ücretsiz — API anahtarı gerektirmez.
"""
from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import yaml

REPO_ROOT     = Path(__file__).resolve().parents[1]
CALENDAR_PATH = REPO_ROOT / "config" / "event_calendar.yaml"

# ---------------------------------------------------------------------------
# BLS 2026 — HARDCODED
# Kaynak: https://www.bls.gov/schedule/2026/
# NFP  = Employment Situation (İstihdam Raporu)
# CPI  = Consumer Price Index (Tüketici Fiyat Endeksi)
# PPI  = Producer Price Index (Üretici Fiyat Endeksi)
#
# ★ CPI ve PPI tarihleri NFP'den türetilmez — BLS bağımsız takvimi var!
# ★ 4 Temmuz 2026 Cumartesi → federal tatil 3 Temmuz'da → BLS NFP'yi 2 Temmuz'a çekiyor
# ---------------------------------------------------------------------------

BLS_2026: list[tuple[str, str, str, str]] = [
    # (nfp_date,    cpi_date,    ppi_date,    data_label)
    ("2026-06-05", "2026-06-10", "2026-06-11", "Mayıs 2026"),       # BLS onaylı
    ("2026-07-02", "2026-07-14", "2026-07-15", "Haziran 2026"),     # ★ 4 Tem tatili → NFP 2 Tem
    ("2026-08-07", "2026-08-12", "2026-08-13", "Temmuz 2026"),      # BLS onaylı
    ("2026-09-04", "2026-09-11", "2026-09-10", "Ağustos 2026"),     # ★ CPI 11 Eyl, PPI 10 Eyl
    ("2026-10-02", "2026-10-07", "2026-10-08", "Eylül 2026"),       # BLS onaylı
    ("2026-11-06", "2026-11-12", "2026-11-13", "Ekim 2026"),        # ~ BLS onaylanacak
    ("2026-12-04", "2026-12-10", "2026-12-11", "Kasım 2026"),       # ~ BLS onaylanacak
]

# ---------------------------------------------------------------------------
# FOMC tarihleri — hardcoded 2026-2027
# Güncelleme: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
# ---------------------------------------------------------------------------

FOMC_DATES: list[tuple[str, str]] = [
    # (karar_tarihi, toplantı_başlangıcı)
    # 2026
    ("2026-01-29", "2026-01-28"),   # Ocak
    ("2026-03-19", "2026-03-18"),   # Mart
    ("2026-05-07", "2026-04-29"),   # Nisan-Mayıs (3 günlük)
    ("2026-06-17", "2026-06-16"),   # Haziran
    ("2026-07-29", "2026-07-28"),   # Temmuz
    ("2026-09-16", "2026-09-15"),   # Eylül
    ("2026-10-28", "2026-10-27"),   # Ekim
    ("2026-12-16", "2026-12-15"),   # Aralık
    # 2027 (yaklaşık — Fed 2027 takvimini açıkladığında güncelle)
    ("2027-02-03", "2027-02-02"),
    ("2027-03-17", "2027-03-16"),
    ("2027-04-28", "2027-04-27"),
    ("2027-06-16", "2027-06-15"),
    ("2027-07-28", "2027-07-27"),
    ("2027-09-15", "2027-09-14"),
    ("2027-10-27", "2027-10-26"),
    ("2027-12-15", "2027-12-14"),
]

# ---------------------------------------------------------------------------
# Ay adları (Türkçe)
# ---------------------------------------------------------------------------

_TR = {
    1:"Ocak", 2:"Şubat", 3:"Mart", 4:"Nisan", 5:"Mayıs", 6:"Haziran",
    7:"Temmuz", 8:"Ağustos", 9:"Eylül", 10:"Ekim", 11:"Kasım", 12:"Aralık",
}

def _tr_month(m: int) -> str:
    return _TR.get(m, str(m))

# ---------------------------------------------------------------------------
# İlk Cuma (BLS 2027+ için yaklaşık formül — tatil kuralı basit)
# ---------------------------------------------------------------------------

def first_friday(year: int, month: int) -> date:
    """Ayın ilk Cumasını döndürür. Federal tatil kontrolü YOK — 2027+ için yaklaşık."""
    for day in range(1, 8):
        d = date(year, month, day)
        if d.weekday() == 4:
            return d
    raise ValueError(f"No Friday in first week of {year}-{month:02d}")

# ---------------------------------------------------------------------------
# BLS olayları — 2026 hardcoded, 2027+ yaklaşık formül
# ---------------------------------------------------------------------------

def generate_bls_events(months_extra: int = 2) -> list[dict]:
    """
    2026 için BLS resmi takviminden hardcoded tarihleri kullanır.
    2027 ve sonrası için basit ilk-Cuma formülü (yaklaşık).
    """
    today  = date.today()
    cutoff = today + timedelta(days=120 + months_extra * 30)
    events: list[dict] = []

    # ── 2026 hardcoded ────────────────────────────────────────────────────
    for nfp_str, cpi_str, ppi_str, data_label in BLS_2026:
        nfp_date = date.fromisoformat(nfp_str)
        cpi_date = date.fromisoformat(cpi_str)
        ppi_date = date.fromisoformat(ppi_str)

        # Yayın ayı ID'si (nfp_date'in yıl-ay'ı)
        rel_label = f"{nfp_date.year}_{nfp_date.month:02d}"

        # 7 günden eski ve çok uzak tarihleri atla
        for ev_date, ev_type, importance, expectation, impact in [
            (nfp_date, "nfp", "HIGH",
             "08:30 ET — BLS resmi takvim",
             "Güçlü → Fed kesmez DXY↑ | Zayıf → resesyon korkusu risk-off"),
            (cpi_date, "cpi", "CRITICAL",
             "08:30 ET — BLS resmi takvim",
             "Yüksek → DXY↑ BTC↓ Altın↓ | Düşük → BTC↑ Altın↑ hisse↑"),
            (ppi_date, "ppi", "MEDIUM",
             "08:30 ET — BLS resmi takvim",
             "Yüksek gelirse enflasyon beklentileri yükselir"),
        ]:
            days_delta = (ev_date - today).days
            if days_delta < -7 or ev_date > cutoff:
                continue

            name_map = {
                "nfp": f"ABD İstihdam / NFP ({data_label})",
                "cpi": f"ABD CPI ({data_label})",
                "ppi": f"ABD PPI ({data_label})",
            }

            events.append({
                "id":            f"{ev_type}_{rel_label}",
                "date":          ev_date.isoformat(),
                "name":          name_map[ev_type],
                "category":      "MACRO",
                "importance":    importance,
                "expectation":   expectation,
                "market_impact": impact,
            })

    # ── 2027+ yaklaşık formül ─────────────────────────────────────────────
    # BLS 2027 resmi takvim yayımlandığında BLS_2026 benzeri bir liste ekle
    for delta_m in range(1, 13):
        release_month = today.month + delta_m
        release_year  = today.year + (release_month - 1) // 12
        release_month = ((release_month - 1) % 12) + 1

        if release_year < 2027:
            continue  # 2026 zaten hardcoded

        nfp_date = first_friday(release_year, release_month)
        if nfp_date > cutoff:
            break

        # Veri ayı
        dm, dy = (release_month - 1, release_year) if release_month > 1 else (12, release_year - 1)
        data_label = f"{_tr_month(dm)} {dy}"
        rel_label  = f"{release_year}_{release_month:02d}"

        # 2027 için CPI/PPI NFP+5/+6 yaklaşık (BLS takvimi açıklandığında düzelt)
        cpi_approx = nfp_date + timedelta(days=5)
        ppi_approx = nfp_date + timedelta(days=6)

        for ev_date, ev_type, importance, impact in [
            (nfp_date,  "nfp", "HIGH",     "Güçlü → Fed kesmez DXY↑ | Zayıf → resesyon korkusu risk-off"),
            (cpi_approx,"cpi", "CRITICAL", "Yüksek → DXY↑ BTC↓ Altın↓ | Düşük → BTC↑ Altın↑ hisse↑"),
            (ppi_approx,"ppi", "MEDIUM",   "Yüksek gelirse enflasyon beklentileri yükselir"),
        ]:
            days_delta = (ev_date - today).days
            if days_delta < -7:
                continue

            name_map = {
                "nfp": f"ABD İstihdam / NFP ({data_label})",
                "cpi": f"ABD CPI ({data_label}) [~yaklaşık]",
                "ppi": f"ABD PPI ({data_label}) [~yaklaşık]",
            }
            exp_map = {
                "nfp": "08:30 ET — İlk Cuma (2027 BLS takvimi açıklandığında güncelle)",
                "cpi": "08:30 ET — YAKLAŞIK, BLS 2027 resmi tarihi kontrol et",
                "ppi": "08:30 ET — YAKLAŞIK, BLS 2027 resmi tarihi kontrol et",
            }

            events.append({
                "id":            f"{ev_type}_{rel_label}",
                "date":          ev_date.isoformat(),
                "name":          name_map[ev_type],
                "category":      "MACRO",
                "importance":    importance,
                "expectation":   exp_map[ev_type],
                "market_impact": impact,
            })

    return events


# ---------------------------------------------------------------------------
# FOMC olayları (120 gün içindekiler)
# ---------------------------------------------------------------------------

def generate_fomc_events() -> list[dict]:
    today  = date.today()
    cutoff = today + timedelta(days=120)
    events: list[dict] = []

    for decision_str, _ in FOMC_DATES:
        decision = date.fromisoformat(decision_str)
        if decision < today - timedelta(days=7) or decision > cutoff:
            continue

        m, y      = decision.month, decision.year
        label     = f"{_tr_month(m)} {y}"
        rel_label = f"{y}_{m:02d}"
        minutes   = decision + timedelta(days=21)

        events += [
            {
                "id":            f"fomc_{rel_label}",
                "date":          decision_str,
                "name":          f"FOMC Faiz Kararı ({label})",
                "category":      "FED",
                "importance":    "CRITICAL",
                "expectation":   "14:00 ET — basın toplantısı 14:30 ET",
                "market_impact": "Hawkish sürpriz → DXY↑ BTC↓ | Dovish pivot → BTC↑ Altın↑",
            },
            {
                "id":            f"fomc_minutes_{rel_label}",
                "date":          minutes.isoformat(),
                "name":          f"FOMC Tutanakları ({label} kararı)",
                "category":      "FED",
                "importance":    "MEDIUM",
                "expectation":   f"{decision_str} kararı detayları (karar+21g)",
                "market_impact": "Şahin ton → DXY↑ | Güvercin ipuçları → risk iştahı açılır",
            },
        ]

    return events


# ---------------------------------------------------------------------------
# Statik olaylar: Jackson Hole
# Tarih = 3. haftanın CUMASII = Powell yıllık politika konuşması
# (Sempozyum Per-Cmt sürer; piyasalar için kritik an Cuma sabahı)
# ---------------------------------------------------------------------------

def generate_static_events() -> list[dict]:
    today  = date.today()
    year   = today.year
    events: list[dict] = []

    for y in (year, year + 1):
        # Ağustos'un ilk Perşembesi
        aug_1     = date(y, 8, 1)
        first_thu = aug_1 + timedelta(days=(3 - aug_1.weekday()) % 7)
        # 3. Perşembe = sempozyum açılışı; 3. Cuma = Powell konuşması
        jh_fri    = first_thu + timedelta(weeks=2, days=1)

        events.append({
            "id":            f"jackson_hole_{y}",
            "date":          jh_fri.isoformat(),
            "name":          f"Jackson Hole — Powell Konuşması ({y})",
            "category":      "FED",
            "importance":    "CRITICAL",
            "expectation":   f"~10:00 ET Cuma — Powell yıllık politika konuşması (sempozyum 3 gün)",
            "market_impact": "Pivot ipucu → tüm riskli varlıklar↑ | Şahin ton → geneli↓ DXY↑",
        })

    return events


# ---------------------------------------------------------------------------
# YAML yazıcı
# ---------------------------------------------------------------------------

def _keep_manual_events(old_events: list[dict], new_ids: set[str]) -> list[dict]:
    """_source: manual etiketli olayları koru."""
    today = date.today()
    kept  = []
    for ev in old_events:
        if ev.get("_source") == "manual" and ev.get("id") not in new_ids:
            try:
                if date.fromisoformat(ev.get("date", "")) >= today - timedelta(days=7):
                    kept.append(ev)
            except ValueError:
                pass
    return kept


def update_yaml(all_events: list[dict], dry_run: bool = False) -> None:
    today = date.today()

    old_events: list[dict] = []
    if CALENDAR_PATH.exists():
        try:
            data = yaml.safe_load(CALENDAR_PATH.read_text(encoding="utf-8")) or {}
            old_events = data.get("events", [])
        except Exception:
            pass

    new_ids  = {ev["id"] for ev in all_events}
    manual   = _keep_manual_events(old_events, new_ids)
    merged   = manual + all_events

    # 7 günden eski geçmişi temizle, sırala
    cutoff_str = (today - timedelta(days=7)).isoformat()
    merged = [e for e in merged if e.get("date", "") >= cutoff_str]
    merged.sort(key=lambda e: e.get("date", ""))

    # Aynı ID varsa en yenisi kazanır
    seen: dict[str, dict] = {}
    for ev in merged:
        seen[ev["id"]] = ev
    merged = sorted(seen.values(), key=lambda e: e.get("date", ""))

    # YAML metni oluştur
    lines = [
        "# ---------------------------------------------------------------------------",
        "# E-YAY BrainChain — Olay Takvimi (Catalyst Calendar)",
        f"# Son güncelleme: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        "# OTOMATİK: scripts/update_event_calendar.py  (her Pazar 09:00)",
        "# Manuel eklenti: _source: manual ekle",
        "# BLS 2026 tarihleri HARDCODED — kaynak: bls.gov/schedule/2026/",
        "# FOMC tarihleri HARDCODED — kaynak: federalreserve.gov/monetarypolicy/fomccalendars.htm",
        "# BLS 2027 tarihleri [~yaklaşık] — BLS takvim yayımlandığında güncelle",
        "# ---------------------------------------------------------------------------",
        "",
        "events:",
    ]

    cur_ym = None
    for ev in merged:
        ym = ev.get("date", "")[:7]
        if ym != cur_ym:
            cur_ym = ym
            lines.append(f"\n  # ─── {ym} {'─' * 50}")

        lines.append("")
        lines.append(f"  - id: \"{ev.get('id','')}\"")
        for key in ("date", "name", "category", "importance", "expectation", "market_impact"):
            val = ev.get(key, "")
            if val:
                safe = str(val).replace('"', "'")
                lines.append(f"    {key}: \"{safe}\"")
        if ev.get("_source"):
            lines.append(f"    _source: \"{ev['_source']}\"")

    output = "\n".join(lines) + "\n"

    if dry_run:
        print("─── DRY-RUN çıktısı ───")
        print(output)
        print(f"\n[{len(merged)} etkinlik]")
        return

    CALENDAR_PATH.write_text(output, encoding="utf-8")
    print(f"✓ {CALENDAR_PATH.name} güncellendi — {len(merged)} etkinlik")
    for ev in merged:
        delta = (date.fromisoformat(ev["date"]) - today).days
        approx = " [~]" if "[~" in ev.get("name", "") else ""
        print(f"  {ev['date']} ({delta:+d}g){approx}  {ev['name']}")


# ---------------------------------------------------------------------------
# Cron / LaunchAgent kurulumu
# ---------------------------------------------------------------------------

def install_cron() -> None:
    import subprocess
    venv_python = REPO_ROOT / ".venv" / "bin" / "python3"
    script_path = REPO_ROOT / "scripts" / "update_event_calendar.py"
    cron_line   = f"0 9 * * 0 {venv_python} {script_path} >> /tmp/eyay_calendar.log 2>&1"

    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = result.stdout if result.returncode == 0 else ""

    if str(script_path) in existing:
        print("✓ Cron zaten kurulu")
        return

    new_cron = existing.rstrip() + f"\n{cron_line}\n"
    proc = subprocess.run(["crontab", "-"], input=new_cron, text=True)
    if proc.returncode == 0:
        print(f"✓ Cron kuruldu: {cron_line}")
    else:
        print(f"✗ Cron kurulamadı — LaunchAgent kullan (zaten kurulu): ~/Library/LaunchAgents/com.eyay.calendar.update.plist")


# ---------------------------------------------------------------------------
# Ana akış
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="E-YAY takvim güncelleyici")
    parser.add_argument("--dry-run",      action="store_true", help="Dosyayı değiştirmeden göster")
    parser.add_argument("--install-cron", action="store_true", help="macOS crontab'a ekle")
    args = parser.parse_args()

    if args.install_cron:
        install_cron()
        return

    print(f"E-YAY Takvim Güncelleyici — {date.today()}")

    bls_events  = generate_bls_events()
    print(f"  BLS (hardcoded 2026 + yaklaşık 2027): {len(bls_events)} etkinlik")

    fomc_events = generate_fomc_events()
    print(f"  FOMC (hardcoded): {len(fomc_events)} etkinlik")

    static      = generate_static_events()
    print(f"  Statik (Jackson Hole): {len(static)} etkinlik")

    all_events  = bls_events + fomc_events + static
    update_yaml(all_events, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
