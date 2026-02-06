/** Bottom right — Mommy co-pilot with insight + chat. */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { MommyInsight } from "../lib/types";

function MommyAvatar() {
  return (
    <div className="relative w-10 h-10 shrink-0">
      {/* Glow */}
      <div className="absolute inset-0 rounded-full bg-accent/20 animate-pulse" />
      {/* Avatar circle */}
      <div className="relative w-10 h-10 rounded-full bg-bg-elevated border border-accent/40 flex items-center justify-center">
        <span className="text-accent text-lg font-bold">M</span>
      </div>
    </div>
  );
}

export default function MommyCoPilot() {
  const [input, setInput] = useState("");
  const [chatResponse, setChatResponse] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: insight } = useQuery<MommyInsight>({
    queryKey: ["mommyInsight"],
    queryFn: api.getMommyInsight,
    refetchInterval: 60_000,
  });

  const chatMutation = useMutation({
    mutationFn: (message: string) => api.chat(message),
    onSuccess: (data) => {
      setChatResponse(typeof data === "string" ? data : data.response);
      queryClient.invalidateQueries({ queryKey: ["mommyInsight"] });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    chatMutation.mutate(input.trim());
    setInput("");
  };

  const displayText =
    chatResponse ?? insight?.insight ?? "Mommy's here. Ask me anything, baby.";

  const categoryColor: Record<string, string> = {
    alert: "border-loss/40",
    warning: "border-warning/40",
    performance: "border-profit/40",
    idle: "border-accent/40",
  };
  const borderColor = chatResponse
    ? "border-accent/40"
    : categoryColor[insight?.category ?? "idle"] ?? "border-accent/40";

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-border">
        <h2 className="text-xs font-semibold text-text-secondary tracking-wider uppercase">
          Mommy
        </h2>
      </div>

      {/* Insight area */}
      <div className="flex-1 flex items-start gap-3 p-3 overflow-y-auto">
        <MommyAvatar />
        <div
          className={`flex-1 rounded-lg border ${borderColor} bg-bg-elevated/50 p-3`}
        >
          <p className="text-sm italic text-text-primary leading-relaxed">
            {chatMutation.isPending ? (
              <span className="animate-pulse text-text-muted">
                Mommy's thinking...
              </span>
            ) : (
              displayText
            )}
          </p>
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
