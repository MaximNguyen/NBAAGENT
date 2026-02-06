import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getHealth,
  getOpportunities,
  getOpportunitiesForGame,
  triggerAnalysis,
  getAnalysisStatus,
  getLatestAnalysis,
  getOddsComparison,
  getSportsbookMetrics,
  getCacheMetrics,
  getPerformance,
  getMonthlyROI,
  getModelAccuracy,
  type OpportunityFilters,
} from "./client";
import type { AnalysisRunRequest } from "@/types";

// --- Health ---
export const useHealth = () =>
  useQuery({ queryKey: ["health"], queryFn: getHealth, refetchInterval: 30000 });

// --- Opportunities ---
export const useOpportunities = (filters: OpportunityFilters = {}) =>
  useQuery({
    queryKey: ["opportunities", filters],
    queryFn: () => getOpportunities(filters),
    refetchInterval: 10000,
  });

export const useGameOpportunities = (gameId: string) =>
  useQuery({
    queryKey: ["opportunities", "game", gameId],
    queryFn: () => getOpportunitiesForGame(gameId),
    enabled: !!gameId,
  });

// --- Analysis ---
export const useTriggerAnalysis = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: AnalysisRunRequest) => triggerAnalysis(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["opportunities"] });
      queryClient.invalidateQueries({ queryKey: ["analysis"] });
    },
  });
};

export const useAnalysisStatus = (runId: string | null) =>
  useQuery({
    queryKey: ["analysis", runId],
    queryFn: () => getAnalysisStatus(runId!),
    enabled: !!runId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "completed" || status === "error") return false;
      return 2000;
    },
  });

export const useLatestAnalysis = () =>
  useQuery({
    queryKey: ["analysis", "latest"],
    queryFn: getLatestAnalysis,
  });

// --- Odds ---
export const useOddsComparison = (gameId: string) =>
  useQuery({
    queryKey: ["odds", gameId],
    queryFn: () => getOddsComparison(gameId),
    enabled: !!gameId,
  });

// --- Metrics ---
export const useSportsbookMetrics = () =>
  useQuery({
    queryKey: ["metrics", "sportsbooks"],
    queryFn: getSportsbookMetrics,
    refetchInterval: 30000,
  });

export const useCacheMetrics = () =>
  useQuery({
    queryKey: ["metrics", "cache"],
    queryFn: getCacheMetrics,
    refetchInterval: 30000,
  });

// --- History ---
export const usePerformance = (season?: string) =>
  useQuery({
    queryKey: ["history", "performance", season],
    queryFn: () => getPerformance(season),
  });

export const useMonthlyROI = (season?: string) =>
  useQuery({
    queryKey: ["history", "monthly-roi", season],
    queryFn: () => getMonthlyROI(season),
  });

export const useModelAccuracy = (season?: string) =>
  useQuery({
    queryKey: ["history", "model-accuracy", season],
    queryFn: () => getModelAccuracy(season),
  });
