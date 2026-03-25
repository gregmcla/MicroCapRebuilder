/** Daily report tab — text report generated from portfolio state. */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { usePortfolioStore } from "../lib/store";

export default function ReportTab() {
  const pid = usePortfolioStore((s) => s.activePortfolioId);
  const [refreshKey, setRefreshKey] = useState(0);

  const { data, isLoading, error, isFetching } = useQuery({
    queryKey: ["report", pid, refreshKey],
    queryFn: () => api.getDailyReport(pid),
    staleTime: 60_000,
    enabled: pid !== "overview",
  });

  if (pid === "overview") {
    return (
      <div className="p-4 text-xs" style={{ color: "var(--text-2)" }}>
        Select a portfolio to view its daily report.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 py-2 shrink-0 border-b"
        style={{ borderColor: "var(--border-0)" }}
      >
        <span className="text-xs font-medium" style={{ color: "var(--text-1)" }}>
          Daily Report
        </span>
        <button
          onClick={() => setRefreshKey((k) => k + 1)}
          disabled={isFetching}
          className="text-xs px-2 py-1 rounded transition-colors"
          style={{
            color: isFetching ? "var(--text-2)" : "var(--accent-bright)",
            background: "rgba(255,255,255,0.04)",
            border: "1px solid var(--border-0)",
            cursor: isFetching ? "default" : "pointer",
          }}
        >
          {isFetching ? "Generating…" : "Regenerate"}
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3">
        {isLoading && (
          <div className="text-xs" style={{ color: "var(--text-2)" }}>
            Generating report…
          </div>
        )}
        {error && (
          <div className="text-xs" style={{ color: "var(--red)" }}>
            Failed to generate report.
          </div>
        )}
        {data && (
          <pre
            className="text-xs leading-relaxed whitespace-pre-wrap font-mono"
            style={{ color: "var(--text-1)" }}
          >
            {data.text}
          </pre>
        )}
      </div>
    </div>
  );
}
