"use client";

import { useEffect, useState } from "react";

// ---------------------------------------------------------------------------
// PAPER TRADING KARAR MERKEZİ
// 10 bloklu kompakt dashboard. Karar dili "açık pozisyon yoksa KÜÇÜLT YOK"
// kuralına saygı duyar — backend zaten bu disiplini uygular.
// PAPER_SAFE / NO_EXECUTION
// ---------------------------------------------------------------------------

interface PaperDecisionResponse {
  generated_at:           string;
  execution_status:       string;
  owner_action:           string;
  decision_label:         string;
  decision_reason:        string;
  market_interpretation:  Record<string, unknown>;
  data_quality_status:    Record<string, unknown>;
  trigger_engine_output:  Record<string, unknown>;
  risk_engine_verdict:    Record<string, unknown>;
  paper_trading_decision: Record<string, unknown>;
  entry_plan:             Record<string, unknown>;
  exit_plan:              Record<string, unknown>;
  active_paper_positions: Array<Record<string, unknown>>;
  news_to_decision_mapping: Array<Record<string, unknown>>;
  learning_layer:         Record<string, unknown>;
}

const DECISION_THEMES: Record<string, { fg: string; bg: string; border: string; pill: string }> = {
  "YENİ RİSK AÇMA / BEKLE":  { fg: "text-amber-300",   bg: "bg-amber-950/25",   border: "border-amber-900/55",  pill: "bg-amber-500/15 text-amber-300 border-amber-700/40" },
  "KÜÇÜLT":                  { fg: "text-orange-300",  bg: "bg-orange-950/25",  border: "border-orange-900/55", pill: "bg-orange-500/15 text-orange-300 border-orange-700/40" },
  "İŞLEM YOK / SİSTEM DURDU":{ fg: "text-red-300",     bg: "bg-red-950/30",     border: "border-red-900/60",    pill: "bg-red-500/20 text-red-300 border-red-700/50" },
  "POZİSYON ARTIRMA":        { fg: "text-yellow-300",  bg: "bg-yellow-950/20",  border: "border-yellow-900/45", pill: "bg-yellow-500/15 text-yellow-300 border-yellow-700/40" },
  "İZLE":                    { fg: "text-blue-300",    bg: "bg-blue-950/20",    border: "border-blue-900/45",   pill: "bg-blue-500/15 text-blue-300 border-blue-700/40" },
  "KORU":                    { fg: "text-emerald-300", bg: "bg-emerald-950/20", border: "border-emerald-900/45",pill: "bg-emerald-500/15 text-emerald-300 border-emerald-700/40" },
  "POZİSYON YOK · NÖTR İZLEME": { fg: "text-slate-300", bg: "bg-slate-950/20", border: "border-slate-900/45",   pill: "bg-slate-500/15 text-slate-300 border-slate-700/40" },
};

function theme(label: string) {
  return DECISION_THEMES[label] ?? DECISION_THEMES["POZİSYON YOK · NÖTR İZLEME"];
}

