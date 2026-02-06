import axios from "axios";
import type {
  AnalysisRunRequest,
  AnalysisRunResponse,
  AnalysisStatus,
  CacheMetrics,
  HealthResponse,
  ModelAccuracy,
  MonthlyROI,
  OddsComparison,
  Opportunity,
  OpportunitiesListResponse,
  PerformanceSummary,
  SportsbookMetrics,
} from "@/types";

const api = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

// Attach Bearer token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("nba_dashboard_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auto-logout on 401 from any API call
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err?.response?.status === 401) {
      localStorage.removeItem("nba_dashboard_token");
      localStorage.removeItem("nba_dashboard_user");
      window.location.reload();
    }
    return Promise.reject(err);
  }
);

// --- Health ---
export const getHealth = () =>
  api.get<HealthResponse>("/health").then((r) => r.data);

// --- Opportunities ---
export interface OpportunityFilters {
  min_ev?: number;
  max_ev?: number;
  confidence?: string;
  team?: string;
  market?: string;
  sort_by?: string;
  limit?: number;
}

export const getOpportunities = (filters: OpportunityFilters = {}) =>
  api
    .get<OpportunitiesListResponse>("/opportunities", { params: filters })
    .then((r) => r.data);

export const getOpportunitiesForGame = (gameId: string) =>
  api.get<Opportunity[]>(`/opportunities/${gameId}`).then((r) => r.data);

// --- Analysis ---
export const triggerAnalysis = (request: AnalysisRunRequest) =>
  api.post<AnalysisRunResponse>("/analysis/run", request).then((r) => r.data);

export const getAnalysisStatus = (runId: string) =>
  api.get<AnalysisStatus>(`/analysis/${runId}`).then((r) => r.data);

export const getLatestAnalysis = () =>
  api.get<AnalysisStatus>("/analysis/latest").then((r) => r.data);

// --- Odds ---
export const getOddsComparison = (gameId: string) =>
  api.get<OddsComparison>(`/odds/${gameId}/comparison`).then((r) => r.data);

// --- Metrics ---
export const getSportsbookMetrics = () =>
  api.get<SportsbookMetrics[]>("/metrics/sportsbooks").then((r) => r.data);

export const getCacheMetrics = () =>
  api.get<CacheMetrics>("/metrics/cache").then((r) => r.data);

// --- History ---
export const getPerformance = (season?: string) =>
  api
    .get<PerformanceSummary>("/history/performance", {
      params: season ? { season } : {},
    })
    .then((r) => r.data);

export const getMonthlyROI = (season?: string) =>
  api
    .get<MonthlyROI[]>("/history/monthly-roi", {
      params: season ? { season } : {},
    })
    .then((r) => r.data);

export const getModelAccuracy = (season?: string) =>
  api
    .get<ModelAccuracy>("/history/model-accuracy", {
      params: season ? { season } : {},
    })
    .then((r) => r.data);
