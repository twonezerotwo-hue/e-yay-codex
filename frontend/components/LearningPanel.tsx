"use client";

import { useEffect, useState } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────

interface CalibrationPerf {
  win_rate:       number | null;
  profit_factor:  number | null;
  expectancy_usd: number | null;
}

interface LatestCalibration {
  calibration_id:   string | null;
  created_at:       string | null;
  lookback_days:    number | null;
  performance:      CalibrationPerf;
  evidence_quality: string | null;
}

interface ActiveOverride {
  target:       string;
  condition:    string;
  value:        number | boolean;
  last_updated: string | null;
}

interface LatestAdjustment {
  adjustment_id:         string | null;
  status:                string | null;
  target:                string | null;
  condition:             string | null;
  old_value:             number | boolean | null;
  new_value:             number | boolean | null;
  source_calibration_id: string | null;
  created_at:            string | null;
}

interface LatestMemory {
  memory_id:    string | null;
  pair:         string | null;
  result:       string | null;   // "WIN" | "LOSS" | "BREAK_EVEN"
  final_labels: string[];
  main_lesson:  string | null;
  created_at:   string | null;
}

interface Safety {
  decision_permission:    string;
  execution_mode:         string;
  broker_permission:      string;
  live_execution_allowed: boolean;
  override_scope:         string;
}

interface LearningSummary {
  latest_calibration: LatestCalibration | null;
  active_overrides:   ActiveOverride[];
  latest_adjustment:  LatestAdjustment | null;
  latest_memory:      LatestMemory | null;
  safety:             Safety;
}

// ── Küçük yardımcı bileşenler ─────────────────────────────────────────────────

function SafeChip({ label }: { label: string }) {
  return (
    <span className="inline-block text-[8px] font-mono font-bold px-1.5 py-0.5 rounded border
                     border-emerald-800/50 bg-emerald-950/30 text-emerald-400 uppercase tracking-wider">
      {label}
    </span>
  );
}

function EmptyNote({ text }: { text: string }) {
  return (
    <p className="text-[10px] font-mono text-eyay-faint italic py-0.5">{text}</p>
  );
}

function Accordion({
  title,
  badge,
  defaultOpen = false,
  children,
}: {
  title: string;
  badge?: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-eyay-border/60 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2
                   hover:bg-eyay-raised/40 transition-colors text-left"
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-[10px] font-mono font-bold text-eyay-text uppercase tracking-wider truncate">
            {title}
          </span>
          {badge}
        </div>
        <span className={`text-eyay-faint text-xs shrink-0 transition-transform ${open ? "rotate-180" : ""}`}>
          ▾
        </span>
      </button>
      {open && (
        <div className="px-3 pb-3 pt-1 border-t border-eyay-border/40 space-y-1">
          {children}
        </div>
      )}
    </div>
  );
}

function Row({ label, value, cls }: { label: string; value: React.ReactNode; cls?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2 text-[10px] font-mono">
      <span className="text-eyay-faint shrink-0">{label}</span>
      <span className={`text-right truncate ${cls ?? "text-eyay-text"}`}>{value}</span>
    </div>
  );
}

