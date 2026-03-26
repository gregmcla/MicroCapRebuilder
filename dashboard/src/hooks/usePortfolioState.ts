/** TanStack Query hook for portfolio state with 30s polling. */

import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { usePortfolioStore } from "../lib/store";
import type { PortfolioState } from "../lib/types";

export function usePortfolioState() {
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);

  return useQuery<PortfolioState>({
    queryKey: ["portfolioState", portfolioId],
    queryFn: () => api.getState(portfolioId),
    refetchInterval: 30_000,
    enabled: portfolioId !== "overview" && portfolioId !== "logs",
  });
}

export function usePortfolioRefresh() {
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);

  return useQuery<PortfolioState>({
    queryKey: ["portfolioState", portfolioId],
    queryFn: () => api.refreshState(portfolioId),
    enabled: false, // only runs when manually triggered
  });
}
