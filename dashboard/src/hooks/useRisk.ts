/** Hooks for risk and warning data. */

import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { RiskScoreboard, Warning } from "../lib/types";

export function useRisk() {
  return useQuery<RiskScoreboard>({
    queryKey: ["risk"],
    queryFn: api.getRisk,
    refetchInterval: 60_000,
  });
}

export function useWarnings() {
  return useQuery<Warning[]>({
    queryKey: ["warnings"],
    queryFn: api.getWarnings,
    refetchInterval: 60_000,
  });
}
