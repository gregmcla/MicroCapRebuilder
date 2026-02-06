/** Hooks for performance and learning data. */

import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { PerformanceData, LearningData } from "../lib/types";

export function usePerformance() {
  return useQuery<PerformanceData>({
    queryKey: ["performance"],
    queryFn: api.getPerformance,
    refetchInterval: 120_000,
  });
}

export function useLearning() {
  return useQuery<LearningData>({
    queryKey: ["learning"],
    queryFn: api.getLearning,
    refetchInterval: 300_000,
  });
}
