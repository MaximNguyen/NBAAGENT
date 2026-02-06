// TypeScript interfaces matching API schemas

export interface Opportunity {
  game_id: string;
  matchup: string;
  market: string;
  outcome: string;
  bookmaker: string;
  our_prob: number;
  market_odds: number;
  fair_odds: number;
  ev_pct: number;
  kelly_bet_pct: number;
  confidence: string;
  sharp_edge?: number | null;
  rlm_signal?: string | null;
  llm_insight?: string | null;
  ml_prob?: number | null;
  ml_explanation?: string | null;
}

export interface OpportunitiesListResponse {
  opportunities: Opportunity[];
  total: number;
  filters_applied: Record<string, unknown>;
}

export interface AnalysisRunRequest {
  query: string;
  min_ev?: number | null;
  confidence?: string | null;
  limit?: number | null;
}

export interface AnalysisRunResponse {
  run_id: string;
  status: string;
  message: string;
}

export interface AnalysisStatus {
  run_id: string;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  duration_ms?: number | null;
  current_step?: string | null;
  opportunities: Opportunity[];
  errors: string[];
  recommendation?: string | null;
}

export interface OddsOutcome {
  outcome: string;
  bookmaker: string;
  price: number;
  point?: number | null;
}

export interface OddsComparison {
  game_id: string;
  matchup: string;
  market: string;
  outcomes: OddsOutcome[];
  best_odds: Record<string, OddsOutcome>;
}

export interface SportsbookMetrics {
  name: string;
  games_with_odds: number;
  markets_available: string[];
  last_seen?: string | null;
  availability_pct: number;
}

export interface CacheMetrics {
  hits: number;
  misses: number;
  stale_hits: number;
  hit_rate: number;
  fresh_hit_rate: number;
}

export interface PerformanceSummary {
  total_bets: number;
  wins: number;
  losses: number;
  win_rate: number;
  net_profit: number;
  roi_pct: number;
  avg_edge: number;
  brier_score?: number | null;
}

export interface MonthlyROI {
  month: string;
  bets: number;
  roi_pct: number;
  net_profit: number;
}

export interface ModelAccuracy {
  brier_score: number;
  calibration_error: number;
  clv_pct?: number | null;
  total_predictions: number;
}

export interface HealthResponse {
  status: string;
  version: string;
  timestamp: string;
}

// WebSocket message types
export type WsMessage =
  | { type: "status"; status: string; step: string }
  | { type: "agent_complete"; agent: string; duration_ms: number }
  | { type: "opportunity"; opportunity: Opportunity }
  | { type: "complete"; total_opportunities: number; duration_ms: number }
  | { type: "error"; message: string }
  | { type: "heartbeat" };
