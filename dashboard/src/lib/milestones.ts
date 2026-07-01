/** All-time return milestones — the tiers a book "graduates" through. */

const TIERS = [500, 200, 100, 50, 25] as const; // descending

/** Highest milestone tier reached by an all-time return %, or null if below 25%. */
export function milestoneTier(returnPct: number): number | null {
  if (Number.isNaN(returnPct)) return null;
  for (const t of TIERS) {
    if (returnPct >= t) return t;
  }
  return null;
}

export function milestoneLabel(tier: number): string {
  return `+${tier}%`;
}
