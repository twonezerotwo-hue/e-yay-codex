"use client";

import { useEffect, useState } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────

type CheckStatus = "ok" | "degraded" | "fail";

interface HealthCheck {
  name: string;
  status: CheckStatus;
  message: string;
}

interface Safety {
  decision_permission: string;
  execution_mode: string;
  broker_permission: string;
  live_execution_allowed: boolean;
}

interface SystemHealthSummary {
  status: CheckStatus;
  checks: HealthCheck[];
  safety: Safety;
}

// ── Küçük yardımcı bileşenler ─────────────────────────────────────────────────

function StatusChip({ status }: { status: string }) {
  const map: Record<string, string> = {
    ok:       "border-emerald-700/60 bg-emerald-950/30 text-emerald-400",
    degraded: "border-amber-700/60  bg-amber-950/30  text-amber-400",
    fail:     "border-red-700/60    bg-red-950/30    text-red-400",
  };
  const cls = map[status] ?? "border-eyay-border bg-transparent text-eyay-faint";
  return (
    <span
      className={`inline-block text-[8px] font-mono font-bold px-1.5 py-0.5 rounded border uppercase tracking-wider ${cls}`}
    >
      {status}
    </span>
  );
}

function SafeChip({ label }: { label: string }) {
  return (
    <span className="inline-block text-[8px] font-mono font-bold px-1.5 py-0.5 rounded border
                     border-emerald-800/50 bg-emerald-950/30 text-emerald-400 uppercase tracking-wider">
      {label}
    </span>
  );
}

function StatusDot({ status }: { status: string }) {
  const cls =
    status === "ok"       ? "text-emerald-400" :
    status === "fail"     ? "text-red-400" :
    status === "degraded" ? "text-amber-400" :
                            "text-eyay-faint";
  return <span className={`shrink-0 ${cls} leading-none`}>●</span>;
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
        <span
          className={`text-eyay-faint text-xs shrink-0 transition-transform ${open ? "rotate-180" : ""}`}
        >
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

// ── Check adı → okunabilir etiket ─────────────────────────────────────────────

const CHECK_LABELS: Record<string, string> = {
  scheduler:     "Scheduler",
  snapshot:      "Snapshot",
  thesis:        "Thesis",
  paper_trading: "Paper Trading",
  auto_tune:     "Auto Tune",
};

// ── Bölüm: Check satırları ────────────────────────────────────────────────────

function ChecksSection({ checks }: { checks: HealthCheck[] }) {
  return (
    <div className="space-y-0.5">
      {checks.map((c) => (
        <div
          key={c.name}
          className="flex items-start gap-2 text-[10px] font-mono py-1 px-1"
        >
          <StatusDot status={c.status} />
          <span className="shrink-0 w-24 text-eyay-faint capitalize">
            {CHECK_LABELS[c.name] ?? c.name}
          </span>
          <span className="text-eyay-text leading-snug flex-1 min-w-0 break-words">
            {c.message}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Bölüm: Safety ────────────────────────────────────────────────────────────

function SafetySection({ safety }: { safety: Safety }) {
  return (
    <Accordion title="Safety">
      <div className="flex flex-wrap gap-1 pt-0.5">
        <SafeChip label={safety.decision_permission} />
        <SafeChip label={safety.execution_mode} />
        <SafeChip label={safety.broker_permission} />
        <SafeChip label={safety.live_execution_allowed ? "live:on" : "live:off"} />
      </div>
    </Accordion>
  );
}

// ── Panel ─────────────────────────────────────────────────────────────────────

export default function SystemHealthPanel() {
  const [data, setData] = useState<SystemHealthSummary | null>(null);
  const [error, setError] = useState<boolean>(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const fetchData = () => {
    fetch("/api/backend/system-health/summary")
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d: SystemHealthSummary) => {
        setData(d);
        setError(false);
        setLastUpdated(new Date().toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" }));
      })
      .catch(() => setError(true));
  };

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, 60_000);
    return () => clearInterval(id);
  }, []);

  const overallStatus = data?.status ?? (error ? "fail" : "degraded");

  return (
    <div className="rounded-2xl border border-eyay-border bg-eyay-card p-3 space-y-2">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono font-bold text-eyay-text uppercase tracking-widest">
            System Health
          </span>
          <StatusChip status={overallStatus} />
        </div>
        {lastUpdated && (
          <span className="text-[9px] font-mono text-eyay-faint shrink-0">
            {lastUpdated}
          </span>
        )}
      </div>

      {/* ── Bağlantı hatası ─────────────────────────────────────────────── */}
      {error && !data && (
        <p className="text-[10px] font-mono text-red-400 italic px-1">
          Health endpoint bağlantısı kurulamadı
        </p>
      )}

      {/* ── Check satırları ─────────────────────────────────────────────── */}
      {data && <ChecksSection checks={data.checks} />}

      {/* ── Safety (accordion, kapalı) ──────────────────────────────────── */}
      {data && <SafetySection safety={data.safety} />}
    </div>
  );
}
