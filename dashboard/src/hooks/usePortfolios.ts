/** Hooks for portfolio list and overview data. */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { PortfolioList, OverviewData, CreatePortfolioRequest } from "../lib/types";

export function usePortfolios() {
  return useQuery<PortfolioList>({
    queryKey: ["portfolios"],
    queryFn: api.getPortfolios,
    refetchInterval: 60_000,
  });
}

export function useOverview() {
  return useQuery<OverviewData>({
    queryKey: ["overview"],
    queryFn: api.getOverview,
    refetchInterval: 30_000,
  });
}

export function useCreatePortfolio() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (req: CreatePortfolioRequest) => api.createPortfolio(req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
    },
  });
}
