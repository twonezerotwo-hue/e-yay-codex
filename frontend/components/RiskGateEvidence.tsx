"use client";

/**
 * RiskGateEvidence — canonical RiskGate + AgentVote kanıt zinciri görünümü.
 *
 * Backend /api/v1/dashboard/state'ten gelen ViewModel'leri compact bir bant
 * olarak gösterir. Karar motorunu çağırmaz; sadece backend görünümünü işler.
 * PAPER_SAFE / NO_EXECUTION.
 */
import type { AgentVoteView, RiskGateView } from "@/lib/api";

interface Props {
  riskGate: RiskGateView | null;
  agentVotes: AgentVoteView[];
  className?: string;
}

const GATE_STYLE: Record<string, { ring: string; bg: string; label: string; text: string }> = {
  PASS:    { ring: "border-emerald-700/60", bg: "bg-emerald-950/30", label: "PASS",    text: "text-emerald-300" },
  CAUTION: { ring: "border-amber-700/60",   bg: "bg-amber-950/25",   label: "CAUTION", text: "text-amber-300"   },
  BLOCK:   { ring: "border-red-700/60",     bg: "bg-red-950/30",     label: "BLOCK",   text: "text-red-300"     },
};

const VOTE_STYLE: Record<string, string> = {
  ALLOW:   "border-emerald-700/50 text-emerald-300 bg-emerald-950/20",
  CAUTION: "border-amber-700/50 text-amber-300 bg-amber-950/20",
  BLOCK:   "border-red-700/50 text-red-300 bg-red-950/20",
  ABSTAIN: "border-eyay-border text-eyay-dim bg-eyay-raised/40",
};

export default function RiskGateEvidence({ riskGate, agentVotes, className }: Props) {
  if (!riskGate) return null;

  const st = GATE_STYLE[riskGate.status] ?? GATE_STYLE.PASS;

  return (
    <section className={`rounded-2xl border ${st.ring} ${st.bg} p-3 ${className ?? ""}`}>
      <header className="flex items-center justify-between gap-2 flex-wrap mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-[9px] font-mono uppercase tracking-[0.2em] text-eyay-faint">
            🛡️ Risk Gate
          </span>
          <span className={`text-[11px] font-mono font-black px-1.5 py-0.5 rounded border ${st.ring} ${st.text}`}>
            {st.label}
          </span>
          <span className="text-[10px] font-mono text-eyay-faint">
            · {riskGate.source_risk_action}
          </span>
        </div>
        {riskGate.dqs_score !== null && (
          <span
            className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
              riskGate.dqs_passed === false
                ? "border-red-700/50 text-red-300 bg-red-950/30"
                : "border-eyay-border text-eyay-dim bg-eyay-raised/40"
            }`}
            title="Data Quality Score"
          >
            DQS {riskGate.dqs_score.toFixed(0)}
          </span>
        )}
      </header>

      <p className="text-[11px] text-eyay-text leading-snug">{riskGate.reason}</p>

      {riskGate.hard_blockers.length > 0 && (
        <ul className="mt-2 space-y-1">
          {riskGate.hard_blockers.map((b, i) => (
            <li key={i} className="text-[10px] font-mono text-red-300 leading-snug">
              ▣ {b}
            </li>
          ))}
        </ul>
      )}

      {agentVotes.length > 0 && (
        <div className="mt-2.5 pt-2 border-t border-white/5">
          <p className="text-[8px] font-mono uppercase tracking-widest text-eyay-faint mb-1.5">
            Agent oyları
          </p>
          <div className="flex flex-wrap gap-1.5">
            {agentVotes.map((v, i) => (
              <span
                key={i}
                title={`${v.agent_name}: ${v.reason}`}
                className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${VOTE_STYLE[v.vote] ?? VOTE_STYLE.ABSTAIN}`}
              >
                {v.agent_name}: {v.vote}
              </span>
            ))}
          </div>
        </div>
      )}

      <p className="mt-2 text-[8px] font-mono text-eyay-faint text-right">
        PAPER_SAFE · NO_EXECUTION · canonical-state
      </p>
    </section>
  );
}
