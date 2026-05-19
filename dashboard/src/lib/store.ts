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

export type PortfolioAnalysisStatus =
  | "idle"
  | "running"
  | "complete"
  | "error"
  | "executing"
  | "executed";

export type AnalysisMode = "full" | "buys_only" | "sells_only";

export interface AnalysisSlot {
  status: PortfolioAnalysisStatus;
  result: AnalysisResult | null;
  error: string | null;
  analyzedAt: string | null;
}

// Backward-compat alias — older code referred to per-portfolio state by this name.
export type PortfolioAnalysisState = AnalysisSlot;

const emptySlot = (): AnalysisSlot => ({
  status: "idle",
  result: null,
  error: null,
  analyzedAt: null,
});

export type AnalysisSlots = Record<AnalysisMode, AnalysisSlot>;

const emptySlots = (): AnalysisSlots => ({
  full: emptySlot(),
  buys_only: emptySlot(),
  sells_only: emptySlot(),
});

interface AnalysisStore {
  // Current-portfolio view (auto-synced from portfolioAnalyses[activePortfolioId][activeMode])
  result: AnalysisResult | null;
  isAnalyzing: boolean;
  isExecuting: boolean;
  error: string | null;
  lastAnalyzedAt: string | null;

  // Per-portfolio per-mode analysis state (persists across navigation)
  portfolioAnalyses: Record<string, AnalysisSlots>;

  // The mode currently being viewed in the dashboard (UI state)
  activeMode: AnalysisMode;
  setActiveMode: (m: AnalysisMode) => void;

  runAnalysis: (mode?: AnalysisMode) => Promise<void>;
  runExecute: (mode?: AnalysisMode, selectedTickers?: string[]) => Promise<void>;
  setPortfolioAnalysis: (pid: string, mode: AnalysisMode, patch: Partial<AnalysisSlot>) => void;
  clearPortfolioAnalysis: (pid: string) => void;
  clearAllAnalyses: () => void;
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

export const useAnalysisStore = create<AnalysisStore>((set, get) => {
  // Sync top-level `result`/`isAnalyzing`/`error`/`lastAnalyzedAt` to whatever
  // portfolio + mode is currently active, so consumers don't need to know about
  // the per-portfolio/per-mode map.
  const syncActive = () => {
    const pid = usePortfolioStore.getState().activePortfolioId;
    const mode = get().activeMode;
    const slot = get().portfolioAnalyses[pid]?.[mode];
    set({
      result: slot?.result ?? null,
      isAnalyzing: slot?.status === "running",
      isExecuting: slot?.status === "executing",
      error: slot?.error ?? null,
      lastAnalyzedAt: slot?.analyzedAt ?? null,
    });
  };

  // Rebind top-level view whenever the active portfolio changes.
  usePortfolioStore.subscribe((state, prev) => {
    if (state.activePortfolioId !== prev.activePortfolioId) syncActive();
  });

  const writeSlot = (pid: string, mode: AnalysisMode, patch: Partial<AnalysisSlot>) => {
    set((s) => {
      const portfolioSlots = s.portfolioAnalyses[pid] ?? emptySlots();
      const prev = portfolioSlots[mode];
      return {
        portfolioAnalyses: {
          ...s.portfolioAnalyses,
          [pid]: { ...portfolioSlots, [mode]: { ...prev, ...patch } },
        },
      };
    });
    syncActive();
  };

  return {
    result: null,
    isAnalyzing: false,
    isExecuting: false,
    error: null,
    lastAnalyzedAt: null,
    portfolioAnalyses: {},
    activeMode: "full",

    setActiveMode: (m: AnalysisMode) => {
      set({ activeMode: m });
      syncActive();
    },

    runAnalysis: async (mode: AnalysisMode = "full") => {
      const portfolioId = usePortfolioStore.getState().activePortfolioId;
      if (portfolioId === "overview") return;
      writeSlot(portfolioId, mode, { status: "running", error: null });
      try {
        const result = await api.analyze(portfolioId, mode);
        writeSlot(portfolioId, mode, {
          status: "complete",
          result,
          error: null,
          analyzedAt: new Date().toLocaleTimeString(),
        });
      } catch (e) {
        writeSlot(portfolioId, mode, {
          status: "error",
          error: e instanceof Error ? e.message : "Analysis failed",
        });
      }
    },

    runExecute: async (mode: AnalysisMode = "full", selectedTickers?: string[]) => {
      const portfolioId = usePortfolioStore.getState().activePortfolioId;
      if (portfolioId === "overview") return;
      const slot = get().portfolioAnalyses[portfolioId]?.[mode];
      if (!slot?.result?.summary.can_execute) return;
      writeSlot(portfolioId, mode, { status: "executing", error: null });
      try {
        await api.execute(portfolioId, mode, selectedTickers);
        writeSlot(portfolioId, mode, {
          status: "executed",
          result: null,
          analyzedAt: null,
        });
      } catch (e) {
        writeSlot(portfolioId, mode, {
          status: "error",
          error: e instanceof Error ? e.message : "Execution failed",
        });
      }
    },

    setPortfolioAnalysis: writeSlot,

    clearPortfolioAnalysis: (pid) => {
      set((s) => {
        const { [pid]: _, ...rest } = s.portfolioAnalyses;
        void _;
        return { portfolioAnalyses: rest };
      });
      syncActive();
    },

    clearAllAnalyses: () => {
      set({ portfolioAnalyses: {} });
      syncActive();
    },

    clear: () => {
      set({ portfolioAnalyses: {} });
      syncActive();
    },
  };
});

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

// ── Brief Store — controls Intelligence Brief open state globally ──────────

interface BriefStore {
  briefOpen: boolean;
  briefInitialTab: string;
  briefInitialTradeId: string | null;
  openBrief: (tab?: string, tradeId?: string | null) => void;
  closeBrief: () => void;
}

export const useBriefStore = create<BriefStore>((set) => ({
  briefOpen: false,
  briefInitialTab: "performance",
  briefInitialTradeId: null,
  openBrief: (tab = "performance", tradeId = null) =>
    set({ briefOpen: true, briefInitialTab: tab, briefInitialTradeId: tradeId }),
  closeBrief: () =>
    set({ briefOpen: false, briefInitialTradeId: null }),
}));
