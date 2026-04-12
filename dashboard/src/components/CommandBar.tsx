/** Command bar — UPDATE · SCAN · ANALYZE · EXECUTE. Sits below TopBar. */

import React, { useState, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAnalysisStore, useFreshnessStore, usePortfolioStore } from "../lib/store";
import type { ScanResult } from "../lib/types";
import { api } from "../lib/api";
import { play } from "../lib/sounds";

// ---------------------------------------------------------------------------
// Shared styles
// ---------------------------------------------------------------------------

const BASE = "inline-flex items-center gap-1.5 tracking-widest uppercase disabled:opacity-40 disabled:cursor-not-allowed";

const BTN_BASE: React.CSSProperties = {
  height: "30px",
  fontSize: 11,
  fontWeight: 600,
  borderRadius: 6,
  border: "1px solid",
  transition: "all 150ms ease",
  padding: "0 12px",
};

const BLUE_STYLE: React.CSSProperties = {
  ...BTN_BASE,
  color: "var(--blue)",
  background: "rgba(59,130,246,0.1)",
  borderColor: "rgba(59,130,246,0.2)",
};

const AMBER_STYLE: React.CSSProperties = {
  ...BTN_BASE,
  color: "var(--amber)",
  background: "var(--amber-dim)",
  borderColor: "rgba(245,158,11,0.2)",
};

const ACCENT_STYLE: React.CSSProperties = {
  ...BTN_BASE,
  color: "var(--accent)",
  background: "var(--accent-dim)",
  borderColor: "rgba(139,92,246,0.2)",
};

const EXECUTE_STYLE: React.CSSProperties = {
  ...BTN_BASE,
  color: "#C4B5FD",
  background: "rgba(139,92,246,0.2)",
  borderColor: "rgba(139,92,246,0.3)",
};


// ---------------------------------------------------------------------------
// Update button
// ---------------------------------------------------------------------------

