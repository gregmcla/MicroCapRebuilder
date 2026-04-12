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
      <div className="p-4" style={{ fontSize: 12, color: "var(--text-secondary)" }}>
        Select a portfolio to view its daily report.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 py-2 shrink-0"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <span style={{ fontSize: 11, fontWeight: 500, color: "var(--text-secondary)" }}>
          Daily Report
        </span>
        <button
          onClick={() => setRefreshKey((k) => k + 1)}
          disabled={isFetching}
          style={{
            fontSize: 11,
            padding: "3px 8px",
            borderRadius: "var(--radius)",
            color: isFetching ? "var(--text-muted)" : "var(--accent)",
            background: "var(--accent-dim)",
            border: "none",
            cursor: isFetching ? "default" : "pointer",
            transition: "opacity 0.15s",
            opacity: isFetching ? 0.6 : 1,
          }}
        >
          {isFetching ? "Generating…" : "Regenerate"}
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3">
        {isLoading && (
          <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
            Generating report…
          </div>
        )}
        {error && (
          <div style={{ fontSize: 12, color: "var(--red)" }}>
            Failed to generate report.
          </div>
        )}
        {data && (
          <pre
            style={{
              fontSize: 13,
              lineHeight: 1.6,
              whiteSpace: "pre-wrap",
              fontFamily: "var(--font-sans)",
              color: "var(--text-secondary)",
            }}
          >
            {data.text}
          </pre>
        )}
        {data && (
          <p style={{ fontSize: 10, color: "var(--text-dim)", marginTop: 12 }}>
            Generated at {new Date().toLocaleTimeString()}
          </p>
        )}
      </div>
    </div>
  );
}