function shortId(id: string | null | undefined): string {
  if (!id) return "—";
  return id.slice(0, 8) + "…";
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("tr-TR", {
      month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso.slice(0, 16).replace("T", " ");
  }
}

function pct(n: number | null | undefined): string {
  if (n == null) return "—";
  return `%${(n * 100).toFixed(1)}`;
}

function num2(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toFixed(2);
}

function usd(n: number | null | undefined): string {
  if (n == null) return "—";
  const s = Math.abs(n).toFixed(0);
  return `${n >= 0 ? "+" : "-"}$${s}`;
}

// ── Evidence quality badge ─────────────────────────────────────────────────

function EvidenceBadge({ quality }: { quality: string | null }) {
  const map: Record<string, { cls: string; label: string }> = {
    full:    { cls: "border-emerald-700/60 text-emerald-300", label: "Güçlü Kanıt" },
    mixed:   { cls: "border-amber-700/60 text-amber-300",    label: "Karma Kanıt" },
    limited: { cls: "border-red-700/60 text-red-300",        label: "Sınırlı Kanıt" },
  };
  if (!quality) return null;
  const m = map[quality] ?? { cls: "border-eyay-border text-eyay-faint", label: quality };
  return (
    <span className={`text-[8px] font-mono font-bold px-1.5 py-0.5 rounded border uppercase tracking-wider ${m.cls}`}>
      {m.label}
    </span>
  );
}

// ── Result badge ──────────────────────────────────────────────────────────────

function ResultBadge({ result }: { result: string | null }) {
  const map: Record<string, string> = {
    WIN:        "border-emerald-700/60 text-emerald-300",
    LOSS:       "border-red-700/60 text-red-300",
    BREAK_EVEN: "border-amber-700/60 text-amber-300",
  };
  if (!result) return null;
  const cls = map[result] ?? "border-eyay-border text-eyay-faint";
  return (
    <span className={`text-[8px] font-mono font-bold px-1.5 py-0.5 rounded border uppercase tracking-wider ${cls}`}>
      {result}
    </span>
  );
}

// ── Status badge (adjustment) ─────────────────────────────────────────────────

function AdjStatusBadge({ status }: { status: string | null }) {
  if (!status) return null;
  const cls =
    status === "applied"
      ? "border-sky-700/60 text-sky-300"
      : status === "rolled_back"
      ? "border-amber-700/60 text-amber-300"
      : "border-eyay-border text-eyay-faint";
  const label = status === "applied" ? "Uygulandı" : status === "rolled_back" ? "Geri Alındı" : status;
  return (
    <span className={`text-[8px] font-mono font-bold px-1.5 py-0.5 rounded border uppercase tracking-wider ${cls}`}>
      {label}
    </span>
  );
}

// ── Bölüm 1: Calibration ──────────────────────────────────────────────────────

function CalibrationSection({ cal }: { cal: LatestCalibration | null }) {
  const perfOk = (n: number | null) =>
    n != null && n > 0 ? "text-emerald-300" : "text-eyay-faint";

  return (
    <Accordion
      title="Son Haftalık Kalibrasyon"
      badge={cal ? <EvidenceBadge quality={cal.evidence_quality} /> : undefined}
    >
      {!cal ? (
        <EmptyNote text="Henüz kalibrasyon raporu yok" />
      ) : (
        <>
          <Row label="Win Rate"       value={pct(cal.performance.win_rate)}
               cls={perfOk(cal.performance.win_rate)} />
          <Row label="Profit Factor"  value={num2(cal.performance.profit_factor)}
               cls={perfOk(cal.performance.profit_factor)} />
          <Row label="Expectancy"     value={usd(cal.performance.expectancy_usd)}
               cls={perfOk(cal.performance.expectancy_usd)} />
          <Row label="Lookback"       value={cal.lookback_days != null ? `${cal.lookback_days} gün` : "—"} />
          <Row label="Tarih"          value={fmtDate(cal.created_at)} />
          <Row label="ID"             value={shortId(cal.calibration_id)} />
        </>
      )}
    </Accordion>
  );
}

// ── Bölüm 2: Aktif Override'lar ───────────────────────────────────────────────

function OverridesSection({ overrides }: { overrides: ActiveOverride[] }) {
  const badge = overrides.length > 0
    ? <span className="text-[8px] font-mono font-bold px-1.5 py-0.5 rounded border
                        border-sky-700/60 bg-sky-950/30 text-sky-300 uppercase tracking-wider">
        {overrides.length} aktif
      </span>
    : undefined;

  return (
    <Accordion title="Aktif Auto Tune Override'ları" badge={badge}>
      {/* Sabit bilgi satırı — her zaman görünür */}
      <p className="text-[9px] font-mono text-sky-300/80 italic mb-1 leading-snug">
        Auto Tune aktif ama sadece paper trading size modifier olarak çalışıyor.
        Yön değiştirmez, trade açmaz.
      </p>
      {overrides.length === 0 ? (
        <EmptyNote text="Aktif override yok" />
      ) : (
        overrides.map((ov, i) => (
          <div
            key={i}
            className="rounded border border-eyay-border/40 bg-eyay-raised/30 px-2 py-1.5 space-y-1"
          >
            <Row label="Hedef"    value={ov.target} />
            <Row label="Koşul"    value={ov.condition} />
            <Row
              label="Değer"
              value={typeof ov.value === "boolean" ? (ov.value ? "açık" : "kapalı") : String(ov.value)}
              cls="text-sky-300 font-bold"
            />
            <Row label="Güncelleme" value={fmtDate(ov.last_updated)} />
            <div className="flex gap-1 pt-0.5">
              <SafeChip label="PAPER_SAFE" />
              <SafeChip label="BROKER_NOT_CONNECTED" />
            </div>
          </div>
        ))
      )}
    </Accordion>
  );
}

// ── Bölüm 3: Son Adjustment ───────────────────────────────────────────────────

function AdjustmentSection({ adj }: { adj: LatestAdjustment | null }) {
  return (
    <Accordion
      title="Son Auto Tune Değişikliği"
      badge={adj ? <AdjStatusBadge status={adj.status} /> : undefined}
    >
      {!adj ? (
        <EmptyNote text="Henüz auto-tune değişikliği yok" />
      ) : (
        <>
          <Row label="Hedef"   value={adj.target ?? "—"} />
          <Row label="Koşul"   value={adj.condition ?? "—"} />
          <Row label="Eski"    value={adj.old_value != null ? String(adj.old_value) : "—"} />
          <Row
            label="Yeni"
            value={adj.new_value != null ? String(adj.new_value) : "—"}
            cls="text-sky-300 font-bold"
          />
          <Row label="Kalibrasyon" value={shortId(adj.source_calibration_id)} />
          <Row label="Tarih"       value={fmtDate(adj.created_at)} />
          <Row label="ID"          value={shortId(adj.adjustment_id)} />
        </>
      )}
    </Accordion>
  );
}

// ── Bölüm 4: Son Öğrenme Kaydı ────────────────────────────────────────────────

function MemorySection({ mem }: { mem: LatestMemory | null }) {
  return (
    <Accordion
      title="Son Öğrenme Kaydı"
      badge={mem ? <ResultBadge result={mem.result} /> : undefined}
    >
      {!mem ? (
        <EmptyNote text="Henüz öğrenme kaydı yok" />
      ) : (
        <>
          <Row label="Parite" value={mem.pair ?? "—"} />
          <Row label="Tarih"  value={fmtDate(mem.created_at)} />
          {mem.main_lesson && (
            <p className="text-[10px] font-mono text-eyay-dim italic leading-snug mt-0.5 line-clamp-3">
              {mem.main_lesson}
            </p>
          )}
          {mem.final_labels.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {mem.final_labels.slice(0, 4).map((lbl) => (
                <span
                  key={lbl}
                  className="text-[8px] font-mono px-1.5 py-0.5 rounded border
                             border-eyay-border/60 text-eyay-faint"
                >
                  {lbl}
                </span>
              ))}
            </div>
          )}
        </>
      )}
    </Accordion>
  );
}