export function UpdateButton() {
  const queryClient = useQueryClient();
  const updateTimestamp = useFreshnessStore((s) => s.updateTimestamp);
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const [updating, setUpdating] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handle = async () => {
    play("update");
    setUpdating(true);
    setResult(null);
    try {
      const res = await api.updatePrices(portfolioId);
      updateTimestamp("positions");
      setResult(`${res.num_positions} updated`);
      queryClient.invalidateQueries({ queryKey: ["portfolioState"] });
      queryClient.invalidateQueries({ queryKey: ["chartData"] });
      setTimeout(() => setResult(null), 3000);
    } catch {
      setResult("Failed");
      setTimeout(() => setResult(null), 4000);
    } finally {
      setUpdating(false);
    }
  };

  return (
    <button
      onClick={handle}
      disabled={updating}
      className={BASE}
      title={result || undefined}
      style={BLUE_STYLE}
    >
      {/* Refresh icon */}
      <svg
        width="11" height="11" viewBox="0 0 12 12" fill="none"
        className={updating ? "animate-spin" : ""}
        style={{ flexShrink: 0 }}
      >
        <path
          d="M10 6A4 4 0 1 1 6 2a4 4 0 0 1 2.83 1.17L10 2v4H6"
          stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"
        />
      </svg>
      {updating ? "Updating" : "Update"}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Scan button
// ---------------------------------------------------------------------------

function relTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const sec = (Date.now() - new Date(iso).getTime()) / 1000;
  if (sec < 90) return "just now";
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return `${Math.floor(sec / 86400)}d ago`;
}

function fmtScanResult(r: ScanResult, finishedAt?: string | null): string {
  const parts = [`+${r.added} added`, `${r.total_active} active`];
  if (r.marked_stale > 0) parts.push(`${r.marked_stale} stale`);
  if (finishedAt) parts.push(relTime(finishedAt));
  return parts.join(" · ");
}

export function ScanButton() {
  const queryClient = useQueryClient();
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Persistent last-scan result — fetched on mount, lives until page reload
  const { data: lastStatus, refetch: refetchStatus } = useQuery({
    queryKey: ["scanStatus", portfolioId],
    queryFn: () => api.scanStatus(portfolioId),
    staleTime: Infinity,
    retry: false,
  });

  const stop = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  const handle = async () => {
    play("scan");
    setScanning(true);
    setScanError(null);
    try {
      await api.scan(portfolioId);
    } catch (e) {
      setScanning(false);
      setScanError(e instanceof Error ? e.message : "Failed");
      return;
    }
    const start = Date.now();
    pollRef.current = setInterval(async () => {
      try {
        const s = await api.scanStatus(portfolioId);
        if (s.status === "complete" && s.result) {
          stop(); setScanning(false);
          play("scanComplete");
          refetchStatus();
          queryClient.invalidateQueries({ queryKey: ["portfolioState"] });
          queryClient.invalidateQueries({ queryKey: ["watchlist"] });
        } else if (s.status === "error") {
          stop(); setScanning(false);
          refetchStatus();
        } else if (s.status === "idle" || Date.now() - start > 10 * 60 * 1000) {
          stop(); setScanning(false);
        }
      } catch { /* keep polling */ }
    }, 10_000);
  };

  // Derive display text
  let resultText = "";
  if (scanError) {
    resultText = scanError;
  } else if (!scanning && lastStatus?.status === "complete" && lastStatus.result) {
    resultText = fmtScanResult(lastStatus.result, lastStatus.finished_at);
  } else if (!scanning && lastStatus?.status === "error") {
    resultText = lastStatus.error ?? "Scan failed";
  }

  const isError = !scanning && lastStatus?.status === "error";
  const errorStyle = isError
    ? { borderColor: "rgba(248,113,113,0.45)", color: "rgba(248,113,113,0.8)", background: "rgba(248,113,113,0.07)" }
    : {};

  return (
    <button
      onClick={handle}
      disabled={scanning}
      className={BASE}
      title={resultText || undefined}
      style={{ ...AMBER_STYLE, ...errorStyle }}
    >
      <span
        style={{
          width: "7px", height: "7px", borderRadius: "50%",
          background: "currentColor", opacity: scanning ? 1 : 0.6, flexShrink: 0,
          animation: scanning ? "pulse 1s ease-in-out infinite" : "none",
        }}
      />
      {scanning ? "Scanning" : "Scan"}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Analyze + Execute
// ---------------------------------------------------------------------------

export function AnalyzeExecute() {
  const { result, isAnalyzing, isExecuting, runAnalysis, runExecute } = useAnalysisStore();
  const actionCount = result ? result.summary.approved + result.summary.modified : 0;

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => { play("analyze"); runAnalysis(); }}
        disabled={isAnalyzing}
        className={BASE}
        style={ACCENT_STYLE}
      >
        {/* Sparkle */}
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ flexShrink: 0 }}>
          <path
            d="M6 1v2M6 9v2M1 6h2M9 6h2M2.64 2.64l1.42 1.42M7.94 7.94l1.42 1.42M2.64 9.36l1.42-1.42M7.94 4.06l1.42-1.42"
            stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"
          />
        </svg>
        {isAnalyzing ? "Analyzing…" : "Analyze"}
      </button>

      {actionCount > 0 && (
        <button
          onClick={() => { play("execute"); runExecute(); }}
          disabled={isExecuting}
          className={BASE}
          style={EXECUTE_STYLE}
        >
          {/* Play icon */}
          <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor" style={{ flexShrink: 0 }}>
            <path d="M2 1.5l7 3.5-7 3.5V1.5z" />
          </svg>
          {isExecuting ? "Executing…" : `Execute ${actionCount}`}
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// CommandBar
// ---------------------------------------------------------------------------

export default function CommandBar() {
  return (
    <div
      className="flex items-center justify-center gap-3 shrink-0"
      style={{
        height: "44px",
        background: "var(--surface-1)",
        borderBottom: "1px solid var(--border-0)",
      }}
    >
      {/* Operational buttons */}
      <UpdateButton />
      <ScanButton />

      {/* Separator */}
      <div
        style={{
          width: "1px", height: "18px",
          background: "var(--border-1)",
          flexShrink: 0,
        }}
      />

      {/* AI buttons */}
      <AnalyzeExecute />
    </div>
  );
}
