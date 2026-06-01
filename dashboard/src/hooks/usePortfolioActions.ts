/** Shared hook — cross-portfolio action handlers (Update All, Scan All, Analyze All, + New). */

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { usePortfolios } from "./usePortfolios";
import { useAnalysisStore } from "../lib/store";
import { play } from "../lib/sounds";

type ActionStatus = {
  kind: "update" | "scan" | "analyze";
  running: boolean;
  current: string | null;   // portfolio NAME being processed
  done: number;
  total: number;
  summary: string | null;   // completion summary with counts
  error: string | null;
} | null;

export function usePortfolioActions() {
  const qc = useQueryClient();
  const { data: portfolioList } = usePortfolios();
  const setPortfolioAnalysis = useAnalysisStore((s) => s.setPortfolioAnalysis);
  const clearAllAnalyses = useAnalysisStore((s) => s.clearAllAnalyses);

  const [showCreate, setShowCreate] = useState(false);
  const [status, setStatus] = useState<ActionStatus>(null);

  const activeIds = (): string[] =>
    (portfolioList?.portfolios ?? [])
      .filter((p: { id: string; active: boolean }) => p.active)
      .map((p: { id: string; active: boolean }) => p.id);

  const nameOf = (id: string): string =>
    (portfolioList?.portfolios ?? []).find((p: any) => p.id === id)?.name ?? id;

  const sleep = (ms: number) => new Promise((res) => setTimeout(res, ms));

  const clearLater = (ms: number) =>
    setTimeout(() => setStatus((s) => (s && !s.running ? null : s)), ms);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["overview"] });
    qc.invalidateQueries({ queryKey: ["digest"] });
  };

  // ── Update All ────────────────────────────────────────────────────────────
  const updateAll = async () => {
    const ids = activeIds();
    if (!ids.length || status?.running) return;
    play("update");
    setStatus({ kind: "update", running: true, current: null, done: 0, total: ids.length, summary: null, error: null });
    let done = 0;
    const withTimeout = (p: Promise<unknown>, ms: number) =>
      Promise.race([
        p,
        new Promise<never>((_, rej) =>
          setTimeout(() => rej(new Error("timeout")), ms),
        ),
      ]);
    await Promise.allSettled(
      ids.map((pid) =>
        withTimeout(api.updatePrices(pid), 30_000).finally(() => {
          done += 1;
          setStatus((s) => (s ? { ...s, done } : s));
        }),
      ),
    );
    invalidate();
    setStatus({ kind: "update", running: false, current: null, done: ids.length, total: ids.length, summary: `${ids.length} portfolios updated`, error: null });
    clearLater(6000);
  };

  // ── Scan All ──────────────────────────────────────────────────────────────
  const scanAll = async () => {
    const ids = activeIds();
    if (!ids.length || status?.running) return;
    play("scan");
    setStatus({ kind: "scan", running: true, current: nameOf(ids[0]), done: 0, total: ids.length, summary: null, error: null });
    let added = 0;
    for (let i = 0; i < ids.length; i++) {
      const id = ids[i];
      setStatus((s) => (s ? { ...s, current: nameOf(id), done: i } : s));
      try {
        await api.scan(id);
        const deadline = Date.now() + 9 * 60 * 1000;
        while (Date.now() < deadline) {
          await sleep(3000);
          const st: any = await api.scanStatus(id);
          if (st.status !== "running") {
            if (st.status === "complete" && st.result) {
              added += (st.result.added ?? 0);
            }
            break;
          }
        }
      } catch (e) {
        console.error("scanAll: scan failed for", id, e);
      }
    }
    invalidate();
    play("scanComplete");
    setStatus({ kind: "scan", running: false, current: null, done: ids.length, total: ids.length, summary: `Scanned ${ids.length} · ${added} candidates added`, error: null });
    clearLater(8000);
  };

  // ── Analyze All ───────────────────────────────────────────────────────────
  const analyzeAll = async () => {
    const ids = activeIds();
    if (!ids.length || status?.running) return;
    setStatus({ kind: "analyze", running: true, current: nameOf(ids[0]), done: 0, total: ids.length, summary: null, error: null });
    clearAllAnalyses();
    let proposed = 0;
    for (let i = 0; i < ids.length; i++) {
      const id = ids[i];
      setStatus((s) => (s ? { ...s, current: nameOf(id), done: i } : s));
      setPortfolioAnalysis(id, "full", { status: "running", result: null, error: null });
      try {
        const result: any = await api.analyze(id);
        // summary.total_proposed is the canonical field; fall back to approved array length
        proposed += (result?.summary?.total_proposed ?? result?.approved?.length ?? 0);
        setPortfolioAnalysis(id, "full", {
          status: "complete",
          result,
          error: null,
          analyzedAt: new Date().toLocaleTimeString(),
        });
      } catch (err) {
        setPortfolioAnalysis(id, "full", {
          status: "error",
          result: null,
          error: err instanceof Error ? err.message : "Unknown error",
        });
      }
    }
    setStatus({ kind: "analyze", running: false, current: null, done: ids.length, total: ids.length, summary: `Analyzed ${ids.length} · ${proposed} actions proposed — open a portfolio's Actions tab to review`, error: null });
    clearLater(12000);
  };

  return { status, showCreate, setShowCreate, updateAll, scanAll, analyzeAll };
}
