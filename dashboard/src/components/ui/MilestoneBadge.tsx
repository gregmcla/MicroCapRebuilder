/** A gold milestone chip for books up ≥25% all-time. When the book crosses UP
 *  into a new tier during the session it pops + plays the milestone sound —
 *  a genuine "you just hit a win" moment (not a page-load spam). */

import { useEffect } from "react";
import type { CSSProperties } from "react";
import { milestoneTier, milestoneLabel } from "../../lib/milestones";
import { useMilestoneCross } from "../../hooks/useMilestoneCross";
import { play } from "../../lib/sounds";

export function MilestoneBadge({ returnPct, style }: { returnPct: number; style?: CSSProperties }) {
  const tier = milestoneTier(returnPct);
  const nonce = useMilestoneCross(returnPct);

  useEffect(() => {
    if (nonce > 0) play("milestone");
  }, [nonce]);

  if (tier == null) return null;

  return (
    <span
      // Remount on each fresh crossing so the pop animation replays.
      key={nonce}
      className={nonce > 0 ? "milestone-celebrate" : undefined}
      title={`Milestone — up ${milestoneLabel(tier)} all-time`}
      style={{
        display: "inline-block",
        fontSize: "8.5px",
        fontWeight: 800,
        letterSpacing: "0.03em",
        lineHeight: 1.4,
        padding: "0 5px",
        borderRadius: "999px",
        color: "#231a00",
        background: "linear-gradient(135deg, #fde68a, #f59e0b)",
        boxShadow: "0 0 8px rgba(245,158,11,0.35)",
        whiteSpace: "nowrap",
        ...style,
      }}
    >
      {milestoneLabel(tier)}
    </span>
  );
}
