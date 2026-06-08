"use client";

/**
 * GlobalEventMap — 2D dünya haritası, haber lokasyonu pulse marker'ı.
 *
 * Bağımlılıksız (no react-simple-maps, no d3): basit inline SVG kıta silüetleri
 * + equirectangular projeksiyon. Performans yüksek, indirme yükü sıfır.
 *
 * Marker rengi severity'ye göre:
 *   RED    — sistemik risk / savaş / enerji şoku
 *   ORANGE — yüksek dikkat
 *   YELLOW — orta önem
 *   BLUE   — destekleyici / normal
 *
 * Hover → tooltip; click → onSelect(eventId).
 */
import { useMemo } from "react";
import type { NewsHeadline, NewsSeverity } from "@/lib/types";

interface Props {
  headlines:        NewsHeadline[];
  selectedEventId?: string | null;
  onSelect?:        (eventId: string | null) => void;
}

// ── Equirectangular projection: lat/lon → SVG viewBox koordinatı ─────────────
// viewBox 0 0 1000 500 — dünyanın tamamı görünür
const VIEW_W = 1000;
const VIEW_H = 500;
function project(lat: number, lon: number): { x: number; y: number } {
  const x = ((lon + 180) / 360) * VIEW_W;
  const y = ((90 - lat) / 180) * VIEW_H;
  return { x, y };
}

// ── Severity → renk paleti ───────────────────────────────────────────────────
const SEV_COLOR: Record<NewsSeverity, { fill: string; stroke: string; class: string }> = {
  RED:    { fill: "#ef4444", stroke: "#fecaca", class: "text-red-400"     },
  ORANGE: { fill: "#fb923c", stroke: "#fed7aa", class: "text-orange-400"  },
  YELLOW: { fill: "#facc15", stroke: "#fef3c7", class: "text-yellow-400"  },
  BLUE:   { fill: "#60a5fa", stroke: "#bfdbfe", class: "text-blue-400"    },
};

// Aynı lokasyonda birden fazla haber varsa kümele
interface MarkerCluster {
  key:        string;
  lat:        number;
  lon:        number;
  name:       string;
  severity:   NewsSeverity;
  count:      number;
  topHeadline:NewsHeadline;
  headlines:  NewsHeadline[];
}

function clusterByLocation(headlines: NewsHeadline[]): MarkerCluster[] {
  const map = new Map<string, MarkerCluster>();
  // Severity önceliği: RED > ORANGE > YELLOW > BLUE
  const sevRank: Record<NewsSeverity, number> = { RED: 0, ORANGE: 1, YELLOW: 2, BLUE: 3 };

  for (const h of headlines) {
    if (!h.location) continue;
    const key = `${h.location.lat.toFixed(2)}|${h.location.lon.toFixed(2)}`;
    const existing = map.get(key);
    if (existing) {
      existing.count++;
      existing.headlines.push(h);
      // En kritik severity ile en üst başlığı tut
      const curSev = h.severity ?? "BLUE";
      if (sevRank[curSev] < sevRank[existing.severity]) {
        existing.severity = curSev;
        existing.topHeadline = h;
      }
    } else {
      map.set(key, {
        key,
        lat:         h.location.lat,
        lon:         h.location.lon,
        name:        h.location.name,
        severity:    h.severity ?? "BLUE",
        count:       1,
        topHeadline: h,
        headlines:   [h],
      });
    }
  }
  // En kritik markerlar son render edilsin (üstte görünsün)
  return Array.from(map.values()).sort(
    (a, b) => sevRank[b.severity] - sevRank[a.severity],
  );
}

// ── Render ───────────────────────────────────────────────────────────────────

