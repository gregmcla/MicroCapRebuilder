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
    staleTime: 300_000, // 5 minutes
  });
}