// ── Bölüm 5: Güvenlik satırı ──────────────────────────────────────────────────

function SafetySection({ safety }: { safety: Safety }) {
  return (
    <Accordion title="Sistem Güvenlik Durumu">
      <p className="text-[9px] font-mono text-eyay-faint italic mb-1 leading-snug">
        {safety.override_scope}
      </p>
      <div className="flex flex-wrap gap-1">
        <SafeChip label={safety.decision_permission} />
        <SafeChip label={safety.execution_mode} />
        <SafeChip label={safety.broker_permission} />
        <SafeChip label={`LIVE_EXEC: ${safety.live_execution_allowed ? "ON" : "OFF"}`} />
      </div>
    </Accordion>
  );
}

// ── Ana bileşen ───────────────────────────────────────────────────────────────

const POLL_MS = 60_000;  // 1 dakika — statik öğrenme verileri sık değişmez

export default function LearningPanel() {
  const [summary, setSummary] = useState<LearningSummary | null>(null);
  const [error,   setError]   = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await fetch("/api/backend/learning/summary", { cache: "no-store" });
        if (!res.ok) {
          if (!cancelled) setError(`HTTP ${res.status}`);
          return;
        }
        const data: LearningSummary = await res.json();
        if (!cancelled) {
          setSummary(data);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(String(e).slice(0, 80));
      }
    }

    load();
    const t = setInterval(load, POLL_MS);
    return () => { cancelled = true; clearInterval(t); };
  }, []);

  return (
    <div className="bg-eyay-surface rounded-2xl border border-eyay-border shadow-card overflow-hidden">
      {/* Başlık */}
      <div className="px-5 py-3 border-b border-eyay-border flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-2xs text-eyay-blue uppercase tracking-widest font-semibold">
            Öğrenme & Auto-Tune
          </p>
          <p className="text-[11px] text-eyay-faint mt-0.5 leading-snug">
            Sistem ne öğrendi · Hangi override aktif
          </p>
        </div>
        {summary && (
          <div className="flex gap-1 shrink-0">
            <SafeChip label="PAPER_SAFE" />
          </div>
        )}
      </div>

      <div className="px-4 py-3 space-y-2">
        {/* Yükleniyor */}
        {!summary && !error && (
          <p className="text-[10px] font-mono text-eyay-faint italic py-2 text-center">
            Yükleniyor…
          </p>
        )}

        {/* Hata */}
        {error && (
          <p className="text-[10px] font-mono text-red-300 italic py-2 text-center">
            Yüklenemedi: {error}
          </p>
        )}

        {summary && (
          <>
            <CalibrationSection  cal={summary.latest_calibration} />
            <OverridesSection    overrides={summary.active_overrides} />
            <AdjustmentSection   adj={summary.latest_adjustment} />
            <MemorySection       mem={summary.latest_memory} />
            <SafetySection       safety={summary.safety} />
          </>
        )}
      </div>
    </div>
  );
}
