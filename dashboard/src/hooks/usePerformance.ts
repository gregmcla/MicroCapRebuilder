/** Hooks for performance and learning data. */

import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { usePortfolioStore } from "../lib/store";
import type { PerformanceData, LearningData } from "../lib/types";

export function usePerformance() {
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);

  return useQuery<PerformanceData>({
    queryKey: ["performance", portfolioId],
    queryFn: () => api.getPerformance(portfolioId),
    refetchInterval: 120_000,
    enabled: portfolioId !== "overview" && portfolioId !== "logs",
  });
}

export function useLearning() {
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);

  return useQuery<LearningData>({
    queryKey: ["learning", portfolioId],
    queryFn: () => api.getLearning(portfolioId),
    refetchInterval: 300_000,
    enabled: portfolioId !== "overview" && portfolioId !== "logs",
  });
}
