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
        className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold transition-colors"
        style={{
          background: "var(--surface-2)",
          color: "var(--text-3)",
          border: "1px solid var(--border-1)",
        }}
      >
        <span>{label}</span>
        <span style={{ color: "var(--text-1)", fontSize: "10px" }}>{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div
          className="absolute top-full left-0 mt-1 w-56 rounded-lg shadow-xl z-50 overflow-hidden"
          style={{
            background: "var(--surface-2)",
            border: "1px solid var(--border-1)",
          }}
        >
          {/* Overview option */}
          <button
            onClick={() => { setPortfolio("overview"); setOpen(false); }}
            className="w-full text-left px-3 py-2 text-xs transition-colors flex items-center gap-2 hover:opacity-80"
            style={{
              color: activeId === "overview" ? "var(--accent)" : "var(--text-3)",
            }}
          >
            <span className="font-semibold">Overview</span>
            <span className="ml-auto" style={{ fontSize: "10px", color: "var(--text-1)" }}>
              All portfolios
            </span>
          </button>

          <div style={{ borderTop: "1px solid var(--border-1)" }} />

          {/* Portfolio list */}
          {data?.portfolios.map((p) => (
            <button
              key={p.id}
              onClick={() => { setPortfolio(p.id); setOpen(false); }}
              className="w-full text-left px-3 py-2 text-xs transition-colors flex items-center gap-2 hover:opacity-80"
              style={{
                color: activeId === p.id ? "var(--accent)" : "var(--text-3)",
              }}
            >
              <span className="font-semibold">{p.name}</span>
              <span className="ml-auto" style={{ fontSize: "10px", color: "var(--text-1)" }}>
                {p.universe}
              </span>
            </button>
          ))}

          <div style={{ borderTop: "1px solid var(--border-1)" }} />

          {/* Create new */}
          <button
            onClick={() => { setOpen(false); setShowCreate(true); }}
            className="w-full text-left px-3 py-2 text-xs flex items-center gap-2 transition-opacity hover:opacity-70"
            style={{ color: "var(--text-1)" }}
          >
            <span>+ New Portfolio</span>
          </button>
        </div>
      )}

      {showCreate && <CreatePortfolioModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}
