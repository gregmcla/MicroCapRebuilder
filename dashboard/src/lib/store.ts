/** Zustand store — shared UI state across components. */

import { create } from "zustand";
import type { AnalysisResult, Position } from "./types";
import { api } from "./api";

// --- Portfolio Store ---

interface PortfolioStore {
  activePortfolioId: string;
  setPortfolio: (id: string) => void;
}

export const usePortfolioStore = create<PortfolioStore>((set) => ({
  activePortfolioId: "overview",
  setPortfolio: (id) => set({ activePortfolioId: id }),
}));

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

export type RightTab = "actions" | "risk" | "performance" | "report";

interface UIStore {
  rightTab: RightTab;
  setRightTab: (tab: RightTab) => void;
  selectedPosition: Position | null;
  selectPosition: (pos: Position | null) => void;
  activityOpen: boolean;
  toggleActivity: () => void;
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  theme: "dark" | "light";
  toggleTheme: () => void;
}

export const useUIStore = create<UIStore>((set) => ({
  rightTab: "actions",
  setRightTab: (tab) => set({ rightTab: tab, selectedPosition: null }),
  selectedPosition: null,
  selectPosition: (pos) => set({ selectedPosition: pos }),
  activityOpen: false,
  toggleActivity: () => set((s) => ({ activityOpen: !s.activityOpen })),
  sidebarCollapsed: (() => {
    const stored = localStorage.getItem("sidebar-collapsed");
    if (stored !== null) return stored === "true";
    return window.innerWidth < 1600;
  })(),
  toggleSidebar: () =>
    set((s) => {
      const next = !s.sidebarCollapsed;
      localStorage.setItem("sidebar-collapsed", String(next));
      return { sidebarCollapsed: next };
    }),
  theme: (() => {
    const stored = localStorage.getItem("gscott-theme");
    const t = (stored === "light" || stored === "dark") ? stored : "dark";
    document.documentElement.setAttribute("data-theme", t);
    return t;
  })() as "dark" | "light",
  toggleTheme: () =>
    set((s) => {
      const next = s.theme === "dark" ? "light" : "dark";
      localStorage.setItem("gscott-theme", next);
      document.documentElement.setAttribute("data-theme", next);
      return { theme: next };
    }),
}));

export const useAnalysisStore = create<AnalysisStore>((set, get) => ({
  result: null,
  isAnalyzing: false,
  isExecuting: false,
  error: null,
  lastAnalyzedAt: null,

  runAnalysis: async () => {
    const portfolioId = usePortfolioStore.getState().activePortfolioId;
    if (portfolioId === "overview") return;
    set({ isAnalyzing: true, error: null });
    try {
      const result = await api.analyze(portfolioId);
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
    const portfolioId = usePortfolioStore.getState().activePortfolioId;
    if (portfolioId === "overview") return;
    if (!get().result?.summary.can_execute) return;
    set({ isExecuting: true, error: null });
    try {
      await api.execute(portfolioId);
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

interface FreshnessStore {
  timestamps: Record<string, number>;
  updateTimestamp: (key: string) => void;
  getTimestamp: (key: string) => number | null;
  getStalenessSeverity: (key: string) => "fresh" | "stale" | "very-stale" | "critical";
  getTimeAgo: (key: string) => string;
}

export const useFreshnessStore = create<FreshnessStore>((set, get) => ({
  timestamps: {},
  updateTimestamp: (key) =>
    set((state) => ({
      timestamps: { ...state.timestamps, [key]: Date.now() },
    })),
  getTimestamp: (key) => get().timestamps[key] ?? null,
  getStalenessSeverity: (key) => {
    const timestamp = get().timestamps[key];
    if (!timestamp) return "critical";
    const ageMs = Date.now() - timestamp;
    const ageMin = ageMs / 60000;
    if (ageMin < 5) return "fresh";
    if (ageMin < 15) return "stale";
    if (ageMin < 60) return "very-stale";
    return "critical";
  },
  getTimeAgo: (key) => {
    const timestamp = get().timestamps[key];
    if (!timestamp) return "Never";
    const ageMs = Date.now() - timestamp;
    const ageSec = Math.floor(ageMs / 1000);
    if (ageSec < 60) return "Just now";
    const ageMin = Math.floor(ageSec / 60);
    if (ageMin < 60) return `${ageMin}m ago`;
    const ageHr = Math.floor(ageMin / 60);
    return `${ageHr}h ago`;
  },
}));
