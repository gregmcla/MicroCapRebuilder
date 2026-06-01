/** Shared hook — cross-portfolio action handlers (Update All, Scan All, Analyze All, + New). */

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { usePortfolios } from "./usePortfolios";
import { useAnalysisStore } from "../lib/store";
import { play } from "../lib/sounds";

export function usePortfolioActions() {
  const qc = useQueryClient();
  const { data: portfolioList } = usePortfolios();
  const setPortfolioAnalysis = useAnalysisStore((s) => s.setPortfolioAnalysis);
  const clearAllAnalyses = useAnalysisStore((s) => s.clearAllAnalyses);

  const [showCreate, setShowCreate] = useState(false);

  // Update All
  const [updatingAll, setUpdatingAll] = useState(false);
  const [updateLabel, setUpdateLabel] = useState<string | null>(null);

  // Scan All
  const [scanRunning, setScanRunning] = useState(false);
  const [scanLabel, setScanLabel] = useState<string | null>(null);

  // Analyze All
  const [analyzeRunning, setAnalyzeRunning] = useState(false);
  const [analyzeLabel, setAnalyzeLabel] = useState<string | null>(null);

  const activeIds = (): string[] =>
    (portfolioList?.portfolios ?? [])
      .filter((p: { id: string; active: boolean }) => p.active)
      .map((p: { id: string; active: boolean }) => p.id);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["overview"] });
    qc.invalidateQueries({ queryKey: ["digest"] });
  };

  // ── Update All ────────────────────────────────────────────────────────────
  const updateAll = async () => {
    const ids = activeIds();
    if (!ids.length || updatingAll) return;
    play("update");
    setUpdatingAll(true);
    let done = 0;
    setUpdateLabel(`0 / ${ids.length}`);
    const withTimeout = (p: Promise<unknown>, ms: number) =>
      Promise.race([
        p,
        new Promise<never>((_, rej) =>
          setTimeout(() => rej(new Error("timeout")), ms),
        ),
      ]);
    try {
      await Promise.allSettled(
        ids.map((pid) =>
          withTimeout(api.updatePrices(pid), 30_000).finally(() => {
            done += 1;
            setUpdateLabel(`${done} / ${ids.length}`);
          }),
        ),
      );
      invalidate();
      setUpdateLabel(`${ids.length} updated`);
      setTimeout(() => setUpdateLabel(null), 3000);
    } finally {
      setUpdatingAll(false);
    }
  };

  // ── Scan All ──────────────────────────────────────────────────────────────
  const scanAll = async () => {
    const ids = activeIds();
    if (!ids.length || scanRunning) return;
    play("scan");
    setScanRunning(true);
    try {
      for (let i = 0; i < ids.length; i++) {
        const id = ids[i];
        setScanLabel(`${i + 1} / ${ids.length}`);
        try {
          await api.scan(id);
          const deadline = Date.now() + 9 * 60 * 1000;
          while (Date.now() < deadline) {
            await new Promise((res) => setTimeout(res, 3000));
            const st = await api.scanStatus(id);
            if (st.status !== "running") break;
          }
        } catch (e) {
          console.error("scanAll: scan failed for", id, e);
        }
      }
      invalidate();
      play("scanComplete");
      setScanLabel("done");
      setTimeout(() => setScanLabel(null), 4000);
    } finally {
      setScanRunning(false);
    }
  };

  // ── Analyze All ───────────────────────────────────────────────────────────
  const analyzeAll = async () => {
    const ids = activeIds();
    if (!ids.length || analyzeRunning) return;
    setAnalyzeRunning(true);
    clearAllAnalyses();
    try {
      for (let i = 0; i < ids.length; i++) {
        const id = ids[i];
        setAnalyzeLabel(`${i + 1} / ${ids.length}`);
        setPortfolioAnalysis(id, "full", { status: "running", result: null, error: null });
        try {
          const result = await api.analyze(id);
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
      setAnalyzeLabel("done");
      setTimeout(() => setAnalyzeLabel(null), 4000);
    } finally {
      setAnalyzeRunning(false);
    }
  };

  return {
    showCreate,
    setShowCreate,
    updateAll,
    updatingAll,
    updateLabel,
    scanAll,
    scanRunning,
    scanLabel,
    analyzeAll,
    analyzeRunning,
    analyzeLabel,
  };
}
