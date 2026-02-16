/** Portfolio switcher dropdown — placed in TopBar. */

import { useState, useRef, useEffect } from "react";
import { usePortfolioStore } from "../lib/store";
import { usePortfolios } from "../hooks/usePortfolios";
import CreatePortfolioModal from "./CreatePortfolioModal";

const UNIVERSE_COLORS: Record<string, string> = {
  microcap: "bg-purple-500/20 text-purple-400",
  smallcap: "bg-blue-500/20 text-blue-400",
  midcap: "bg-teal-500/20 text-teal-400",
  largecap: "bg-green-500/20 text-green-400",
  custom: "bg-gray-500/20 text-gray-400",
};

export default function PortfolioSwitcher() {
  const [open, setOpen] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const activeId = usePortfolioStore((s) => s.activePortfolioId);
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio);
  const { data } = usePortfolios();

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const activePortfolio = data?.portfolios.find((p) => p.id === activeId);
  const label = activeId === "overview" ? "Overview" : activePortfolio?.name ?? activeId;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold bg-bg-elevated text-text-primary rounded hover:bg-border transition-colors"
      >
        <span className="text-accent">{activeId === "overview" ? "\u{1F4CA}" : "\u{1F4BC}"}</span>
        <span>{label}</span>
        <span className="text-text-muted text-[10px]">{open ? "\u25B2" : "\u25BC"}</span>
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 w-56 bg-bg-elevated border border-border rounded-lg shadow-xl z-50 overflow-hidden">
          {/* Overview option */}
          <button
            onClick={() => { setPortfolio("overview"); setOpen(false); }}
            className={`w-full text-left px-3 py-2 text-xs hover:bg-bg-surface transition-colors flex items-center gap-2 ${
              activeId === "overview" ? "bg-accent/10 text-accent" : "text-text-primary"
            }`}
          >
            <span>{"\u{1F4CA}"}</span>
            <span className="font-semibold">Overview</span>
            <span className="text-text-muted ml-auto">All portfolios</span>
          </button>

          <div className="border-t border-border" />

          {/* Portfolio list */}
          {data?.portfolios.map((p) => (
            <button
              key={p.id}
              onClick={() => { setPortfolio(p.id); setOpen(false); }}
              className={`w-full text-left px-3 py-2 text-xs hover:bg-bg-surface transition-colors flex items-center gap-2 ${
                activeId === p.id ? "bg-accent/10 text-accent" : "text-text-primary"
              }`}
            >
              <span>{"\u{1F4BC}"}</span>
              <span className="font-semibold">{p.name}</span>
              <span className={`ml-auto text-[10px] px-1.5 py-0.5 rounded ${UNIVERSE_COLORS[p.universe] ?? UNIVERSE_COLORS.custom}`}>
                {p.universe}
              </span>
            </button>
          ))}

          <div className="border-t border-border" />

          {/* Create new */}
          <button
            onClick={() => { setOpen(false); setShowCreate(true); }}
            className="w-full text-left px-3 py-2 text-xs hover:bg-bg-surface transition-colors flex items-center gap-2 text-accent"
          >
            <span>+</span>
            <span className="font-semibold">New Portfolio</span>
          </button>
        </div>
      )}

      {showCreate && <CreatePortfolioModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}
