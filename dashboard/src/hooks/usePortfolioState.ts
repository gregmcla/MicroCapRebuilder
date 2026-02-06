/** TanStack Query hook for portfolio state with 30s polling. */

import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { PortfolioState } from "../lib/types";

export function usePortfolioState() {
  return useQuery<PortfolioState>({
    queryKey: ["portfolioState"],
    queryFn: api.getState,
    refetchInterval: 30_000,
  });
}

export function usePortfolioRefresh() {
  return useQuery<PortfolioState>({
    queryKey: ["portfolioState"],
    queryFn: api.refreshState,
    enabled: false, // only runs when manually triggered
  });
}