export default function GlobalEventMap({ headlines, selectedEventId, onSelect }: Props) {
  const clusters = useMemo(() => clusterByLocation(headlines), [headlines]);
  const selectedCluster = useMemo(
    () => clusters.find(c => c.headlines.some(h => h.event_id === selectedEventId)) ?? null,
    [clusters, selectedEventId],
  );

  return (
    <div
      className="relative w-full rounded-xl overflow-hidden border border-eyay-border"
      style={{ background: "linear-gradient(180deg, #0a1322 0%, #061018 100%)" }}
    >
      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        className="w-full block"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Küresel olay haritası"
      >
        {/* Equirectangular grid — coğrafi referans */}
        <defs>
          <pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse">
            <path d="M 50 0 L 0 0 0 50" fill="none" stroke="#1e293b" strokeWidth="0.4" opacity="0.6" />
          </pattern>
        </defs>
        <rect width={VIEW_W} height={VIEW_H} fill="url(#grid)" />

        {/* Ekvator + ana meridyenler */}
        <line x1="0" y1={VIEW_H / 2} x2={VIEW_W} y2={VIEW_H / 2}
              stroke="#1e3a5c" strokeWidth="0.8" strokeDasharray="4 4" opacity="0.7" />
        <line x1={VIEW_W / 2} y1="0" x2={VIEW_W / 2} y2={VIEW_H}
              stroke="#1e3a5c" strokeWidth="0.8" strokeDasharray="4 4" opacity="0.5" />

        {/* Sadeleştirilmiş kıta silüetleri (path verisi düşük çözünürlüklü, hafif) */}
        <g fill="#0f2235" stroke="#1e3f5e" strokeWidth="0.5" opacity="0.9">
          {/* Kuzey + Güney Amerika */}
          <path d="M 150 110 L 175 90 L 220 100 L 240 130 L 245 165 L 235 185 L 250 200 L 270 220 L 290 240
                   L 285 280 L 270 320 L 260 360 L 250 395 L 240 415 L 225 430 L 210 425 L 205 405 L 220 380
                   L 215 350 L 200 320 L 205 295 L 215 270 L 200 245 L 175 225 L 155 215 L 140 200 L 135 175
                   L 145 145 Z" />
          {/* Avrupa + Afrika */}
          <path d="M 470 110 L 510 95 L 545 105 L 555 125 L 540 145 L 550 165 L 545 185 L 525 210 L 530 240
                   L 545 270 L 560 305 L 575 340 L 570 370 L 555 395 L 535 405 L 525 390 L 530 360 L 515 330
                   L 510 295 L 505 265 L 495 235 L 475 210 L 470 185 L 465 160 L 470 135 Z" />
          {/* Asya */}
          <path d="M 560 90 L 620 80 L 680 95 L 730 105 L 780 115 L 815 130 L 840 155 L 855 185 L 850 215
                   L 825 240 L 800 230 L 775 250 L 760 275 L 750 290 L 765 305 L 780 320 L 790 335 L 770 345
                   L 750 340 L 720 320 L 690 290 L 660 260 L 635 230 L 615 205 L 595 175 L 580 145 L 568 115 Z" />
          {/* Avustralya */}
          <path d="M 790 360 L 840 355 L 875 370 L 880 395 L 855 410 L 820 410 L 795 395 L 785 375 Z" />
          {/* Birleşik Krallık (ada) */}
          <path d="M 478 130 L 488 125 L 494 138 L 488 150 L 478 148 Z" />
          {/* Japonya */}
          <path d="M 855 175 L 868 168 L 872 180 L 865 195 L 855 192 Z" />
          {/* Yeni Zelanda */}
          <path d="M 905 420 L 920 415 L 925 432 L 912 442 L 905 432 Z" />
        </g>

        {/* Marker'lar */}
        <g>
          {clusters.map(c => {
            const { x, y } = project(c.lat, c.lon);
            const sel = selectedCluster?.key === c.key;
            const sev = SEV_COLOR[c.severity];
            const r = c.severity === "RED" ? 6 : c.severity === "ORANGE" ? 5 : 4;
            const isCritical = c.severity === "RED" || c.severity === "ORANGE";

            return (
              <g
                key={c.key}
                transform={`translate(${x},${y})`}
                style={{ cursor: "pointer", color: sev.fill }}
                onClick={(e) => {
                  e.stopPropagation();
                  if (onSelect) onSelect(c.topHeadline.event_id ?? null);
                }}
                className={sel ? "map-marker-selected" : ""}
              >
                {/* Outer pulse ring (sadece kritikler için) */}
                {isCritical && (
                  <circle r={r} fill={sev.fill} opacity="0.45"
                          className={c.severity === "RED" ? "map-marker-ring" : "map-marker-ring-slow"} />
                )}
                {/* Solid core */}
                <circle
                  r={sel ? r + 1.5 : r}
                  fill={sev.fill}
                  stroke={sel ? "#ffffff" : sev.stroke}
                  strokeWidth={sel ? 1.5 : 0.8}
                  opacity={sel ? 1 : 0.92}
                />
                {/* Count badge */}
                {c.count > 1 && (
                  <text
                    y={-r - 4}
                    textAnchor="middle"
                    fontSize="9"
                    fontWeight="700"
                    fill={sev.stroke}
                    style={{ pointerEvents: "none" }}
                  >
                    {c.count}
                  </text>
                )}
                {/* Hover tooltip — SVG title */}
                <title>{`${c.name} · ${c.severity}${c.count > 1 ? ` · ${c.count} haber` : ""}\n${c.topHeadline.title}`}</title>
              </g>
            );
          })}
        </g>
      </svg>

      {/* Severity legend (overlay) */}
      <div className="absolute bottom-2 left-2 flex items-center gap-2 px-2 py-1 rounded-md bg-black/55 backdrop-blur border border-white/10 text-[9px] font-mono text-eyay-dim pointer-events-none">
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-red-500" /> RED</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-orange-400" /> ORANGE</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-yellow-400" /> YELLOW</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-blue-400" /> BLUE</span>
      </div>

      {/* Empty state */}
      {clusters.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <p className="text-xs font-mono text-eyay-faint italic">
            Coğrafi referans içeren haber bulunmadı
          </p>
        </div>
      )}
    </div>
  );
}