function Pill({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 text-[9px] font-mono font-bold border rounded ${className}`}>
      {children}
    </span>
  );
}

function Block({ title, badge, badgeClass, children }: {
  title: string;
  badge?: string;
  badgeClass?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-eyay-line bg-eyay-raised/30 overflow-hidden flex flex-col">
      <div className="px-3 py-1.5 border-b border-white/5 flex items-center justify-between">
        <p className="text-[9px] uppercase tracking-widest font-bold text-eyay-faint">{title}</p>
        {badge && <Pill className={badgeClass ?? "bg-white/5 text-eyay-dim border-white/10"}>{badge}</Pill>}
      </div>
      <div className="px-3 py-2 flex-1 text-[10.5px] text-eyay-text leading-snug space-y-1">
        {children}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-2">
      <span className="text-eyay-faint text-[10px]">{label}</span>
      <span className="font-mono text-[10px] text-eyay-text text-right break-words max-w-[60%]">
        {value === null || value === undefined || value === "" ? "—" : String(value)}
      </span>
    </div>
  );
}

function ListBlock({ items, empty = "—" }: { items?: unknown[]; empty?: string }) {
  if (!items || items.length === 0) return <p className="text-eyay-faint text-[10px] italic">{empty}</p>;
  return (
    <ul className="space-y-1">
      {items.map((it, i) => (
        <li key={i} className="flex items-start gap-1.5">
          <span className="text-eyay-faint mt-0.5 text-[9px] font-mono">•</span>
          <span className="text-[10px]">{typeof it === "string" ? it : JSON.stringify(it)}</span>
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------

export default function PaperDecisionCenter() {
  const [data, setData] = useState<PaperDecisionResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const fetchOnce = async () => {
      try {
        const r = await fetch("/api/backend/paper/decision/latest", { cache: "no-store" });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = await r.json();
        if (alive) { setData(j); setErr(null); }
      } catch (e) {
        if (alive) setErr(e instanceof Error ? e.message : "fetch failed");
      } finally {
        if (alive) setLoading(false);
      }
    };
    fetchOnce();
    const id = setInterval(fetchOnce, 45_000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  if (loading) {
    return (
      <div className="rounded-xl border border-eyay-line bg-eyay-raised/20 p-4 text-center">
        <p className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest">
          PAPER TRADING KARAR MERKEZİ · loading…
        </p>
      </div>
    );
  }
  if (err || !data) {
    return (
      <div className="rounded-xl border border-red-900/50 bg-red-950/15 p-3">
        <p className="text-[10px] font-mono text-red-300">Karar merkezi yüklenemedi: {err}</p>
      </div>
    );
  }

  const t = theme(data.decision_label);
  const mi = data.market_interpretation as Record<string, unknown>;
  const dq = data.data_quality_status as Record<string, unknown>;
  const te = data.trigger_engine_output as Record<string, unknown>;
  const re = data.risk_engine_verdict as Record<string, unknown>;
  const pt = data.paper_trading_decision as Record<string, unknown>;
  const ep = data.entry_plan as Record<string, unknown>;
  const xp = data.exit_plan as Record<string, unknown>;
  const ll = data.learning_layer as Record<string, unknown>;
  const positions = data.active_paper_positions ?? [];
  const news = data.news_to_decision_mapping ?? [];

  return (
    <section className="space-y-2">

      {/* ─── BAŞLIK + KARAR BANNER ──────────────────────────────────────── */}
      <div className={`rounded-xl border ${t.border} ${t.bg} px-3 py-2 flex items-center justify-between gap-3`}>
        <div className="min-w-0">
          <p className="text-[9px] uppercase tracking-widest font-bold text-eyay-faint">
            PAPER TRADING KARAR MERKEZİ
          </p>
          <p className={`text-[14px] font-bold leading-tight mt-0.5 ${t.fg}`}>
            {data.decision_label}
          </p>
          <p className="text-[9px] font-mono text-eyay-dim mt-0.5">
            owner_action: <span className={t.fg}>{data.owner_action}</span>
            <span className="mx-2 text-eyay-faint">·</span>
            reason: <span className="text-eyay-dim">{data.decision_reason}</span>
          </p>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <Pill className={t.pill}>{data.execution_status}</Pill>
          <span className="text-[8px] font-mono text-eyay-faint">
            {new Date(data.generated_at).toLocaleTimeString("tr-TR")}
          </span>
        </div>
      </div>

      {/* ─── 4'lü üst sıra: MARKET / DQS / TRIGGERS / RISK ──────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-2">

        {/* 1. MARKET INTERPRETATION */}
        <Block title="1 · Market Interpretation" badge={String(mi.regime ?? "—")}
               badgeClass={t.pill}>
          <Row label="risk_on"             value={mi.risk_on_score} />
          <Row label="risk_off"            value={mi.risk_off_score} />
          <Row label="credit"              value={mi.credit_confirmation} />
          <Row label="dollar"              value={mi.dollar_pressure} />
          <Row label="energy"              value={mi.energy_pressure} />
          <Row label="crypto"              value={mi.crypto_structure} />
          <Row label="silver/copper"       value={mi.silver_copper_confirmation} />
        </Block>

        {/* 2. DATA QUALITY */}
        <Block title="2 · Data Quality" badge={String(dq.decision_permission ?? "—")}
               badgeClass="bg-cyan-500/15 text-cyan-300 border-cyan-700/40">
          <Row label="overall_dqs"   value={`${dq.overall_dqs ?? 0}/100`} />
          <Row label="dqs_decision"  value={dq.dqs_decision} />
          <Row label="real_assets"   value={(dq.real_assets as unknown[])?.length ?? 0} />
          <Row label="mock_assets"   value={(dq.mock_assets as unknown[])?.length ?? 0} />
          <Row label="stale_assets"  value={(dq.stale_assets as unknown[])?.length ?? 0} />
          <Row label="missing"       value={(dq.missing_assets as unknown[])?.length ?? 0} />
        </Block>

        {/* 3. TRIGGER ENGINE */}
        <Block title="3 · Trigger Engine" badge={`SEV: ${te.trigger_severity ?? "INFO"}`}
               badgeClass={
                 te.trigger_severity === "RED"    ? "bg-red-500/20 text-red-300 border-red-700/50" :
                 te.trigger_severity === "ORANGE" ? "bg-orange-500/15 text-orange-300 border-orange-700/40" :
                 te.trigger_severity === "YELLOW" ? "bg-yellow-500/15 text-yellow-300 border-yellow-700/40" :
                 "bg-white/5 text-eyay-dim border-white/10"
               }>
          <Row label="active"        value={(te.active_triggers as unknown[])?.length ?? 0} />
          <Row label="confirmed"     value={(te.confirmed_triggers as unknown[])?.length ?? 0} />
          <Row label="placeholder"   value={(te.placeholder_triggers as unknown[])?.length ?? 0} />
          <div className="mt-1.5 pt-1.5 border-t border-white/5">
            <p className="text-[9px] font-mono text-eyay-faint mb-1">Confirmed triggers:</p>
            <ListBlock
              items={(te.confirmed_triggers as Array<{ trigger_code: string; asset: string }> ?? [])
                .map(c => `${c.asset} · ${c.trigger_code}`)}
              empty="(yok)"
            />
          </div>
        </Block>

        {/* 4. RISK ENGINE */}
        <Block title="4 · Risk Engine" badge={String(re.risk_action ?? "HOLD")}
               badgeClass={t.pill}>
          <Row label="kill_switch"   value={re.kill_switch_active ? "🔴 AKTİF" : "off"} />
          <Row label="reason_codes"  value={(re.reason_codes as unknown[])?.length ?? 0} />
          <Row label="softeners"     value={(re.risk_softeners as unknown[])?.length ?? 0} />
          <Row label="hardeners"     value={(re.risk_hardeners as unknown[])?.length ?? 0} />
          <div className="mt-1.5 pt-1.5 border-t border-white/5">
            <ListBlock items={re.reason_codes as string[]} empty="(temiz)" />
          </div>
        </Block>
      </div>

      {/* ─── 3'lü orta sıra: PAPER DECISION / ENTRY / EXIT ──────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-2">

        {/* 5. PAPER TRADING DECISION */}
        <Block title="5 · Paper Trading Decision"
               badge={String(pt.position_intent ?? "HOLD/FLAT")}
               badgeClass={
                 pt.position_intent === "OPEN"
                   ? "bg-emerald-500/15 text-emerald-300 border-emerald-700/40"
                   : "bg-white/5 text-eyay-dim border-white/10"
               }>
          <Row label="last_decision"     value={pt.latest_paper_decision} />
          <Row label="setup_valid"       value={pt.setup_validity ? "evet" : "hayır"} />
          <Row label="would_trade"
               value={`${pt.would_trade_asset ?? "—"} · ${pt.would_trade_direction ?? "—"}`} />
          <Row label="consensus"         value={pt.best_consensus_score} />
          <Row label="open_positions"    value={pt.has_open_positions ? "var" : "yok"} />
          <div className="mt-1.5 pt-1.5 border-t border-white/5">
            <p className="text-[9px] font-mono text-eyay-faint mb-1">why_no_trade:</p>
            <ListBlock items={pt.why_no_trade as string[]} empty="(engelsiz)" />
          </div>
        </Block>

        {/* 6. ENTRY PLAN */}
        <Block title="6 · Entry Plan"
               badge={(ep.conditions_to_enter as unknown[])?.length
                 ? `${(ep.conditions_to_enter as unknown[]).length} koşul` : "—"}>
          <p className="text-[9px] font-mono text-eyay-faint">Conditions to enter:</p>
          <ListBlock items={ep.conditions_to_enter as string[]} />
          <div className="mt-1 pt-1.5 border-t border-white/5">
            <p className="text-[9px] font-mono text-eyay-faint">Macro:</p>
            <ListBlock items={ep.required_macro_confirmations as string[]} empty="(temiz)" />
          </div>
          <div className="mt-1 pt-1.5 border-t border-white/5">
            <p className="text-[9px] font-mono text-eyay-faint">Credit + News:</p>
            <ListBlock
              items={[
                ...((ep.required_credit_confirmations as string[]) ?? []),
                ...((ep.required_news_confirmations as string[]) ?? []),
              ]}
              empty="(temiz)"
            />
          </div>
        </Block>

        {/* 7. EXIT PLAN */}
        <Block title="7 · Exit / Reduce Plan"
               badge={xp.stop_loss ? "active" : "n/a"}
               badgeClass={xp.stop_loss ? "bg-red-500/15 text-red-300 border-red-700/40"
                                        : "bg-white/5 text-eyay-dim border-white/10"}>
          <Row label="stop_loss"      value={xp.stop_loss} />
          <Row label="target_price"   value={xp.target_price} />
          <Row label="time_stop"      value={xp.time_stop} />
          <div className="mt-1.5 pt-1.5 border-t border-white/5">
            <p className="text-[9px] font-mono text-eyay-faint">Invalidation:</p>
            <ListBlock items={xp.invalidation_conditions as string[]} empty="(yok)" />
          </div>
          <div className="mt-1 pt-1.5 border-t border-white/5">
            <p className="text-[9px] font-mono text-eyay-faint">Risk reduce:</p>
            <ListBlock items={xp.risk_reduce_conditions as string[]} empty="(yok)" />
          </div>
        </Block>
      </div>

      {/* ─── 8. ACTIVE POSITIONS — full width ───────────────────────────── */}
      <Block title={`8 · Active Paper Positions (${positions.length})`}
             badge={positions.length ? "AKTİF" : "FLAT"}
             badgeClass={positions.length
               ? "bg-emerald-500/15 text-emerald-300 border-emerald-700/40"
               : "bg-white/5 text-eyay-dim border-white/10"}>
        {positions.length === 0 ? (
          <p className="text-eyay-faint text-[10px] italic">Açık pozisyon yok — KÜÇÜLT denmez.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {positions.map((p, i) => (
              <div key={i} className="rounded-lg border border-white/5 bg-black/20 p-2">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono text-[11px] font-bold text-eyay-text">
                    {String(p.asset)} · {String(p.direction)}
                  </span>
                  <Pill className={Number(p.unrealized_pnl) >= 0
                    ? "bg-emerald-500/15 text-emerald-300 border-emerald-700/40"
                    : "bg-red-500/15 text-red-300 border-red-700/40"}>
                    {Number(p.unrealized_pnl) >= 0 ? "+" : ""}{String(p.unrealized_pnl ?? 0)} USD
                  </Pill>
                </div>
                <Row label="entry"        value={p.entry_price} />
                <Row label="current"      value={p.current_price} />
                <Row label="stop_loss"    value={p.stop_loss} />
                <Row label="target"       value={p.target_price} />
                <Row label="size"         value={p.position_size} />
                <Row label="rr"           value={p.risk_reward} />
                <Row label="opened_because" value={p.opened_because} />
                <Row label="close_if"     value={p.close_if} />
              </div>
            ))}
          </div>
        )}
      </Block>

      {/* ─── 9 + 10: NEWS  +  LEARNING ──────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">

        {/* 9. NEWS-TO-DECISION */}
        <Block title={`9 · News → Decision Map (${news.length})`}>
          {news.length === 0 ? (
            <p className="text-eyay-faint text-[10px] italic">Aktif haber yok.</p>
          ) : (
            <div className="space-y-1.5">
              {news.slice(0, 5).map((n, i) => (
                <div key={i} className="border-b border-white/5 pb-1.5 last:border-b-0 last:pb-0">
                  <p className="text-[10.5px] font-semibold text-eyay-text leading-tight">
                    {String(n.headline ?? "—")}
                  </p>
                  <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                    <Pill className="bg-white/5 text-eyay-dim border-white/10">
                      {String(n.source ?? "internal")}
                    </Pill>
                    <Pill className="bg-blue-500/10 text-blue-300 border-blue-700/30">
                      {(n.affected_assets as string[])?.join(",") ?? "MULTI"}
                    </Pill>
                    <Pill className="bg-white/5 text-eyay-dim border-white/10">
                      {String(n.expected_direction ?? "—")}
                    </Pill>
                  </div>
                  {n.decision_impact ? (
                    <p className="text-[9.5px] text-eyay-dim mt-0.5">
                      → {String(n.decision_impact)}
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </Block>

        {/* 10. LEARNING LAYER */}
        <Block title="10 · Learning Layer"
               badge={String(ll.weekly_learning_tag ?? "—")}
               badgeClass="bg-violet-500/15 text-violet-300 border-violet-700/40">
          <Row label="prediction_id"   value={ll.prediction_id} />
          <Row label="logged"          value={ll.decision_logged} />
          <Row label="trade_count"     value={ll.trade_count_so_far} />
          <div className="mt-1 pt-1.5 border-t border-white/5">
            <p className="text-[9px] font-mono text-eyay-faint">Expected outcome:</p>
            <p className="text-[10px] text-eyay-dim mt-0.5">{String(ll.expected_outcome ?? "—")}</p>
          </div>
          <div className="mt-1 pt-1.5 border-t border-white/5">
            <p className="text-[9px] font-mono text-eyay-faint">Will be checked:</p>
            <ListBlock items={ll.what_will_be_checked_later as string[]} empty="(yok)" />
          </div>
          <div className="mt-1 pt-1.5 border-t border-white/5">
            <p className="text-[9px] font-mono text-eyay-faint">Failure conditions:</p>
            <ListBlock items={ll.failure_conditions as string[]} empty="(yok)" />
          </div>
        </Block>
      </div>

      {/* PAPER_SAFE footer */}
      <div className="px-3 py-1 border-t border-white/5 bg-black/20 rounded-md">
        <p className="text-[8px] font-mono text-eyay-faint tracking-wider text-center">
          PAPER_SAFE · NO_EXECUTION · tüm kararlar insana aittir
        </p>
      </div>
    </section>
  );
}
