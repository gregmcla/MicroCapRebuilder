/** Hooks for risk and warning data. */

import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { usePortfolioStore } from "../lib/store";
import type { RiskScoreboard, Warning } from "../lib/types";

export function useRisk() {
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);

  return useQuery<RiskScoreboard>({
    queryKey: ["risk", portfolioId],
    queryFn: () => api.getRisk(portfolioId),
    refetchInterval: 60_000,
    enabled: portfolioId !== "overview",
  });
}

export function useWarnings() {
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);

  return useQuery<Warning[]>({
    queryKey: ["warnings", portfolioId],
    queryFn: () => api.getWarnings(portfolioId),
    refetchInterval: 60_000,
    enabled: portfolioId !== "overview",
  });
}
