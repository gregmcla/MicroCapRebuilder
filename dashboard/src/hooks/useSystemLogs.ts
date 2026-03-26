/** TanStack Query hooks for system logs and Claude narrative. */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { SystemLogsResponse, NarrativeResponse } from "../lib/types";

export function useSystemLogs() {
  return useQuery<SystemLogsResponse>({
    queryKey: ["system-logs"],
    queryFn: () => api.getSystemLogs(),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export function useSystemNarrative(logDate?: string) {
  return useQuery<NarrativeResponse>({
    queryKey: ["system-narrative", logDate],
    queryFn: () => api.generateNarrative(logDate),
    staleTime: 10 * 60 * 1000,  // 10 min — matches server cache
    retry: false,               // don't retry Claude failures
  });
}

export function useRegenerateNarrative() {
  const queryClient = useQueryClient();
  // Calls with regenerate=true so the server bypasses its 10-min cache,
  // then writes the result directly into the query cache.
  return async (logDate?: string) => {
    const result = await api.generateNarrative(logDate, true);
    queryClient.setQueryData(["system-narrative", logDate], result);
  };
}
