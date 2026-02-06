import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useFreshnessStore } from "../lib/store";
import type { MarketIndices } from "../lib/types";

export function useMarketIndices() {
  const updateTimestamp = useFreshnessStore((s) => s.updateTimestamp);

  return useQuery<MarketIndices>({
    queryKey: ["marketIndices"],
    queryFn: async () => {
      const data = await api.getMarketIndices();
      updateTimestamp("marketData");
      return data;
    },
    refetchInterval: 60_000, // Auto-refresh every minute
    staleTime: 50_000,
  });
}
