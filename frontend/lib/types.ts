export type RegimeCode = "RISK_ON" | "TRANSITIONING" | "DEFENSIVE" | "CRISIS";
export type AppetiteCode = "STRONG" | "MODERATE" | "WEAK" | "CRISIS";
export type Decision = "AÇIL" | "BEKLE" | "KÜÇÜLT" | "KAPAT";
export type SignalStatus = "CONFIRMED" | "PENDING" | "BLOCKING" | "NEUTRAL" | "VERİ_YOK";
export type Sentiment = "BULLISH" | "BEARISH" | "NEUTRAL";
export type Relevance = "HIGH" | "MEDIUM" | "LOW";

export interface MacroLayer {
  regime: RegimeCode;
  confidence_pct: number;
  dxy_signal: string;
  energy_signal: string;
  yield_curve_signal: string;
  m2_signal: string;
  summary: string;
}

export interface RiskAppetiteLayer {
  status: AppetiteCode;
  credit_signal: string;
  btc_dominance_signal: string;
  usdt_dominance_signal: string;
  safe_haven_signal: string;
  summary: string;
}

export interface AssetSignal {
  asset_code: string;
  asset_name: string;
  status: SignalStatus;
  reason: string;
  value: number | null;
  unit: string;
}

export interface ConfirmationItem {
  signal: string;
  met: boolean;
  current_value: string;
  threshold: string;
}

export interface NewsHeadline {
  title: string;
  source: string;
  url: string;
  published_at: string;
  relevance: Relevance;
  sentiment: Sentiment;
  tags: string[];
}

export interface RegimeReport {
  generated_at: string;
  execution_mode: string;
  macro_layer: MacroLayer;
  appetite_layer: RiskAppetiteLayer;
  asset_signals: AssetSignal[];
  confirmation_checklist: ConfirmationItem[];
  decision: Decision;
  owner_action: string;
  verdict: string;
  news_headlines: NewsHeadline[];
  blocking_count: number;
  confirmed_count: number;
  pending_count: number;
}

export interface ApiResponse {
  status: string;
  data_mode: string;
  execution_mode: string;
  report: RegimeReport;
  meta: {
    total_snapshots: number;
    blocking_signals: number;
    confirmed_signals: number;
    news_fetched: number;
  };
}
