import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useFreshnessStore } from "../lib/store";

export function useChartData(ticker: string, range: string = "20D") {
  const updateTimestamp = useFreshnessStore((s) => s.updateTimestamp);

  return useQuery({
    queryKey: ["chartData", ticker, range],
    queryFn: async () => {
      const data = await api.getChartData(ticker, range);
      updateTimestamp(`chart:${ticker}`);
      return data;
    },
    staleTime: 60_000, // 1 minute cache — charts don't need to refetch every render
    gcTime: 60_000, // Keep in cache for 1 minute
  });
}
