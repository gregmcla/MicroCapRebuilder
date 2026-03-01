/** Command bar — UPDATE · SCAN · ANALYZE · EXECUTE. Sits below TopBar. */

import { useState, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAnalysisStore, useFreshnessStore, usePortfolioStore } from "../lib/store";
import type { ScanResult } from "../lib/types";
import { api } from "../lib/api";

// ---------------------------------------------------------------------------
// Shared styles
// ---------------------------------------------------------------------------

const GHOST =
  "inline-flex items-center gap-1.5 font-semibold tracking-widest uppercase transition-all duration-150 rounded-md disabled:opacity-40 disabled:cursor-not-allowed"
  + " border border-white/[0.09] bg-white/[0.04] text-[var(--text-1)]"
  + " hover:border-white/[0.16] hover:bg-white/[0.07] hover:text-[var(--text-3)]";

const GHOST_AMBER =
  "inline-flex items-center gap-1.5 font-semibold tracking-widest uppercase transition-all duration-150 rounded-md disabled:opacity-40 disabled:cursor-not-allowed"
  + " border border-amber-400/[0.18] bg-amber-400/[0.04] text-amber-400/70"
  + " hover:border-amber-400/[0.30] hover:bg-amber-400/[0.08] hover:text-amber-400";

const HERO =
  "inline-flex items-center gap-2 font-bold tracking-widest uppercase transition-all duration-150 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
  + " text-white";

// ---------------------------------------------------------------------------
// Update button
// ---------------------------------------------------------------------------

function UpdateButton() {
  const queryClient = useQueryClient();
  const updateTimestamp = useFreshnessStore((s) => s.updateTimestamp);
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const [updating, setUpdating] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handle = async () => {
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
    <div className="flex items-center gap-2">
      <button
        onClick={handle}
        disabled={updating}
        className={GHOST}
        style={{ fontSize: "10px", height: "28px", padding: "0 12px" }}
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
      {result && (
        <span style={{ fontSize: "10px", color: "var(--text-0)" }}>{result}</span>
      )}
    </div>
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

function ScanButton() {
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
          refetchStatus();
          queryClient.invalidateQueries({ queryKey: ["portfolioState"] });
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
  let resultColor = "var(--text-0)";
  if (scanError) {
    resultText = scanError;
    resultColor = "var(--red)";
  } else if (!scanning && lastStatus?.status === "complete" && lastStatus.result) {
    resultText = fmtScanResult(lastStatus.result, lastStatus.finished_at);
  } else if (!scanning && lastStatus?.status === "error") {
    resultText = lastStatus.error ?? "Scan failed";
    resultColor = "rgba(248,113,113,0.7)";
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={handle}
        disabled={scanning}
        className={GHOST_AMBER}
        style={{ fontSize: "10px", height: "28px", padding: "0 12px" }}
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
      {resultText && (
        <span style={{ fontSize: "9.5px", color: resultColor, maxWidth: "220px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {resultText}
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Analyze + Execute
// ---------------------------------------------------------------------------

function AnalyzeExecute() {
  const { result, isAnalyzing, isExecuting, runAnalysis, runExecute } = useAnalysisStore();
  const actionCount = result ? result.summary.approved + result.summary.modified : 0;

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={runAnalysis}
        disabled={isAnalyzing}
        className={HERO}
        style={{
          fontSize: "11px",
          height: "34px",
          padding: "0 22px",
          background: isAnalyzing
            ? "linear-gradient(135deg, rgba(124,92,252,0.7), rgba(155,126,255,0.7))"
            : "linear-gradient(135deg, #7c5cfc 0%, #9b7eff 100%)",
          boxShadow: isAnalyzing
            ? "0 0 24px rgba(124,92,252,0.25)"
            : "0 0 20px rgba(124,92,252,0.40), inset 0 1px 0 rgba(255,255,255,0.15)",
        }}
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
          onClick={runExecute}
          disabled={isExecuting}
          className={HERO}
          style={{
            fontSize: "11px",
            height: "34px",
            padding: "0 18px",
            background: "linear-gradient(135deg, #10b981 0%, #34d399 100%)",
            boxShadow: "0 0 16px rgba(52,211,153,0.35), inset 0 1px 0 rgba(255,255,255,0.15)",
          }}
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
