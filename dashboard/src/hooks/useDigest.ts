/** Query hooks for the Daily Digest endpoints. */

import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { DigestData, DigestNarrative } from "../lib/types";

export function useDigest(range = "3M") {
  return useQuery<DigestData>({
    queryKey: ["digest", range],
    queryFn: () => api.getDigest(range),
    staleTime: 45_000,
  });
}

export function useDigestNarrative(range = "3M") {
  return useQuery<DigestNarrative>({
    queryKey: ["digest-narrative", range],
    queryFn: () => api.getDigestNarrative(range),
    staleTime: Infinity,
  });
}
