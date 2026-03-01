/** Bottom right — Mommy co-pilot with avatar, insight rotation, quick chips, chat. */

import { useState, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useUIStore, usePortfolioStore } from "../lib/store";
import type { MommyInsight } from "../lib/types";
import MommyAvatar from "./MommyAvatar";

const QUICK_CHIPS = [
  { label: "Actions", tab: "actions" as const, icon: "⚡" },
  { label: "Risk", tab: "risk" as const, icon: "🛡️" },
  { label: "Health", tab: "performance" as const, icon: "❤️" },
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

  const handleChipClick = (tab: "actions" | "risk" | "performance") => {
    setRightTab(tab);
  };

  const displayText =
    chatResponse ?? insight?.insight ?? "Mommy's here. Ask me anything, baby.";

  const isChat = !!chatResponse;

  const categoryBorder: Record<string, string> = {
    alert: "border-[var(--red)]/30",
    warning: "border-[var(--amber)]/30",
    performance: "border-[var(--green)]/30",
    idle: "border-[var(--accent)]/30",
  };
  const borderColor = isChat
    ? "border-[var(--accent)]/30"
    : categoryBorder[insight?.category ?? "idle"] ?? "border-[var(--accent)]/30";

  return (
    <div className="flex flex-col h-full" style={{ background: "var(--surface-0)" }}>
      <div
        className="flex items-center justify-between px-3 py-2 shrink-0"
        style={{ borderBottom: "1px solid var(--border-0)" }}
      >
        <h2
          className="uppercase tracking-wider"
          style={{ fontFamily: "var(--font-mono)", fontSize: "10px", color: "var(--text-1)" }}
        >
          Mommy
        </h2>
        {insight && insight.warnings_count > 0 && (
          <span
            className="px-1.5 py-0.5 rounded font-medium"
            style={{
              fontSize: "10px",
              background: "rgba(251,191,36,0.12)",
              color: "var(--amber)",
            }}
          >
            {insight.warnings_count} warning{insight.warnings_count > 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Insight area */}
      <div className="flex-1 flex items-start gap-3 p-3 overflow-y-auto">
        <MommyAvatar size={48} />
        <div className="flex-1 min-w-0">
          <div
            className={`rounded-lg p-3 mb-2 ${borderColor}`}
            style={{
              border: "1px solid",
              background: "rgba(20,20,22,0.5)",
            }}
          >
            <p
              className="italic leading-relaxed"
              style={{ fontSize: "11.5px", color: "var(--text-1)", fontFamily: "var(--font-sans)" }}
            >
              {chatMutation.isPending ? (
                <span className="animate-pulse" style={{ color: "var(--text-0)" }}>
                  Mommy's thinking...
                </span>
              ) : (
                displayText
              )}
            </p>
            {isChat && (
              <button
                onClick={clearChatResponse}
                className="mt-1.5 transition-colors hover:opacity-80"
                style={{ fontSize: "10px", color: "var(--text-0)" }}
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
                className="flex items-center gap-1 px-2 py-1 rounded-full transition-colors hover:border-[var(--accent)] hover:text-[var(--accent)]"
                style={{
                  fontSize: "11px",
                  fontWeight: 500,
                  color: "var(--text-1)",
                  background: "transparent",
                  border: "1px solid var(--border-1)",
                }}
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
        className="flex items-center gap-2 px-3 py-2 shrink-0"
        style={{ borderTop: "1px solid var(--border-0)" }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask Mommy..."
          className="flex-1 rounded px-3 py-1.5 text-sm transition-colors focus:outline-none"
          style={{
            background: "var(--surface-2)",
            border: "1px solid var(--border-1)",
            color: "var(--text-2)",
          }}
          onFocus={(e) => (e.currentTarget.style.borderColor = "var(--accent)")}
          onBlur={(e) => (e.currentTarget.style.borderColor = "var(--border-1)")}
        />
        <button
          type="submit"
          disabled={chatMutation.isPending || !input.trim()}
          className="px-3 py-1.5 rounded transition-colors disabled:opacity-40"
          style={{
            fontSize: "12px",
            fontWeight: 500,
            background: "rgba(124,92,252,0.12)",
            color: "var(--accent)",
          }}
        >
          Ask
        </button>
      </form>
    </div>
  );
}

/** Collapsed 40px strip — always visible at bottom of right column. */
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
    <div
      className="flex items-center gap-2 px-3 shrink-0"
      style={{
        height: "40px",
        background: "var(--surface-0)",
        borderTop: "1px solid var(--border-0)",
      }}
    >
      {/* Live pulse dot */}
      <div
        className="animate-live-pulse shrink-0"
        style={{
          width: "6px",
          height: "6px",
          borderRadius: "50%",
          background: "var(--green)",
        }}
      />
      <span
        className="uppercase tracking-wider shrink-0"
        style={{ fontFamily: "var(--font-mono)", fontSize: "10px", color: "var(--text-1)" }}
      >
        MOMMY
      </span>
      <span style={{ fontSize: "10px", color: "var(--text-1)" }} className="shrink-0">
        —
      </span>
      <span
        className="flex-1 italic truncate min-w-0"
        style={{ fontSize: "11.5px", color: "var(--text-1)", fontFamily: "var(--font-sans)" }}
      >
        {text}
      </span>
      <button
        onClick={toggleMommy}
        className="shrink-0 px-1 transition-colors hover:opacity-80"
        style={{ fontSize: "10px", color: "var(--text-1)" }}
        title={mommyExpanded ? "Collapse chat" : "Expand chat"}
      >
        {mommyExpanded ? "↓" : "↑"}
      </button>
    </div>
  );
}
