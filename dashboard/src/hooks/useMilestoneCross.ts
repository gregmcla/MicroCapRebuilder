import { useState } from "react";
import { milestoneTier } from "../lib/milestones";

/**
 * Returns a nonce that increments each time `returnPct` crosses UP into a higher
 * milestone tier than it held before (0 until the first crossing). Seeded with
 * the current value, so a book already above a milestone does NOT celebrate on
 * page load — only a genuine upward crossing during the session.
 *
 * Uses React's "adjust state while rendering when a prop changes" pattern
 * (https://react.dev/reference/react/useState#storing-information-from-previous-renders)
 * rather than a setState-in-effect, which the compiler flags as an anti-pattern.
 */
export function useMilestoneCross(returnPct: number): number {
  const [prev, setPrev] = useState(returnPct);
  const [nonce, setNonce] = useState(0);

  if (returnPct !== prev) {
    const tier = milestoneTier(returnPct);
    const prevTier = milestoneTier(prev);
    setPrev(returnPct);
    if (tier != null && (prevTier == null || tier > prevTier)) {
      setNonce((n) => n + 1);
    }
  }

  return nonce;
}
