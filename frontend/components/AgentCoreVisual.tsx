"use client";

/**
 * FAZ 29 — Ortak Agent Core görsel component'i.
 *
 * Agent modal (AgentHolographicLayer) + ana dashboard Brief (AgentBriefPanel)
 * aynı holografik dil kullansın diye tek kaynak. Mode tonu props ile gelir;
 * `animate=false` veya `prefers-reduced-motion` aktifse animasyonlar kapanır.
 */
import type { CSSProperties } from "react";

interface Props {
  /** Ana neon rengi (örn. tone.toneRing). */
  ring:    string;
  /** Aura için yumuşak rgba (örn. tone.toneSoft). */
  soft?:   string;
  animate: boolean;
  /** SVG render boyutu (px). viewBox 280 koordinat sistemine ölçeklenir. */
  size?:   number;
  /** Merkez metin (default "AGENT / CORE"). Brief'te kapatılabilir. */
  showLabel?: boolean;
  className?: string;
  style?:     CSSProperties;
}

export default function AgentCoreVisual({
  ring, soft, animate, size = 280, showLabel = true, className, style,
}: Props) {
  const auraSoft = soft ?? `${ring}33`;
  // ID'leri benzersizleştir — aynı sayfada hem brief hem modal core render olabilir
  const uid = `acv-${ring.replace(/[^0-9a-f]/gi, "")}-${size}`;

  return (
    <svg viewBox="0 0 280 280" width={size} height={size}
         className={className} style={style}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <defs>
        <radialGradient id={`${uid}-bg`} cx="50%" cy="50%" r="60%">
          <stop offset="0%"  stopColor={ring} stopOpacity="0.18" />
          <stop offset="55%" stopColor={ring} stopOpacity="0.06" />
          <stop offset="100%" stopColor="transparent" />
        </radialGradient>
        <radialGradient id={`${uid}-core`} cx="50%" cy="50%" r="60%">
          <stop offset="0%"  stopColor="#fff" stopOpacity="0.85" />
          <stop offset="30%" stopColor={ring} stopOpacity="0.75" />
          <stop offset="100%" stopColor="#020812" />
        </radialGradient>
        <linearGradient id={`${uid}-line`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%"   stopColor={ring} stopOpacity="0" />
          <stop offset="50%"  stopColor={ring} stopOpacity="0.65" />
          <stop offset="100%" stopColor={ring} stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Aura */}
      <circle cx="140" cy="140" r="135" fill={`url(#${uid}-bg)`} />
      {/* Aura overlay — soft RGBA layer */}
      <circle cx="140" cy="140" r="130" fill={auraSoft} />

      {/* Outer rotating ring */}
      <g style={animate ? { transformOrigin: "140px 140px", animation: "acv-spin 40s linear infinite" } : undefined}>
        <circle cx="140" cy="140" r="118" fill="none" stroke={ring} strokeWidth="0.8" strokeDasharray="6 8" opacity="0.5" />
        {Array.from({ length: 8 }, (_, i) => {
          const a = (i / 8) * Math.PI * 2;
          const x = 140 + Math.cos(a) * 118;
          const y = 140 + Math.sin(a) * 118;
          return <circle key={i} cx={x} cy={y} r="2.4" fill={ring} opacity="0.85" />;
        })}
      </g>

      {/* Counter-spinning middle ring */}
      <g style={animate ? { transformOrigin: "140px 140px", animation: "acv-spin 28s linear infinite reverse" } : undefined}>
        <circle cx="140" cy="140" r="92" fill="none" stroke={ring} strokeWidth="0.6" opacity="0.35" />
        <circle cx="140" cy="140" r="92" fill="none" stroke={ring} strokeWidth="0.5" strokeDasharray="2 10" opacity="0.7" />
      </g>

      {/* Hexagonal mesh */}
      <g opacity="0.35">
        {[0, 60, 120].map(rot => (
          <line key={rot} x1="140" y1="55" x2="140" y2="225" stroke={ring} strokeWidth="0.4"
                transform={`rotate(${rot} 140 140)`} />
        ))}
        <polygon points="140,55 215,97 215,183 140,225 65,183 65,97" fill="none" stroke={ring} strokeWidth="0.5" opacity="0.6" />
        <polygon points="140,85 188,113 188,167 140,195 92,167 92,113" fill="none" stroke={ring} strokeWidth="0.4" opacity="0.45" />
      </g>

      {/* Data flow lines */}
      {animate && Array.from({ length: 6 }, (_, i) => {
        const a = (i / 6) * Math.PI * 2 + Math.PI / 6;
        const x1 = 140 + Math.cos(a) * 50;
        const y1 = 140 + Math.sin(a) * 50;
        const x2 = 140 + Math.cos(a) * 110;
        const y2 = 140 + Math.sin(a) * 110;
        return (
          <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={`url(#${uid}-line)`}
                strokeWidth="1.2" strokeDasharray="3 6">
            <animate attributeName="stroke-dashoffset" from="0" to="-36"
                     dur={`${2 + i * 0.4}s`} repeatCount="indefinite" />
          </line>
        );
      })}

      {/* Pulse halo */}
      <circle cx="140" cy="140" r="56" fill="none" stroke={ring} strokeWidth="1.2" opacity="0.7"
              style={animate ? { transformOrigin: "140px 140px", animation: "acv-pulse 3s ease-in-out infinite" } : undefined} />

      {/* Core */}
      <circle cx="140" cy="140" r="44" fill={`url(#${uid}-core)`} />
      <circle cx="140" cy="140" r="44" fill="none" stroke={ring} strokeWidth="1.2" />

      {/* Core label */}
      {showLabel && (
        <>
          <text x="140" y="138" textAnchor="middle" fontSize="10" fontFamily="monospace"
                fontWeight="bold" fill="#fff" letterSpacing="2">AGENT</text>
          <text x="140" y="152" textAnchor="middle" fontSize="8" fontFamily="monospace"
                fill={ring} letterSpacing="3" opacity="0.9">CORE</text>
        </>
      )}

      {/* Animations — inline so the SVG is self-contained */}
      <style>{`
        @keyframes acv-spin   { from{transform:rotate(0)} to{transform:rotate(360deg)} }
        @keyframes acv-pulse  { 0%,100%{transform:scale(1);opacity:0.7} 50%{transform:scale(1.12);opacity:0.35} }
      `}</style>
    </svg>
  );
}
