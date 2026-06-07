"use client";

/**
 * MiniChart — agent chart reader cevabı için tek-TF küçük SVG grafik.
 * Çubuk grafiği yok — sadeleştirilmiş line + S/R bantları + SL/TP marker.
 *
 * read_chart cevabındaki bir TFView alır:
 *   current, support, resistance, atr, atr_pct, trend, rsi_14
 *
 * Veri çekmiyor — parent fetch edip view'i geçirir.
 */

export interface ChartTFView {
  timeframe: string;
  bars_used?: number;
  current: number;
  support: number;
  resistance: number;
  atr: number;
  atr_pct: number;
  trend: "BULLISH" | "BEARISH" | "NEUTRAL" | string;
  rsi_14?: number | null;
  distance_to_support_pct?: number | null;
  distance_to_resistance_pct?: number | null;
  last_close_vs_open_pct?: number | null;
  notes?: string[];
}

interface Props {
  view: ChartTFView;
  stopLoss?: number | null;     // varsa kırmızı SL çizgisi
  takeProfit?: number | null;   // varsa yeşil TP çizgisi
  width?: number;
  height?: number;
  // Geçmiş bar yoksa basit bir "trend" eğrisi çiziyoruz
}

const TREND_COLOR: Record<string, string> = {
  BULLISH: "#34d399",
  BEARISH: "#f87171",
  NEUTRAL: "#94a3b8",
};

export default function MiniChart({
  view, stopLoss, takeProfit,
  width = 280, height = 130,
}: Props) {
  // X-ekseninde sadece 5 referans noktası → mini visual.
  // Y-aralığını S - 0.5*ATR ile R + 0.5*ATR arası alıyoruz.
  const yMin = Math.min(view.support, view.current, stopLoss ?? Infinity) - 0.5 * view.atr;
  const yMax = Math.max(view.resistance, view.current, takeProfit ?? -Infinity) + 0.5 * view.atr;
  const yRange = Math.max(yMax - yMin, 1e-6);

  const toY = (price: number) =>
    Math.round(height - 10 - ((price - yMin) / yRange) * (height - 30));

  const xLeft  = 50;
  const xRight = width - 10;
  const xMid   = (xLeft + xRight) / 2;

  // Heuristic "fiyat yolu" — gerçek bar yok ama trend için bir eğri çiz
  let pathPts: [number, number][];
  if (view.trend === "BULLISH") {
    pathPts = [
      [xLeft, toY(view.current - 1.2 * view.atr)],
      [xLeft + 0.25 * (xRight - xLeft), toY(view.current - 0.6 * view.atr)],
      [xMid, toY(view.current - 0.3 * view.atr)],
      [xLeft + 0.75 * (xRight - xLeft), toY(view.current - 0.15 * view.atr)],
      [xRight, toY(view.current)],
    ];
  } else if (view.trend === "BEARISH") {
    pathPts = [
      [xLeft, toY(view.current + 1.2 * view.atr)],
      [xLeft + 0.25 * (xRight - xLeft), toY(view.current + 0.6 * view.atr)],
      [xMid, toY(view.current + 0.3 * view.atr)],
      [xLeft + 0.75 * (xRight - xLeft), toY(view.current + 0.15 * view.atr)],
      [xRight, toY(view.current)],
    ];
  } else {
    pathPts = [
      [xLeft, toY(view.current + 0.3 * view.atr)],
      [xMid - 30, toY(view.current - 0.2 * view.atr)],
      [xMid, toY(view.current + 0.1 * view.atr)],
      [xMid + 30, toY(view.current - 0.15 * view.atr)],
      [xRight, toY(view.current)],
    ];
  }
  const pathStr = pathPts
    .map((p, i) => (i === 0 ? `M ${p[0]} ${p[1]}` : `L ${p[0]} ${p[1]}`))
    .join(" ");

  const trendColor = TREND_COLOR[view.trend] ?? TREND_COLOR.NEUTRAL;

  const yR  = toY(view.resistance);
  const yS  = toY(view.support);
  const yC  = toY(view.current);
  const ySL = stopLoss   != null ? toY(stopLoss)   : null;
  const yTP = takeProfit != null ? toY(takeProfit) : null;

  const fmt = (n: number) =>
    n >= 1000 ? n.toLocaleString("tr-TR", { maximumFractionDigits: 0 }) : n.toFixed(2);

  return (
    <svg
      width="100%"
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className="block"
      role="img"
      aria-label={`Mini chart ${view.timeframe}`}
    >
      {/* Arka plan ızgarası */}
      <rect x={xLeft} y={5} width={xRight - xLeft} height={height - 15} fill="rgba(255,255,255,0.015)" stroke="rgba(255,255,255,0.06)" />

      {/* TP bandı */}
      {yTP != null && (
        <line x1={xLeft} y1={yTP} x2={xRight} y2={yTP} stroke="#34d39988" strokeWidth={1} strokeDasharray="4 3" />
      )}
      {yTP != null && (
        <text x={xLeft - 4} y={yTP + 3} textAnchor="end" className="fill-emerald-400" fontSize="9" fontFamily="monospace">
          TP {fmt(takeProfit!)}
        </text>
      )}

      {/* Resistance */}
      <line x1={xLeft} y1={yR} x2={xRight} y2={yR} stroke="rgba(245, 158, 11, 0.8)" strokeWidth={1} />
      <text x={xLeft - 4} y={yR + 3} textAnchor="end" className="fill-amber-400" fontSize="9" fontFamily="monospace">
        R {fmt(view.resistance)}
      </text>

      {/* Trend eğrisi */}
      <path d={pathStr} fill="none" stroke={trendColor} strokeWidth={2} strokeLinecap="round" />

      {/* Current marker */}
      <circle cx={xRight} cy={yC} r={3.5} fill={trendColor} stroke="#0a0a0a" strokeWidth={1.5} />
      <text x={xRight + 4} y={yC + 3} className="fill-eyay-text" fontSize="9" fontFamily="monospace" fontWeight="bold">
        {fmt(view.current)}
      </text>

      {/* Support */}
      <line x1={xLeft} y1={yS} x2={xRight} y2={yS} stroke="rgba(56, 189, 248, 0.8)" strokeWidth={1} />
      <text x={xLeft - 4} y={yS + 3} textAnchor="end" className="fill-sky-400" fontSize="9" fontFamily="monospace">
        S {fmt(view.support)}
      </text>

      {/* SL bandı */}
      {ySL != null && (
        <line x1={xLeft} y1={ySL} x2={xRight} y2={ySL} stroke="#f8717188" strokeWidth={1} strokeDasharray="4 3" />
      )}
      {ySL != null && (
        <text x={xLeft - 4} y={ySL + 3} textAnchor="end" className="fill-red-400" fontSize="9" fontFamily="monospace">
          SL {fmt(stopLoss!)}
        </text>
      )}
    </svg>
  );
}
