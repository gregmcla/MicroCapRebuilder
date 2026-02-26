/** Global keyboard shortcuts: A=analyze, E=execute, R=refresh, 1/2/3=tabs. */

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAnalysisStore, useUIStore, usePortfolioStore } from "../lib/store";

export function useKeyboardShortcuts() {
  const queryClient = useQueryClient();
  const runAnalysis = useAnalysisStore((s) => s.runAnalysis);
  const runExecute = useAnalysisStore((s) => s.runExecute);
  const isAnalyzing = useAnalysisStore((s) => s.isAnalyzing);
  const isExecuting = useAnalysisStore((s) => s.isExecuting);
  const result = useAnalysisStore((s) => s.result);
  const setRightTab = useUIStore((s) => s.setRightTab);
  const toggleActivity = useUIStore((s) => s.toggleActivity);
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Skip if typing in an input/textarea
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      // Shortcuts disabled on overview page
      if (portfolioId === "overview") return;

      switch (e.key.toLowerCase()) {
        case "a":
          if (!isAnalyzing) runAnalysis();
          break;
        case "e":
          if (!isExecuting && result?.summary.can_execute) runExecute();
          break;
        case "r":
          queryClient.invalidateQueries({ queryKey: ["portfolioState", portfolioId] });
          break;
        case "1":
          setRightTab("actions");
          break;
        case "2":
          setRightTab("risk");
          break;
        case "3":
          setRightTab("performance");
          break;
        case "f":
          toggleActivity();
          break;
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isAnalyzing, isExecuting, result, runAnalysis, runExecute, queryClient, setRightTab, toggleActivity, portfolioId]);
}
