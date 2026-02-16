/** Modal for creating a new portfolio with universe selection. */

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { usePortfolioStore } from "../lib/store";

const UNIVERSES = [
  { id: "microcap", label: "Micro Cap", desc: "<$300M — High volatility, aggressive momentum" },
  { id: "smallcap", label: "Small Cap", desc: "$300M–$2B — Moderate volatility, balanced factors" },
  { id: "midcap", label: "Mid Cap", desc: "$2B–$10B — Lower volatility, mean-reversion bias" },
  { id: "largecap", label: "Large Cap", desc: "$10B+ — Stable, relative-strength focused" },
  { id: "custom", label: "Custom", desc: "User-defined — start from microcap defaults" },
];

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export default function CreatePortfolioModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const [id, setId] = useState("");
  const [idManual, setIdManual] = useState(false);
  const [universe, setUniverse] = useState("microcap");
  const [capital, setCapital] = useState("50000");
  const [error, setError] = useState<string | null>(null);

  const queryClient = useQueryClient();
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio);

  const mutation = useMutation({
    mutationFn: api.createPortfolio,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      setPortfolio(data.portfolio.id);
      onClose();
    },
    onError: (e: Error) => setError(e.message),
  });

  function handleNameChange(val: string) {
    setName(val);
    if (!idManual) setId(slugify(val));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const capitalNum = parseFloat(capital);
    if (!name.trim()) { setError("Name is required"); return; }
    if (!id.trim()) { setError("ID is required"); return; }
    if (isNaN(capitalNum) || capitalNum <= 0) { setError("Capital must be a positive number"); return; }
    mutation.mutate({ id, name: name.trim(), universe, starting_capital: capitalNum });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-bg-elevated border border-border rounded-xl w-full max-w-md shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-sm font-bold text-text-primary">Create Portfolio</h2>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary text-lg leading-none">&times;</button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {/* Name */}
          <div>
            <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => handleNameChange(e.target.value)}
              placeholder="My Large Cap Portfolio"
              className="w-full bg-bg-surface border border-border rounded px-3 py-2 text-sm text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent"
              autoFocus
            />
          </div>

          {/* ID */}
          <div>
            <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">
              ID <span className="text-text-muted/50">(slug)</span>
            </label>
            <input
              type="text"
              value={id}
              onChange={(e) => { setId(e.target.value); setIdManual(true); }}
              placeholder="my-large-cap-portfolio"
              className="w-full bg-bg-surface border border-border rounded px-3 py-2 text-sm text-text-primary font-mono placeholder:text-text-muted/50 focus:outline-none focus:border-accent"
            />
          </div>

          {/* Universe */}
          <div>
            <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1.5">Universe</label>
            <div className="space-y-1.5">
              {UNIVERSES.map((u) => (
                <button
                  type="button"
                  key={u.id}
                  onClick={() => setUniverse(u.id)}
                  className={`w-full text-left px-3 py-2 rounded border text-xs transition-colors ${
                    universe === u.id
                      ? "border-accent bg-accent/10 text-accent"
                      : "border-border bg-bg-surface text-text-primary hover:border-text-muted"
                  }`}
                >
                  <span className="font-semibold">{u.label}</span>
                  <span className="text-text-muted ml-2">{u.desc}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Starting Capital */}
          <div>
            <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">Starting Capital</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted text-sm">$</span>
              <input
                type="text"
                value={capital}
                onChange={(e) => setCapital(e.target.value.replace(/[^0-9.]/g, ""))}
                className="w-full bg-bg-surface border border-border rounded pl-7 pr-3 py-2 text-sm text-text-primary font-mono focus:outline-none focus:border-accent"
              />
            </div>
          </div>

          {/* Error */}
          {error && (
            <p className="text-xs text-red-400 bg-red-500/10 rounded px-3 py-2">{error}</p>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs text-text-muted hover:text-text-primary transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="px-4 py-2 text-xs font-semibold bg-accent text-bg-primary rounded hover:bg-accent/80 transition-colors disabled:opacity-50"
            >
              {mutation.isPending ? "Creating..." : "Create Portfolio"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
