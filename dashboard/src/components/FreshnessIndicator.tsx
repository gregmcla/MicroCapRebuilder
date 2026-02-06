/** Freshness indicator - shows data age with pulse animation */

import { useEffect, useState } from "react";
import { useFreshnessStore } from "../lib/store";

export default function FreshnessIndicator() {
  const { getStalenessSeverity, getTimeAgo } = useFreshnessStore();
  const [, setTick] = useState(0);

  // Re-render every 10 seconds to update "time ago" text
  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 10000);
    return () => clearInterval(interval);
  }, []);

  const severity = getStalenessSeverity("positions");
  const timeAgo = getTimeAgo("positions");

  const severityStyles = {
    fresh: "text-text-muted",
    stale: "text-warning animate-pulse-slow",
    "very-stale": "text-warning animate-pulse-fast",
    critical: "text-loss animate-pulse-fast",
  };

  const style = severityStyles[severity];

  return (
    <div className="flex items-center gap-1.5">
      <span className={`text-xs font-medium ${style}`}>
        Updated {timeAgo}
      </span>
    </div>
  );
}
