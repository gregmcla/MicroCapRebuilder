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

  // Map severity to design token colors and animations
  const severityStyle: Record<string, React.CSSProperties> = {
    fresh: { color: "var(--text-1)" },
    stale: { color: "var(--amber)" },
    "very-stale": { color: "var(--amber)" },
    critical: { color: "var(--red)" },
  };

  const severityClass: Record<string, string> = {
    fresh: "",
    stale: "animate-pulse-slow",
    "very-stale": "animate-pulse-fast",
    critical: "animate-pulse-fast",
  };

  return (
    <div className="flex items-center gap-1.5">
      <span
        className={`text-xs font-medium ${severityClass[severity] ?? ""}`}
        style={severityStyle[severity] ?? { color: "var(--text-1)" }}
      >
        Updated {timeAgo}
      </span>
    </div>
  );
}
