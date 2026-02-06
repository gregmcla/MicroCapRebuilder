/** Zustand store — shared UI state across components. */

import { create } from "zustand";
import type { AnalysisResult } from "./types";
import { api } from "./api";

interface AnalysisStore {
  result: AnalysisResult | null;
  isAnalyzing: boolean;
  isExecuting: boolean;
  error: string | null;
  lastAnalyzedAt: string | null;

  runAnalysis: () => Promise<void>;
  runExecute: () => Promise<void>;
  clear: () => void;
}

export const useAnalysisStore = create<AnalysisStore>((set, get) => ({
  result: null,
  isAnalyzing: false,
  isExecuting: false,
  error: null,
  lastAnalyzedAt: null,

  runAnalysis: async () => {
    set({ isAnalyzing: true, error: null });
    try {
      const result = await api.analyze();
      set({
        result,
        isAnalyzing: false,
        lastAnalyzedAt: new Date().toLocaleTimeString(),
      });
    } catch (e) {
      set({
        isAnalyzing: false,
        error: e instanceof Error ? e.message : "Analysis failed",
      });
    }
  },

  runExecute: async () => {
    if (!get().result?.summary.can_execute) return;
    set({ isExecuting: true, error: null });
    try {
      await api.execute();
      set({ isExecuting: false, result: null, lastAnalyzedAt: null });
    } catch (e) {
      set({
        isExecuting: false,
        error: e instanceof Error ? e.message : "Execution failed",
      });
    }
  },

  clear: () => set({ result: null, error: null, lastAnalyzedAt: null }),
}));
