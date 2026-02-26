/** Bottom right — Mommy co-pilot with avatar, insight rotation, quick chips, chat. */

import { useState, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useUIStore, usePortfolioStore } from "../lib/store";
import type { MommyInsight } from "../lib/types";
import MommyAvatar from "./MommyAvatar";

const QUICK_CHIPS = [
  { label: "Summary", tab: "summary" as const, icon: "\u26A1" },
  { label: "Risk", tab: "risk" as const, icon: "\u{1F6E1}\uFE0F" },
  { label: "Health", tab: "performance" as const, icon: "\u2764\uFE0F" },
] as const;

export default function MommyCoPilot() {
  const [input, setInput] = useState("");
  const [chatResponse, setChatResponse] = useState<string | null>(null);
  const [chatFadeTimer, setChatFadeTimer] = useState<ReturnType<typeof setTimeout> | null>(null);
  const queryClient = useQueryClient();
  const setRightTab = useUIStore((s) => s.setRightTab);
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);

  const { data: insight } = useQuery<MommyInsight>({
    queryKey: ["mommyInsight", portfolioId],
    queryFn: () => api.getMommyInsight(portfolioId),
    refetchInterval: 60_000,
    enabled: portfolioId !== "overview",
  });

  const chatMutation = useMutation({
    mutationFn: (message: string) => api.chat(portfolioId, message),
    onSuccess: (data) => {
      setChatResponse(data.message);
      queryClient.invalidateQueries({ queryKey: ["mommyInsight"] });
    },
  });

  // Auto-dismiss chat response after 30s, fall back to insight rotation
  const clearChatResponse = useCallback(() => {
    setChatResponse(null);
  }, []);

  useEffect(() => {
    if (chatResponse) {
      const timer = setTimeout(clearChatResponse, 30_000);
      setChatFadeTimer(timer);
      return () => clearTimeout(timer);
    }
  }, [chatResponse, clearChatResponse]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    if (chatFadeTimer) clearTimeout(chatFadeTimer);
    chatMutation.mutate(input.trim());
    setInput("");
  };

  const handleChipClick = (tab: "summary" | "risk" | "performance") => {
    setRightTab(tab);
  };

  const displayText =
    chatResponse ?? insight?.insight ?? "Mommy's here. Ask me anything, baby.";

  const isChat = !!chatResponse;

  const categoryColor: Record<string, string> = {
    alert: "border-loss/40",
    warning: "border-warning/40",
    performance: "border-profit/40",
    idle: "border-accent/40",
  };
  const borderColor = isChat
    ? "border-accent/40"
    : categoryColor[insight?.category ?? "idle"] ?? "border-accent/40";

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <h2 className="text-xs font-semibold text-text-secondary tracking-wider uppercase">
          Mommy
        </h2>
        {insight && insight.warnings_count > 0 && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-warning/15 text-warning font-medium">
            {insight.warnings_count} warning{insight.warnings_count > 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Insight area */}
      <div className="flex-1 flex items-start gap-3 p-3 overflow-y-auto">
        <MommyAvatar size={48} />
        <div className="flex-1 min-w-0">
          <div className={`rounded-lg border ${borderColor} bg-bg-elevated/50 p-3 mb-2`}>
            <p className="text-sm italic text-text-primary leading-relaxed">
              {chatMutation.isPending ? (
                <span className="animate-pulse text-text-muted">
                  Mommy's thinking...
                </span>
              ) : (
                displayText
              )}
            </p>
            {isChat && (
              <button
                onClick={clearChatResponse}
                className="text-[10px] text-text-muted hover:text-text-secondary mt-1.5 transition-colors"
              >
                dismiss
              </button>
            )}
          </div>

          {/* Quick chips */}
          <div className="flex items-center gap-1.5">
            {QUICK_CHIPS.map((chip) => (
              <button
                key={chip.label}
                onClick={() => handleChipClick(chip.tab)}
                className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-text-muted bg-bg-primary border border-border rounded-full hover:border-accent hover:text-accent transition-colors"
              >
                <span>{chip.icon}</span>
                {chip.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Chat input */}
      <form
        onSubmit={handleSubmit}
        className="flex items-center gap-2 px-3 py-2 border-t border-border"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask Mommy..."
          className="flex-1 bg-bg-primary text-sm text-text-primary placeholder-text-muted border border-border rounded px-3 py-1.5 focus:outline-none focus:border-accent transition-colors"
        />
        <button
          type="submit"
          disabled={chatMutation.isPending || !input.trim()}
          className="px-3 py-1.5 text-xs font-medium bg-accent/15 text-accent rounded hover:bg-accent/25 disabled:opacity-40 transition-colors"
        >
          Ask
        </button>
      </form>
    </div>
  );
}

/** Collapsed 36px strip — always visible at bottom of right column. */
export function MommyStrip() {
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const toggleMommy = useUIStore((s) => s.toggleMommy);
  const mommyExpanded = useUIStore((s) => s.mommyExpanded);

  const { data: insight } = useQuery<MommyInsight>({
    queryKey: ["mommyInsight", portfolioId],
    queryFn: () => api.getMommyInsight(portfolioId),
    refetchInterval: 60_000,
    enabled: portfolioId !== "overview",
  });

  const text = insight?.insight ?? "Mommy's watching the market...";

  return (
    <div className="h-9 flex items-center gap-2 px-3 border-t border-border bg-bg-surface shrink-0">
      <div className="w-1.5 h-1.5 rounded-full bg-accent shrink-0" />
      <span className="text-[10px] text-text-muted uppercase tracking-wider shrink-0">MOMMY</span>
      <span className="text-[10px] text-text-muted shrink-0">—</span>
      <span className="flex-1 text-[11px] text-text-secondary italic truncate min-w-0">
        {text}
      </span>
      <button
        onClick={toggleMommy}
        className="shrink-0 text-[10px] text-text-muted hover:text-text-secondary transition-colors px-1"
        title={mommyExpanded ? "Collapse chat" : "Expand chat"}
      >
        {mommyExpanded ? "↓" : "↑"}
      </button>
    </div>
  );
}
