/** Portfolio switcher dropdown — placed in TopBar. */

import { useState, useRef, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usePortfolioStore } from "../lib/store";
import { usePortfolios } from "../hooks/usePortfolios";
import { api } from "../lib/api";
import CreatePortfolioModal from "./CreatePortfolioModal";


export default function PortfolioSwitcher() {
  const [open, setOpen] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const renameInputRef = useRef<HTMLInputElement>(null);
  const ref = useRef<HTMLDivElement>(null);
  const activeId = usePortfolioStore((s) => s.activePortfolioId);
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio);
  const { data } = usePortfolios();
  const queryClient = useQueryClient();

  const renameMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => api.renamePortfolio(id, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      setRenamingId(null);
    },
  });

  function startRename(e: React.MouseEvent, id: string, currentName: string) {
    e.stopPropagation();
    setRenamingId(id);
    setRenameValue(currentName);
    setTimeout(() => renameInputRef.current?.select(), 0);
  }

  function commitRename(id: string) {
    const trimmed = renameValue.trim();
    if (trimmed && trimmed !== data?.portfolios.find(p => p.id === id)?.name) {
      renameMutation.mutate({ id, name: trimmed });
    } else {
      setRenamingId(null);
    }
  }

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
            <div
              key={p.id}
              className="flex items-center px-3 py-2 text-xs transition-colors hover:opacity-90 group"
              style={{ color: activeId === p.id ? "var(--accent)" : "var(--text-3)" }}
            >
              {renamingId === p.id ? (
                <input
                  ref={renameInputRef}
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                  onBlur={() => commitRename(p.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") commitRename(p.id);
                    if (e.key === "Escape") setRenamingId(null);
                  }}
                  onClick={(e) => e.stopPropagation()}
                  style={{
                    flex: 1,
                    background: "var(--void)",
                    border: "1px solid var(--accent-border)",
                    borderRadius: "4px",
                    color: "var(--text-3)",
                    fontSize: "12px",
                    fontWeight: 600,
                    padding: "2px 6px",
                    outline: "none",
                  }}
                  autoFocus
                />
              ) : (
                <button
                  className="flex-1 text-left font-semibold truncate"
                  style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", padding: 0 }}
                  onClick={() => { setPortfolio(p.id); setOpen(false); setRenamingId(null); }}
                >
                  {p.name}
                </button>
              )}
              <span style={{ fontSize: "10px", color: "var(--text-1)", marginLeft: "8px", flexShrink: 0 }}>
                {renamingId !== p.id && p.universe}
              </span>
              {renamingId !== p.id && (
                <button
                  onClick={(e) => startRename(e, p.id, p.name)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity ml-2 flex-shrink-0"
                  style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-1)", fontSize: "11px", padding: "0 2px", lineHeight: 1 }}
                  title="Rename"
                >
                  ✎
                </button>
              )}
            </div>
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
