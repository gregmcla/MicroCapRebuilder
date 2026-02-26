/** Portfolio switcher dropdown — placed in TopBar. */

import { useState, useRef, useEffect } from "react";
import { usePortfolioStore } from "../lib/store";
import { usePortfolios } from "../hooks/usePortfolios";
import CreatePortfolioModal from "./CreatePortfolioModal";


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
        <span>{label}</span>
        <span className="text-text-muted text-[10px]">{open ? "\u25B2" : "\u25BC"}</span>
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 w-56 bg-bg-elevated border border-border rounded-lg shadow-xl z-50 overflow-hidden">
          {/* Overview option */}
          <button
            onClick={() => { setPortfolio("overview"); setOpen(false); }}
            className={`w-full text-left px-3 py-2 text-xs hover:bg-bg-surface transition-colors flex items-center gap-2 ${
              activeId === "overview" ? "text-accent" : "text-text-primary"
            }`}
          >
            <span className="font-semibold">Overview</span>
            <span className="text-text-muted ml-auto text-[10px]">All portfolios</span>
          </button>

          <div className="border-t border-border" />

          {/* Portfolio list */}
          {data?.portfolios.map((p) => (
            <button
              key={p.id}
              onClick={() => { setPortfolio(p.id); setOpen(false); }}
              className={`w-full text-left px-3 py-2 text-xs hover:bg-bg-surface transition-colors flex items-center gap-2 ${
                activeId === p.id ? "text-accent" : "text-text-primary"
              }`}
            >
              <span className="font-semibold">{p.name}</span>
              <span className="ml-auto text-[10px] text-text-muted">
                {p.universe}
              </span>
            </button>
          ))}

          <div className="border-t border-border" />

          {/* Create new */}
          <button
            onClick={() => { setOpen(false); setShowCreate(true); }}
            className="w-full text-left px-3 py-2 text-xs hover:bg-bg-surface transition-colors flex items-center gap-2 text-text-muted hover:text-text-secondary"
          >
            <span>+ New Portfolio</span>
          </button>
        </div>
      )}

      {showCreate && <CreatePortfolioModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}
