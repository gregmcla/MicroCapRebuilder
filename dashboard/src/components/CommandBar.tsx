/** Command bar — UPDATE · SCAN · ANALYZE · EXECUTE. Sits below TopBar. */

import { useState, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAnalysisStore, useFreshnessStore, usePortfolioStore } from "../lib/store";
import type { ScanResult } from "../lib/types";
import { api } from "../lib/api";

// ---------------------------------------------------------------------------
// Shared styles
// ---------------------------------------------------------------------------

const BASE = "inline-flex items-center gap-1.5 font-semibold tracking-widest uppercase transition-all duration-150 rounded-[6px] disabled:opacity-40 disabled:cursor-not-allowed";

// UPDATE — blue
const BLUE_BTN = BASE
  + " border border-sky-400/40 bg-sky-400/[0.07] text-sky-400"
  + " hover:border-sky-400/70 hover:bg-sky-400/[0.13]";

// SCAN — amber
const AMBER_BTN = BASE
  + " border border-amber-400/40 bg-amber-400/[0.07] text-amber-400"
  + " hover:border-amber-400/70 hover:bg-amber-400/[0.13]";

// ANALYZE / EXECUTE — green accent
const ACCENT_BTN = BASE
  + " border border-[var(--accent)]/40 bg-[var(--accent)]/[0.08] text-[var(--accent)]"
  + " hover:border-[var(--accent)]/70 hover:bg-[var(--accent)]/[0.14]";


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
      className={BLUE_BTN}
      title={result || undefined}
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
      className={AMBER_BTN}
      title={resultText || undefined}
      style={{ fontSize: "10px", height: "28px", padding: "0 12px", ...errorStyle }}
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
        onClick={runAnalysis}
        disabled={isAnalyzing}
        className={ACCENT_BTN}
        style={{ fontSize: "10px", height: "28px", padding: "0 14px" }}
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
          className={ACCENT_BTN}
          style={{ fontSize: "10px", height: "28px", padding: "0 14px" }}
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
