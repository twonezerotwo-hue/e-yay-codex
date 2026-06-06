export type RegimeCode = "RISK_ON" | "TRANSITIONING" | "DEFENSIVE" | "CRISIS";
export type ImportanceCode = "CRITICAL" | "HIGH" | "MEDIUM";
export type CategoryCode = "FED" | "MACRO" | "ENERGY" | "CRYPTO" | "EQUITY" | "GEOPOLITICAL";
export type AppetiteCode = "STRONG" | "MODERATE" | "WEAK" | "CRISIS";
export type Decision = "AÇIL" | "BEKLE" | "KÜÇÜLT" | "KAPAT";
export type SignalStatus = "CONFIRMED" | "PENDING" | "BLOCKING" | "NEUTRAL" | "VERİ_YOK";
export type AssetActionType = "LONG" | "LONG_AWAIT" | "SHORT" | "SHORT_AWAIT" | "HOLD" | "AVOID" | "NEUTRAL";
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
  delta_7d_pct: number | null;
  asset_action?: AssetActionType;
  action_trigger?: string;
}

export interface ConfirmationItem {
  signal: string;
  met: boolean;
  current_value: string;
  threshold: string;
}


export interface AsymmetrySignal {
  expected_gain_pct: number;
  expected_loss_pct: number;
  ratio: number;
  label: string;
  color: "green" | "lime" | "yellow" | "orange" | "red";
  brief: string;
}

export interface Scenario {
  key: "bull" | "base" | "bear";
  label: string;
  probability_pct: number;
  trigger: string;
  brief: string;
  color: "green" | "yellow" | "red";
  thresholds?: string[];
}

export interface FlipCondition {
  direction: "AL" | "KÜÇÜLT" | "KAPAT" | "BEKLE";
  label: string;
  icon: "up" | "down" | "neutral";
  conditions: string[];
}

export interface CatalystEvent {
  id: string;
  date: string;
  name: string;
  category: CategoryCode;
  importance: ImportanceCode;
  expectation: string;
  market_impact: string;
  days_until: number;
}

export interface AssetImpact {
  asset_code: string;
  direction: "positive" | "negative" | "neutral";
  note: string;
}

// ---------------------------------------------------------------------------
// Technical Analysis
// ---------------------------------------------------------------------------

export interface DynamicLevels {
  support:     number;
  resistance:  number;
  atr:         number;
  stop_loss:   number;
  take_profit: number;
  atr_pct:     number;   // ATR as % of price
}

export interface TechnicalInsight {
  asset_code:      string;
  timeframe:       string;
  current_price:   number;
  structure:       "BULLISH" | "BEARISH" | "NEUTRAL";
  levels:          DynamicLevels;
  rsi_14:          number | null;
  macd_signal:     "BULLISH" | "BEARISH" | "NEUTRAL";
  volume_ratio:    number | null;
  structure_score: number;   // 0-25
  momentum_score:  number;   // 0-25
  zone_score:      number;   // 0-25
  volume_score:    number;   // 0-25
  technical_score: number;   // 0-100
}

// ---------------------------------------------------------------------------
// Capital Rotation
// ---------------------------------------------------------------------------

export interface AssetClassScore {
  name: string;          // "ALTIN" | "GÜMÜŞ" | "TAHVİL" | "BTC" | "HİSSE" | "NAKİT" | "PETROL"
  score: number;         // -1.5 → +1.5
  momentum_30d: number;  // Ana varlığın 30g % değişimi
  direction: string;     // "GİRİŞ" | "ÇIKIŞ" | "NÖTR"
}

export interface KeyInsight {
  icon: string;          // "🔴" | "🟡" | "🟢" | "⚠️"
  text: string;
  importance: number;    // 1-3
}

export interface RatioSignal {
  pair: string;
  value: number;
  delta_30d_pct: number;
  trend: "RISING" | "FALLING" | "FLAT";
  meaning: string;
}

export interface CorrelationPair {
  pair: string;
  corr_30d: number;
  regime: string;
}

export interface CapitalRotation {
  primary_flow: string;
  secondary_flow: string | null;
  conviction: number;
  class_scores: AssetClassScore[];
  key_insights: KeyInsight[];
  synthesis: string;
  ratios: RatioSignal[];
  correlations: CorrelationPair[];
  rotation_context: string;
  error: string | null;
}

export interface NewsHeadline {
  title: string;
  title_tr?: string;     // AI ile Türkçe çevirisi — boşsa orijinal kullanılır
  source: string;
  url: string;
  published_at: string;
  relevance: Relevance;
  sentiment: Sentiment;
  tags: string[];
  asset_impact?: AssetImpact[];
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
  scenarios: Scenario[];
  asymmetry: AsymmetrySignal;
  owner_actions: string[];
  flip_conditions: FlipCondition[];
  news_headlines: NewsHeadline[];
  upcoming_catalysts: CatalystEvent[];
  tech_insights: TechnicalInsight[];
  blocking_count: number;
  confirmed_count: number;
  pending_count: number;
}

// ---------------------------------------------------------------------------
// AI Analyst Report
// ---------------------------------------------------------------------------

export interface AIAnalystReport {
  generated_at: string;
  model: string;
  cached: boolean;
  // Akıcı narratif — tek metin bloğu, paragraflar \n\n ile ayrılmış
  narrative: string;
  // Hızlı tarama — ticker tarzı kısa sinyaller
  key_signals: string[];
  verdict: string;
  confidence_note: string;
  error: string | null;
}

export interface AIReportResponse {
  status: string;
  data_mode: string;
  execution_mode: string;
  ai_report: AIAnalystReport;
  geo_news_count: number;
}

export type HealthScore = "HIGH" | "MEDIUM" | "LOW";

export interface ModuleHealth {
  score: HealthScore;
  detail: string;
}

export interface ApiResponse {
  status: string;
  data_mode: string;
  execution_mode: string;
  report: RegimeReport;
  capital_rotation: CapitalRotation | null;
  module_health?: Record<string, ModuleHealth>;
  meta: {
    total_snapshots: number;
    blocking_signals: number;
    confirmed_signals: number;
    news_fetched: number;
    catalysts_fetched: number;
    tech_insights: number;
    rotation_ratios: number;
  };
}

export interface AIReportResponseFull extends AIReportResponse {
  capital_rotation?: CapitalRotation | null;
}
