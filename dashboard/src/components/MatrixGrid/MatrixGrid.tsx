import { useState, useMemo, useEffect, useRef, useCallback } from "react";
import type { MatrixGridProps, MatrixPosition, Transaction, WatchlistCandidate, ScanJobStatus } from "./types";
import { pc, pbg, fv, MATRIX_FONT } from "./constants";
import Sparkline from "./Sparkline";
import Waveform from "./Waveform";
import Reticle from "./Reticle";
import DetailCard from "./DetailCard";
import BottomPanel from "./BottomPanel";
import BackgroundCanvas from "./BackgroundCanvas";
import PositionPulse from "./PositionPulse";
import ActionsTab from "../ActionsTab";
import { useAnalysisStore } from "../../lib/store";
import { parseTradeRationale, tradeExplanation } from "../../lib/tradeUtils";
import type { Snapshot } from "../../lib/types";
import { useWarnings } from "../../hooks/useRisk";

// ─── Squarified Treemap ───────────────────────────────────────────────────────
function squarifyLayout(
  values: number[],
  x: number, y: number, w: number, h: number,
  gap: number
): Array<{ x: number; y: number; w: number; h: number }> {
  const n = values.length;
  if (n === 0 || w <= 0 || h <= 0) return [];
  const total = values.reduce((a, b) => a + b, 0);
  if (total === 0) return values.map(() => ({ x, y, w: 0, h: 0 }));

  const area = w * h;
  const normed = values.map(v => (v / total) * area);

  const worstAspect = (row: number[], s: number): number => {
    const sum = row.reduce((a, b) => a + b, 0);
    const rmax = Math.max(...row), rmin = Math.min(...row);
    if (sum === 0 || rmin === 0) return Infinity;
    return Math.max((s * s * rmax) / (sum * sum), (sum * sum) / (s * s * rmin));
  };

  const result: Array<{ x: number; y: number; w: number; h: number }> =
    new Array(n).fill(null).map(() => ({ x: 0, y: 0, w: 0, h: 0 }));
  let start = 0, cx = x, cy = y, cw = w, ch = h;

  while (start < n && cw > 0.5 && ch > 0.5) {
    const s = Math.min(cw, ch);
    const horizontal = cw >= ch;

    let end = start + 1;
    while (end < n) {
      const curr = normed.slice(start, end);
      const next = normed.slice(start, end + 1);
      if (worstAspect(next, s) <= worstAspect(curr, s)) end++;
      else break;
    }

    const row = normed.slice(start, end);
    const rowSum = row.reduce((a, b) => a + b, 0);

    if (horizontal) {
      const rowW = rowSum / ch;
      let off = cy;
      for (let i = 0; i < row.length; i++) {
        const rh = (row[i] / rowSum) * ch;
        result[start + i] = {
          x: cx + gap / 2, y: off + gap / 2,
          w: Math.max(0, rowW - gap), h: Math.max(0, rh - gap),
        };
        off += rh;
      }
      cx += rowW; cw -= rowW;
    } else {
      const rowH = rowSum / cw;
      let off = cx;
      for (let i = 0; i < row.length; i++) {
        const rw = (row[i] / rowSum) * cw;
        result[start + i] = {
          x: off + gap / 2, y: cy + gap / 2,
          w: Math.max(0, rw - gap), h: Math.max(0, rowH - gap),
        };
        off += rw;
      }
      cy += rowH; ch -= rowH;
    }

    start = end;
  }
  return result;
}

const BOOT_LINES = [
  "[SYS] MATRIX v3.0 initializing...",
  "[MEM] Allocating position buffers",
  "[NET] Connecting to market feed — OK",
  "[GPU] Particle system online",
  "[EKG] Vitals monitoring active",
  "[SCN] Threat scanner armed",
  "█████████████████████████ 100%",
  "[RDY] ALL SYSTEMS NOMINAL",
];

export default function MatrixGrid({
  positions,
  portfolios,
  onPositionClick,
  onBack,
  initialFilter,
  showEKG = true,
  showTickerTape = true,
  transactions = [],
  watchlistCandidates = [],
  scanStatus,
  showSecondaryTabs = true,
  filterOverride,
  positionRationales = {},
  snapshots = [],
  startingCapital,
}: MatrixGridProps) {
  const [viewTab, setViewTab] = useState<"grid" | "actions" | "watchlist" | "activity" | "logs" | "history">("grid");
  const analysisResult = useAnalysisStore((s) => s.result);
  const isAnalyzing = useAnalysisStore((s) => s.isAnalyzing);
  const { data: warnings } = useWarnings();

  // Build a map of pending sell reasoning from analysis result (ticker → ai_reasoning)
  const pendingSellReasoningMap = useMemo(() => {
    if (!analysisResult) return {} as Record<string, string>;
    const map: Record<string, string> = {};
    [...analysisResult.approved, ...analysisResult.modified].forEach(a => {
      if (a.original.action_type === "SELL" && a.ai_reasoning) {
        map[a.original.ticker] = a.ai_reasoning;
      }
    });
    return map;
  }, [analysisResult]);

  // Auto-switch to ACTIONS tab only when analysis transitions from running → done
  const wasAnalyzing = useRef(false);
  useEffect(() => {
    if (wasAnalyzing.current && !isAnalyzing && analysisResult) setViewTab("actions");
    wasAnalyzing.current = isAnalyzing;
  }, [analysisResult, isAnalyzing]);
  const [hovIdx, setHovIdx] = useState<number | null>(null);
  const [sortBy, setSortBy] = useState<"entry" | "value" | "perf" | "day" | "alpha" | "portfolio">("perf");
  const [filterP, setFilterP] = useState<string | null>(initialFilter ?? null);
  const [mounted, setMounted] = useState(false);
  const [boot, setBoot] = useState(0);
  const [clock, setClock] = useState("");
  const [selectedPos, setSelectedPos] = useState<MatrixPosition | null>(null);
  const [bootLines, setBootLines] = useState<string[]>([]);
  const mouseXRef = useRef(-1000);
  const mouseYRef = useRef(-1000);
  const gridRef = useRef<HTMLDivElement>(null);
  const treemapRef = useRef<HTMLDivElement>(null);
  const [containerSize, setContainerSize] = useState({ w: 0, h: 0 });

  // Boot sequence
  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = [];
    BOOT_LINES.forEach((line, i) => {
      timers.push(setTimeout(() => setBootLines((prev) => [...prev, line]), i * 120));
    });
    timers.push(setTimeout(() => setBoot(1), 300));
    timers.push(setTimeout(() => setBoot(2), 700));
    timers.push(setTimeout(() => { setBoot(3); setMounted(true); }, 1100));
    return () => timers.forEach(clearTimeout);
  }, []);

  // Clock — seconds only; millisecond precision was high-frequency noise
  useEffect(() => {
    const tick = () => setClock(new Date().toLocaleTimeString("en-US", { hour12: false }));
    tick();
    const i = setInterval(tick, 1000);
    return () => clearInterval(i);
  }, []);

  // Treemap container size
  useEffect(() => {
    const el = treemapRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const e = entries[0];
      if (e) setContainerSize({ w: e.contentRect.width, h: e.contentRect.height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "1") setSortBy("entry");
      if (e.key === "2") setSortBy("value");
      if (e.key === "3") setSortBy("perf");
      if (e.key === "4") setSortBy("day");
      if (e.key === "5") setSortBy("alpha");
      if (e.key === "6") setSortBy("portfolio");
      if (e.key === "Escape") { setSelectedPos(null); setFilterP(null); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // 3D parallax
  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const rect = gridRef.current?.getBoundingClientRect();
    if (!rect) return;
    mouseXRef.current = e.clientX;
    mouseYRef.current = e.clientY;
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const rx = (e.clientX - cx) / rect.width * 6;
    const ry = (e.clientY - cy) / rect.height * 4;
    if (gridRef.current) {
      gridRef.current.style.transform =
        `perspective(1200px) rotateY(${rx}deg) rotateX(${-ry}deg)`;
    }
  }, []);

  const handleMouseLeave = useCallback(() => {
    mouseXRef.current = -1000;
    mouseYRef.current = -1000;
    if (gridRef.current) {
      gridRef.current.style.transform = "perspective(1200px) rotateY(0deg) rotateX(0deg)";
    }
  }, []);

  // When filterOverride is defined externally, use it; otherwise use internal filterP
  const effectiveFilter = filterOverride !== undefined ? filterOverride : filterP;

  // Sorted / filtered positions
  const sorted = useMemo(() => {
    let arr = [...positions];
    if (effectiveFilter) arr = arr.filter((p) => p.portfolioId === effectiveFilter);
    if (sortBy === "entry") arr.sort((a, b) => (b.entryDate ?? "").localeCompare(a.entryDate ?? ""));
    else if (sortBy === "value") arr.sort((a, b) => b.value - a.value);
    else if (sortBy === "perf") arr.sort((a, b) => b.perf - a.perf);
    else if (sortBy === "day") arr.sort((a, b) => b.day - a.day);
    else if (sortBy === "alpha") arr.sort((a, b) => (b.alpha ?? 0) - (a.alpha ?? 0));
    else if (sortBy === "portfolio") arr.sort((a, b) => a.portfolioId.localeCompare(b.portfolioId) || b.value - a.value);
    return arr;
  }, [positions, sortBy, effectiveFilter]);

  const maxVal = useMemo(() => Math.max(...positions.map((p) => p.value), 1), [positions]);

  // Weighted avg P&L — weighted by position value, not simple mean
  const weightedAvgP = useMemo(() => {
    if (positions.length === 0) return "0.0";
    const totalV = positions.reduce((s, p) => s + Math.max(p.value, 0), 0);
    if (totalV === 0) return (positions.reduce((s, p) => s + p.perf, 0) / positions.length).toFixed(1);
    return (positions.reduce((s, p) => s + p.perf * (p.value / totalV), 0)).toFixed(1);
  }, [positions]);

  // Real at-risk detection: positions within 30% of stop-loss range (uses sorted indices)
  const atRiskSet = useMemo(() => {
    const s = new Set<number>();
    sorted.forEach((pos, i) => {
      if (pos.stopLoss != null && pos.takeProfit != null && pos.currentPrice != null) {
        const range = pos.takeProfit - pos.stopLoss;
        if (range > 0) {
          const progress = ((pos.currentPrice - pos.stopLoss) / range) * 100;
          if (progress < 30) s.add(i);
        }
      }
    });
    return s;
  }, [sorted]);


  const treemapRects = useMemo(() => {
    if (containerSize.w < 10 || containerSize.h < 10 || sorted.length === 0) return [];
    const bottomReserve = selectedPos && showSecondaryTabs ? 296 : 0;
    const tw = containerSize.w;
    const th = Math.max(1, containerSize.h - bottomReserve);
    // Pick sizing metric based on sort tab
    const sizeOf = (pos: typeof sorted[0]) => {
      if (sortBy === "perf") return Math.max(Math.abs(pos.perf), 0.5);
      if (sortBy === "day") return Math.max(Math.abs(pos.day), 0.5);
      if (sortBy === "alpha") return Math.max(Math.abs(pos.alpha ?? 0), 0.5);
      if (sortBy === "entry") return 1; // uniform grid
      return Math.max(pos.value, 1); // value / portfolio
    };
    // Sort by size desc for squarified quality, track original indices
    const withIdx = sorted.map((pos, i) => ({ i, v: sizeOf(pos) }));
    withIdx.sort((a, b) => b.v - a.v);
    const rects = squarifyLayout(withIdx.map(item => item.v), 0, 0, tw, th, 3);
    const result: Array<{ x: number; y: number; w: number; h: number }> =
      Array(sorted.length).fill(null).map(() => ({ x: 0, y: 0, w: 0, h: 0 }));
    withIdx.forEach((item, j) => { result[item.i] = rects[j] ?? { x: 0, y: 0, w: 0, h: 0 }; });
    return result;
  }, [sorted, sortBy, containerSize, selectedPos, showSecondaryTabs]);
  const hovered = hovIdx !== null ? sorted[hovIdx] : null;
  const totalVal = positions.reduce((s, p) => s + p.value, 0);
  const wins = positions.filter((p) => p.perf > 0).length;
  const top = positions.length > 0 ? [...positions].sort((a, b) => b.perf - a.perf)[0] : null;
  const bot = positions.length > 0 ? [...positions].sort((a, b) => a.perf - b.perf)[0] : null;
  const tickers = useMemo(() => [...new Set(positions.map((p) => p.ticker))], [positions]);
  const socialMap = useMemo(() => {
    const m = new Map<string, string>();
    watchlistCandidates.forEach(c => { if (c.social_heat) m.set(c.ticker, c.social_heat); });
    return m;
  }, [watchlistCandidates]);
  const CELL_HEAT: Record<string, string> = { SPIKING: "#f87171", HOT: "#fb923c", WARM: "#facc15" };

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        background: "#040608",
        fontFamily: MATRIX_FONT,
        color: "#ccc",
        position: "relative",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
      }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      {/* CSS animations + cell hover effects */}
      <style>{`
        @keyframes matrixTicker { 0%{transform:translateX(0)} 100%{transform:translateX(-50%)} }
        @keyframes matrixFadeIn { from{opacity:0} to{opacity:1} }
        @keyframes matrixScaleIn { from{opacity:0;transform:scale(0.95)} to{opacity:1;transform:scale(1)} }
        @keyframes matrixGlitch {
          0%{transform:translate(0);filter:none}
          25%{transform:translate(-3px,1px);filter:hue-rotate(90deg)}
          50%{transform:translate(3px,-1px);filter:hue-rotate(-90deg) saturate(2)}
          75%{transform:translate(-1px,-2px);filter:hue-rotate(45deg)}
          100%{transform:translate(0);filter:none}
        }
        @keyframes matrixSlideUp { from{transform:translateY(100%);opacity:0} to{transform:translateY(0);opacity:1} }
        @keyframes matrixAnomalyPulse {
          0%,100%{box-shadow:inset 0 0 0 1px rgba(248,113,113,0.1)}
          50%{box-shadow:inset 0 0 0 1px rgba(248,113,113,0.5),0 0 12px rgba(248,113,113,0.15)}
        }
        @keyframes matrixTermLine { from{opacity:0;transform:translateX(-4px)} to{opacity:1;transform:translateX(0)} }
        @keyframes matrixBlink { 0%,100%{opacity:1} 50%{opacity:0} }
        .matrix-cell:hover { background: linear-gradient(to bottom, #1e4a2e, #163826) !important; opacity: 1 !important; }
        .matrix-cell:hover .matrix-tk { color:#fff !important; text-shadow:0 0 10px rgba(74,222,128,0.5); }
        .matrix-cell:hover .matrix-ret { opacity:1 !important; }
        .matrix-cell:hover .matrix-chroma { opacity:1 !important; }
        .matrix-sb:hover { color:#4ade80 !important; }
        .matrix-fb:hover { border-color:rgba(74,222,128,0.2) !important; color:#888 !important; }
        ::-webkit-scrollbar{width:3px}
        ::-webkit-scrollbar-track{background:transparent}
        ::-webkit-scrollbar-thumb{background:rgba(74,222,128,0.12);border-radius:3px}
      `}</style>

      {/* Background canvas layer */}
      <BackgroundCanvas mouseX={mouseXRef} mouseY={mouseYRef} tickers={tickers} />

      {/* Scanlines overlay */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none", zIndex: 1,
        background: "repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.025) 2px,rgba(0,0,0,0.025) 4px)",
      }} />

      {/* Boot terminal overlay */}
      {boot < 3 && (
        <div style={{
          position: "absolute", inset: 0, zIndex: 100, background: "#040608",
          padding: "40px", display: "flex", flexDirection: "column", justifyContent: "center",
        }}>
          <div style={{ maxWidth: 500 }}>
            {bootLines.map((line, i) => (
              <div key={i} style={{
                fontSize: 11, fontFamily: MATRIX_FONT, marginBottom: 4,
                color: line.includes("100%") || line.includes("RDY") ? "#4ade80" : "#4ade8088",
                animation: "matrixTermLine 0.15s ease",
                letterSpacing: "0.03em",
              }}>
                {line}
              </div>
            ))}
            <span style={{
              display: "inline-block", width: 8, height: 14, background: "#4ade80",
              animation: "matrixBlink 0.8s step-end infinite", marginTop: 4,
            }} />
          </div>
        </div>
      )}

      {/* Main content */}
      <div style={{
        position: "relative", zIndex: 2, display: "flex", flexDirection: "column",
        flex: 1, overflow: "hidden",
        opacity: boot >= 3 ? 1 : 0, transition: "opacity 0.6s",
      }}>


        {/* POSITION PULSE */}
        <PositionPulse positions={positions} />

        {/* CONTROLS */}
        <div style={{ padding: "6px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", flexShrink: 0 }}>
          <div style={{ display: "flex", gap: 1, alignItems: "center" }}>
            {/* Portfolio name */}
            {(effectiveFilter ? portfolios.find(p => p.id === effectiveFilter) : portfolios.length === 1 ? portfolios[0] : null) && (
              <span style={{
                fontSize: 13, fontWeight: 700, letterSpacing: "0.08em", marginRight: 16, paddingRight: 16,
                borderRight: "1px solid rgba(255,255,255,0.04)",
                color: (effectiveFilter ? portfolios.find(p => p.id === effectiveFilter) : portfolios[0])?.color ?? "#e8ffe8",
                textShadow: `0 0 20px ${(effectiveFilter ? portfolios.find(p => p.id === effectiveFilter) : portfolios[0])?.color ?? "#4ade80"}22`,
              }}>
                {(effectiveFilter ? portfolios.find(p => p.id === effectiveFilter) : portfolios[0])?.name}
              </span>
            )}
            {/* Stats inline with sort */}
            <div style={{ display: "flex", gap: 12, alignItems: "baseline", marginRight: 16, paddingRight: 16, borderRight: "1px solid rgba(255,255,255,0.04)" }}>
              {[
                { l: "POS", v: String(sorted.length), c: "#e8ffe8" },
                { l: "INVESTED", v: `$${totalVal.toLocaleString()}`, c: "#e8ffe8" },
                { l: "AVG P&L", v: `${weightedAvgP}%`, c: pc(parseFloat(weightedAvgP)) },
              ].map((s) => (
                <div key={s.l} style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
                  <span style={{ fontSize: 9, color: "#555", letterSpacing: "0.08em" }}>{s.l}</span>
                  <span style={{ fontSize: 12, color: s.c, fontWeight: 600 }}>{s.v}</span>
                </div>
              ))}
              <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
                <span style={{ fontSize: 9, color: "#555", letterSpacing: "0.08em" }}>W/L</span>
                <span style={{ fontSize: 12, fontWeight: 600 }}>
                  <span style={{ color: "#4ade80" }}>{wins}</span>
                  <span style={{ color: "#444" }}>/</span>
                  <span style={{ color: "#f87171" }}>{positions.length - wins}</span>
                </span>
              </div>
              {atRiskSet.size > 0 && (
                <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
                  <span style={{ fontSize: 9, color: "#555", letterSpacing: "0.08em" }}>AT RISK</span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: "#f87171" }}>{atRiskSet.size}</span>
                </div>
              )}
            </div>
            <span style={{ fontSize: 9, color: "#444", letterSpacing: "0.1em", marginRight: 8 }}>SORT</span>
            {(["entry", "value", "perf", "day", "alpha", "portfolio"] as const).map((k) => {
              const SORT_LABELS: Record<string, string> = { entry: "entry", value: "size", perf: "perf", day: "today", alpha: "alpha", portfolio: "portfolio" };
              return (
                <button key={k} className="matrix-sb" onClick={() => setSortBy(k)} style={{
                  padding: "3px 8px", fontSize: 9, letterSpacing: "0.07em", textTransform: "uppercase",
                  fontFamily: MATRIX_FONT,
                  background: sortBy === k ? "rgba(74,222,128,0.07)" : "transparent",
                  color: sortBy === k ? "#4ade80" : "#333",
                  border: sortBy === k ? "1px solid rgba(74,222,128,0.15)" : "1px solid transparent",
                  cursor: "pointer", transition: "all 0.15s",
                }}>
                  {sortBy === k && <span style={{ marginRight: 3 }}>&#9658;</span>}
                  {SORT_LABELS[k]}
                </button>
              );
            })}
          </div>
          <div style={{ display: "flex", gap: 2 }}>
            {onBack && (
              <button onClick={onBack} style={{
                padding: "2px 7px", fontSize: 7, fontFamily: MATRIX_FONT,
                background: "transparent", color: "#666",
                border: "1px solid rgba(255,255,255,0.04)",
                cursor: "pointer", letterSpacing: "0.08em", marginRight: 8,
              }}>&larr; BACK</button>
            )}
            {filterOverride === undefined && (
              <>
                <button className="matrix-fb" onClick={() => setFilterP(null)} style={{
                  padding: "2px 7px", fontSize: 7, fontFamily: MATRIX_FONT,
                  background: !filterP ? "rgba(74,222,128,0.05)" : "transparent",
                  color: !filterP ? "#4ade80" : "#1a1a1a",
                  border: !filterP ? "1px solid rgba(74,222,128,0.1)" : "1px solid rgba(255,255,255,0.02)",
                  cursor: "pointer", letterSpacing: "0.08em", transition: "all 0.15s",
                }}>ALL</button>
                {portfolios.map((p) => (
                  <button key={p.id} className="matrix-fb" onClick={() => setFilterP(filterP === p.id ? null : p.id)} style={{
                    padding: "2px 7px", fontSize: 7, fontFamily: MATRIX_FONT,
                    background: filterP === p.id ? `${p.color}12` : "transparent",
                    color: filterP === p.id ? p.color : "#1a1a1a",
                    border: `1px solid ${filterP === p.id ? p.color + "33" : "rgba(255,255,255,0.02)"}`,
                    cursor: "pointer", letterSpacing: "0.08em", transition: "all 0.15s",
                    display: "flex", alignItems: "center", gap: 3,
                  }}>
                    <span style={{
                      width: 3, height: 3, borderRadius: "50%", background: p.color,
                      opacity: filterP === p.id ? 1 : 0.15,
                      boxShadow: filterP === p.id ? `0 0 5px ${p.color}66` : "none",
                      transition: "all 0.2s", flexShrink: 0,
                    }} />
                    {p.abbr}
                  </button>
                ))}
              </>
            )}
            <div style={{ marginLeft: "auto", display: "flex", gap: 10, alignItems: "center", fontSize: 8, color: "#444", letterSpacing: "0.08em" }}>
              <Waveform width={80} height={10} />
              <span>MATRIX::v3.0</span>
              <span style={{ color: "#4ade8044", letterSpacing: "0.05em" }}>{clock}</span>
            </div>
          </div>
        </div>

        {/* CRITICAL/HIGH WARNINGS STRIP */}
        {warnings && warnings.filter((w) => w.severity === "critical" || w.severity === "high").length > 0 && (
          <div style={{
            padding: "4px 20px",
            background: "rgba(248,113,113,0.06)",
            borderBottom: "1px solid rgba(248,113,113,0.15)",
            display: "flex", gap: 16, alignItems: "center",
            fontSize: "10px", letterSpacing: "0.06em",
            flexShrink: 0,
          }}>
            {warnings
              .filter((w) => w.severity === "critical" || w.severity === "high")
              .slice(0, 3)
              .map((w, i) => (
                <span key={i} style={{
                  color: w.severity === "critical" ? "var(--red)" : "var(--color-warning)",
                  fontWeight: 600,
                }}>
                  {w.severity.toUpperCase()} {w.title}
                </span>
              ))}
          </div>
        )}

        {/* TAB BAR */}
        <div style={{
          padding: "0 20px",
          borderBottom: "1px solid rgba(74,222,128,0.06)",
          display: "flex", alignItems: "flex-end", gap: 0, flexShrink: 0,
          overflowX: "auto", scrollbarWidth: "none", msOverflowStyle: "none",
        } as React.CSSProperties}>
          {(showSecondaryTabs
            ? ["grid", "actions", "watchlist", "activity", "logs", "history"] as const
            : ["grid"] as const
          ).map((tab) => {
            const hasActions = (analysisResult || isAnalyzing) && tab === "actions";
            const labels: Record<string, string> = {
              grid: `PORTFOLIO [${sorted.length}]`,
              actions: isAnalyzing ? "ACTIONS ●" : analysisResult ? `ACTIONS [${new Set([...analysisResult.approved, ...analysisResult.modified].map(a => `${a.original.ticker}:${a.original.action_type}`)).size}]` : "ACTIONS",
              watchlist: `WATCHLIST [${watchlistCandidates.length}]`,
              activity: `ACTIVITY [${transactions.length}]`,
              logs: "LOGS",
              history: `HISTORY [${snapshots.length}]`,
            };
            const active = viewTab === tab;
            // Color per tab: grid=green (matrix), actions=violet (AI), watchlist=amber, activity=violet, logs=muted
            const TAB_ACTIVE_COLOR: Record<string, string> = {
              grid:      "#4ade80",
              actions:   "#917aff",
              watchlist: "#fbbf24",
              activity:  "#917aff",
              logs:      "#888",
              history:   "#38bdf8",
            };
            const TAB_ACTIVE_BORDER: Record<string, string> = {
              grid:      "#4ade80",
              actions:   "#7c5cfc",
              watchlist: "#fbbf2466",
              activity:  "#7c5cfc",
              logs:      "#555",
              history:   "#38bdf8",
            };
            const activeColor  = TAB_ACTIVE_COLOR[tab]  ?? "#4ade80";
            const activeBorder = TAB_ACTIVE_BORDER[tab] ?? "#4ade80";
            // ACTIONS tab: amber pulse when analysis pending, violet when active
            const pendingColor  = tab === "actions" && hasActions && !active ? "#fbbf24" : null;
            const displayColor  = active ? activeColor : pendingColor ?? "#555";
            const borderColor   = active ? activeBorder : pendingColor ? "#facc1566" : "transparent";
            return (
              <button
                key={tab}
                onClick={() => setViewTab(tab)}
                style={{
                  padding: "5px 12px 6px",
                  fontSize: 10, letterSpacing: "0.08em",
                  fontFamily: MATRIX_FONT,
                  background: "transparent",
                  color: displayColor,
                  border: "none",
                  borderBottom: `2px solid ${borderColor}`,
                  cursor: "pointer",
                  transition: "all 0.12s",
                  marginBottom: -1,
                }}
              >
                {labels[tab]}
              </button>
            );
          })}
        </div>

        {/* GRID (with 3D parallax + treemap) */}
        <div ref={treemapRef} style={{ flex: 1, padding: "4px 14px", overflow: "hidden", minHeight: 0, display: viewTab === "grid" ? undefined : "none" }}>
          <div
            ref={gridRef}
            style={{
              position: "relative",
              width: "100%",
              height: "100%",
              transition: "transform 0.1s ease-out",
            }}
          >
            {treemapRects.length > 0 && sorted.map((pos, i) => {
              const rect = treemapRects[i];
              if (!rect || rect.w < 1 || rect.h < 1) return null;
              const isHov    = hovIdx === i;
              const isAtRisk = atRiskSet.has(i);
              const barW     = (pos.value / maxVal) * 100;
              const tiny  = rect.w < 85  || rect.h < 58;
              const micro = rect.w < 48  || rect.h < 36;
              const large = rect.w >= 150 && rect.h >= 110;

              // Stop loss distance (% below current price)
              const slDist = (pos.stopLoss != null && pos.currentPrice != null && pos.currentPrice > 0)
                ? ((pos.currentPrice - pos.stopLoss) / pos.currentPrice * 100)
                : null;

              // Days held
              const held = pos.entryDate
                ? Math.floor((Date.now() - new Date(pos.entryDate).getTime()) / 864e5)
                : null;

              return (
                <div
                  key={`${pos.ticker}-${pos.portfolioId}-${i}`}
                  className="matrix-cell"
                  onMouseEnter={() => setHovIdx(i)}
                  onMouseLeave={() => setHovIdx(null)}
                  onClick={() => {
                    setSelectedPos(prev => prev?.ticker === pos.ticker && prev?.portfolioId === pos.portfolioId ? null : pos);
                    onPositionClick?.(pos);
                  }}
                  style={{
                    position: "absolute",
                    left: rect.x, top: rect.y, width: rect.w, height: rect.h,
                    boxSizing: "border-box",
                    background: pbg(sortBy === "day" ? pos.day : pos.perf),
                    boxShadow: isAtRisk
                      ? `inset 0 1px 0 rgba(255,255,255,0.05), inset 0 0 0 1px rgba(248,113,113,0.25)`
                      : `inset 0 1px 0 rgba(255,255,255,0.05), inset 0 0 0 1px rgba(255,255,255,0.02)`,
                    padding: micro ? "3px 4px 2px" : tiny ? "5px 6px 4px" : "9px 9px 6px",
                    cursor: "crosshair",
                    overflow: "hidden",
                    opacity: mounted ? undefined : 0,
                    transition: mounted
                      ? "border-color 0.15s, background 0.15s, left 0.35s ease-out, top 0.35s ease-out, width 0.35s ease-out, height 0.35s ease-out"
                      : "opacity 0.3s",
                    transitionDelay: mounted ? "0ms" : `${Math.min(i * 10, 800)}ms`,
                    borderLeft: `2px solid ${isAtRisk ? "#f87171" : pos.portfolioColor}${isHov ? "cc" : "44"}`,
                  }}
                >
                  {/* Chromatic aberration on hover */}
                  <div className="matrix-chroma" style={{
                    position: "absolute", inset: 0, pointerEvents: "none",
                    opacity: isHov ? 1 : 0, transition: "opacity 0.1s",
                    mixBlendMode: "screen" as const,
                  }}>
                    <div style={{ position: "absolute", inset: 0, background: "rgba(255,0,0,0.015)", transform: "translate(-1px,0)" }} />
                    <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,255,0.015)", transform: "translate(1px,0)" }} />
                  </div>

                  {/* Reticles on hover */}
                  <div className="matrix-ret" style={{ position: "absolute", inset: 0, opacity: isHov ? 1 : 0, transition: "opacity 0.12s", pointerEvents: "none" }}>
                    <Reticle color="#4ade80" s={5} />
                  </div>

                  {/* Social heat dot */}
                  {(() => {
                    const heat = socialMap.get(pos.ticker);
                    const hc = heat ? (CELL_HEAT[heat] ?? null) : null;
                    if (!hc) return null;
                    return (
                      <div style={{
                        position: "absolute", top: 3, left: 6,
                        width: 4, height: 4, borderRadius: "50%",
                        background: hc, boxShadow: `0 0 5px ${hc}99`,
                      }} />
                    );
                  })()}

                  {/* Portfolio value bar (bottom edge) */}
                  <div style={{
                    position: "absolute", bottom: 0, left: 0,
                    width: `${barW}%`, height: isHov ? 2 : 1,
                    background: `linear-gradient(90deg,${pos.portfolioColor}${isHov ? "55" : "12"},transparent)`,
                    transition: "all 0.15s",
                  }} />

                  {/* Row 1: Ticker + P&L% — P&L% survives to micro cells (most important field) */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                    <span className="matrix-tk" style={{
                      fontSize: micro ? 9 : tiny ? 11 : large ? 15 : 13, fontWeight: 700, color: "#ccc",
                      letterSpacing: "0.04em", transition: "all 0.12s",
                      whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                    }}>
                      {pos.ticker}
                    </span>
                    <span style={{ fontSize: micro ? 9 : tiny ? 9 : large ? 14 : 11, fontWeight: 700, color: sortBy === "day" ? pc(pos.day) : pc(pos.perf), flexShrink: 0, marginLeft: 2 }}>
                      {sortBy === "day"
                        ? `${pos.day > 0 ? "+" : ""}${pos.day.toFixed(2)}%`
                        : `${pos.perf > 0 ? "+" : ""}${pos.perf.toFixed(1)}%`}
                    </span>
                  </div>

                  {/* Row 2 (large only): Price + day change */}
                  {large && pos.currentPrice != null && (
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 5 }}>
                      <span style={{ fontSize: 18, fontWeight: 300, color: "#ddd", letterSpacing: "-0.01em" }}>
                        ${pos.currentPrice.toFixed(2)}
                      </span>
                      {pos.day !== 0 && (
                        <span style={{ fontSize: 10, fontWeight: 500, color: pc(pos.day) }}>
                          {pos.day > 0 ? "+" : ""}{pos.day.toFixed(2)}% today
                        </span>
                      )}
                    </div>
                  )}

                  {/* Row 3 (large only): Value + shares */}
                  {large && (
                    <div style={{ display: "flex", gap: 12, marginTop: 3, alignItems: "baseline" }}>
                      <span style={{ fontSize: 11, color: "#aaa" }}>
                        ${pos.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </span>
                      {pos.shares != null && pos.avgCost != null && (
                        <span style={{ fontSize: 10, color: "#777" }}>
                          {pos.shares.toFixed(0)} sh @ ${pos.avgCost.toFixed(2)}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Sparkline — larger on large cells */}
                  {!tiny && (
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginTop: large ? 8 : 2 }}>
                      {held !== null && !large && (
                        <span style={{ fontSize: 9, color: held >= 35 ? "#fbbf24" : "#555" }}>
                          {held}d
                        </span>
                      )}
                      <Sparkline data={pos.sparkline} color={(sortBy === "day" ? pos.day : pos.perf) >= 0 ? "#4ade80" : "#f87171"} w={large ? rect.w - 20 : 56} h={large ? 36 : 22} />
                    </div>
                  )}

                  {/* Bottom row (large): held + SL side by side */}
                  {large && (held !== null || slDist !== null) && (
                    <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
                      {held !== null && (
                        <span style={{ fontSize: 10, color: held >= 35 ? "#fbbf24" : "#777", letterSpacing: "0.05em" }}>
                          {held}d held
                        </span>
                      )}
                      {slDist !== null && (
                        <span style={{
                          fontSize: 10, letterSpacing: "0.05em",
                          color: slDist < 8 ? "#f87171" : slDist < 15 ? "#fbbf24" : "#777",
                        }}>
                          SL -{slDist.toFixed(1)}%
                        </span>
                      )}
                    </div>
                  )}

                  {/* Row: Stop distance — non-large cells only */}
                  {!large && !tiny && slDist !== null && (
                    <div style={{ marginTop: 3 }}>
                      <span style={{
                        fontSize: 8, letterSpacing: "0.05em",
                        color: slDist < 8 ? "#f87171" : slDist < 15 ? "#fbbf24" : "#444",
                      }}>
                        SL -{slDist.toFixed(1)}%
                      </span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* ACTIONS PANEL */}
        {viewTab === "actions" && (
          <div style={{ flex: 1, minHeight: 0, overflow: "hidden", background: "var(--surface-0)" }}>
            <ActionsTab />
          </div>
        )}

        {/* WATCHLIST PANEL */}
        {viewTab === "watchlist" && (
          <WatchlistPanel candidates={watchlistCandidates} onTickerClick={(ticker) => {
            const existing = positions.find(p => p.ticker === ticker);
            if (existing) { setSelectedPos(existing); return; }
            // Build a minimal stub so the detail card can fetch company info
            setSelectedPos({
              ticker, portfolioId: portfolios[0]?.id ?? "", portfolioName: portfolios[0]?.name ?? "",
              portfolioAbbr: portfolios[0]?.abbr ?? "", portfolioColor: portfolios[0]?.color ?? "#4ade80",
              portfolioHex: portfolios[0]?.hex ?? [74,222,128], value: 0, perf: 0, day: 0,
              sparkline: [], sector: "", vol: null, beta: null, mktCap: "",
            });
          }} />
        )}

        {/* ACTIVITY PANEL */}
        {viewTab === "activity" && (
          <ActivityPanel transactions={transactions} onTickerClick={(ticker) => {
            const existing = positions.find(p => p.ticker === ticker);
            if (existing) { setSelectedPos(existing); return; }
            setSelectedPos({
              ticker, portfolioId: portfolios[0]?.id ?? "", portfolioName: portfolios[0]?.name ?? "",
              portfolioAbbr: portfolios[0]?.abbr ?? "", portfolioColor: portfolios[0]?.color ?? "#4ade80",
              portfolioHex: portfolios[0]?.hex ?? [74,222,128], value: 0, perf: 0, day: 0,
              sparkline: [], sector: "", vol: null, beta: null, mktCap: "",
            });
          }} />
        )}

        {/* LOGS PANEL */}
        {viewTab === "logs" && (
          <LogsPanel scanStatus={scanStatus} />
        )}

        {/* HISTORY PANEL */}
        {viewTab === "history" && (
          <HistoryPanel snapshots={snapshots} startingCapital={startingCapital} />
        )}

        {/* STATUS BAR */}
        <div style={{
          padding: "3px 20px",
          borderTop: "1px solid rgba(74,222,128,0.04)",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          fontSize: 8, color: "#444", letterSpacing: "0.08em", flexShrink: 0,
        }}>
          <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
            {top && <span>&#9650; <span style={{ color: "#4ade80" }}>{top.ticker} +{top.perf.toFixed(1)}%</span></span>}
            {bot && <span>&#9660; <span style={{ color: "#f87171" }}>{bot.ticker} {bot.perf.toFixed(1)}%</span></span>}
            {atRiskSet.size > 0 && (
              <span>&#9474; <span style={{ color: "#f87171" }}>{atRiskSet.size} near stop</span></span>
            )}
          </div>
          <div />
        </div>
      </div>

      {/* HOVER DETAIL PANEL */}
      {hovered && !selectedPos && (
        <div style={{
          position: "fixed", bottom: 0, left: 0, right: 0,
          background: "rgba(4,6,8,0.95)",
          borderTop: "1px solid rgba(74,222,128,0.1)",
          padding: "8px 20px",
          display: "flex", gap: 24, alignItems: "center",
          zIndex: 200, animation: "matrixSlideUp 0.12s ease",
          backdropFilter: "blur(12px)",
          pointerEvents: "none",
        }}>
          <div style={{ position: "relative", padding: "3px 10px" }}>
            <Reticle color={hovered.portfolioColor} s={7} />
            <span style={{
              fontSize: 16, fontWeight: 700, color: "#fff",
              textShadow: `0 0 14px ${hovered.portfolioColor}44`,
            }}>{hovered.ticker}</span>
          </div>
          {[
            { l: "PORTFOLIO", v: hovered.portfolioName, c: hovered.portfolioColor },
            { l: "VALUE", v: `$${hovered.value.toLocaleString()}` },
            { l: "ALL-TIME", v: `${hovered.perf > 0 ? "+" : ""}${hovered.perf.toFixed(1)}%`, c: pc(hovered.perf) },
            { l: "DAY", v: `${hovered.day > 0 ? "+" : ""}${hovered.day.toFixed(2)}%`, c: pc(hovered.day) },
            { l: "VOL", v: hovered.vol != null ? `${hovered.vol}%` : "N/A" },
            { l: "BETA", v: hovered.beta != null ? String(hovered.beta) : "N/A" },
            { l: "SECTOR", v: hovered.sector },
          ].map((s) => (
            <div key={s.l}>
              <div style={{ fontSize: 9, color: "#555", letterSpacing: "0.09em" }}>{s.l}</div>
              <div style={{ fontSize: 12, color: s.c ?? "#888", fontWeight: 500 }}>{s.v}</div>
            </div>
          ))}
          <div style={{ flex: 1, display: "flex", justifyContent: "flex-end" }}>
            <Sparkline data={hovered.sparkline} color={hovered.perf >= 0 ? "#4ade80" : "#f87171"} w={110} h={24} />
          </div>
        </div>
      )}

      {/* DETAIL: bottom panel in portfolio view, modal in overview */}
      {showSecondaryTabs
        ? <BottomPanel
            pos={selectedPos}
            onClose={() => setSelectedPos(null)}
            portfolioId={portfolios[0]?.id}
            watchlistCandidates={watchlistCandidates}
            rationale={selectedPos ? (positionRationales[selectedPos.ticker] ?? null) : null}
            buyTx={selectedPos ? (transactions.filter(t => t.ticker === selectedPos.ticker && t.action === "BUY").at(-1) ?? null) : null}
            sellReasoning={selectedPos ? (pendingSellReasoningMap[selectedPos.ticker] ?? null) : null}
          />
        : <DetailCard pos={selectedPos} onClose={() => setSelectedPos(null)} portfolioId={portfolios[0]?.id} watchlistCandidates={watchlistCandidates} />
      }
    </div>
  );
}

// ─── Watchlist Panel ──────────────────────────────────────────────────────────

const HEAT_COLOR: Record<string, string> = {
  SPIKING: "#f87171",
  HOT: "#fb923c",
  WARM: "#facc15",
  COLD: "#555",
};

function WatchlistPanel({ candidates, onTickerClick }: { candidates: WatchlistCandidate[]; onTickerClick: (ticker: string) => void }) {
  const sorted = [...candidates].sort((a, b) => b.score - a.score);
  if (sorted.length === 0) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "#555", fontSize: 10, fontFamily: MATRIX_FONT, letterSpacing: "0.1em" }}>
        NO WATCHLIST DATA — RUN SCAN TO POPULATE
      </div>
    );
  }
  return (
    <div style={{ flex: 1, overflow: "auto", minHeight: 0 }}>
      {/* Header row */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "80px 1fr 60px 80px 120px 65px 80px",
        padding: "5px 20px",
        fontSize: 9, color: "#444", letterSpacing: "0.09em",
        borderBottom: "1px solid rgba(74,222,128,0.04)",
        position: "sticky", top: 0, background: "#040608", zIndex: 2,
      }}>
        <span>TICKER</span>
        <span>NOTES</span>
        <span>SCORE</span>
        <span>SECTOR</span>
        <span>SOURCE</span>
        <span>ADDED</span>
        <span>HEAT</span>
      </div>
      {sorted.map((c, i) => (
        <div key={`${c.ticker}-${i}`} style={{
          display: "grid",
          gridTemplateColumns: "80px 1fr 60px 80px 120px 65px 80px",
          padding: "5px 20px",
          borderBottom: "1px solid rgba(255,255,255,0.02)",
          fontSize: 11, fontFamily: MATRIX_FONT,
          alignItems: "center",
        }}>
          <span onClick={() => onTickerClick(c.ticker)} style={{ color: "#e8ffe8", fontWeight: 700, letterSpacing: "0.04em", cursor: "pointer", textDecoration: "underline", textDecorationColor: "rgba(74,222,128,0.3)" }}>{c.ticker}</span>
          <span style={{ color: "#666", fontSize: 10, overflow: "hidden", whiteSpace: "nowrap", textOverflow: "ellipsis", paddingRight: 8 }}>{c.notes || "—"}</span>
          <span style={{ color: c.score >= 70 ? "#4ade80" : c.score >= 50 ? "#facc15" : "#888", fontWeight: 600 }}>{c.score.toFixed(0)}</span>
          <span style={{ color: "#666", fontSize: 10 }}>{c.sector || "—"}</span>
          <span style={{ color: "#555", fontSize: 10 }}>{c.source || "—"}</span>
          <span style={{ color: "#555", fontSize: 10 }}>{c.added_date ? new Date(c.added_date + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "—"}</span>
          <span style={{
            fontSize: 10, fontWeight: 700, letterSpacing: "0.06em",
            color: c.social_heat ? (HEAT_COLOR[c.social_heat] ?? "#555") : "#333",
          }}>{c.social_heat ?? "—"}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Activity Panel ───────────────────────────────────────────────────────────

function activityDaysHeld(tx: Transaction, allTxs: Transaction[]): number | null {
  const sellDate = tx.date.slice(0, 10);
  const matchingBuy = [...allTxs]
    .filter(t => t.ticker === tx.ticker && t.action === "BUY" && t.date.slice(0, 10) <= sellDate)
    .pop();
  if (!matchingBuy) return null;
  return Math.floor(
    (new Date(sellDate).getTime() - new Date(matchingBuy.date.slice(0, 10)).getTime()) / (1000 * 60 * 60 * 24)
  );
}

function ActivityPanel({ transactions, onTickerClick }: { transactions: Transaction[]; onTickerClick: (ticker: string) => void }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const sorted = [...transactions].reverse().slice(0, 100);
  if (sorted.length === 0) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "#555", fontSize: 10, fontFamily: MATRIX_FONT, letterSpacing: "0.1em" }}>
        NO TRADE HISTORY
      </div>
    );
  }
  const COLS = "90px 50px 90px 90px 90px 80px 60px 1fr";
  return (
    <div style={{ flex: 1, overflow: "auto", minHeight: 0 }}>
      <div style={{
        display: "grid",
        gridTemplateColumns: COLS,
        padding: "5px 20px",
        fontSize: 9, color: "#444", letterSpacing: "0.09em",
        borderBottom: "1px solid rgba(74,222,128,0.04)",
        position: "sticky", top: 0, background: "#040608", zIndex: 2,
      }}>
        <span>DATE</span>
        <span>ACT</span>
        <span>TICKER</span>
        <span>ENTRY / QTY</span>
        <span>SELL / PRICE</span>
        <span>P&L / TOTAL</span>
        <span>RET%</span>
        <span>REASON</span>
      </div>
      {sorted.map((tx) => {
        const isBuy = tx.action === "BUY";
        const ac = isBuy ? "#4ade80" : "#f87171";
        const hasPnl = !isBuy && tx.realized_pnl != null && tx.realized_pnl_pct != null;
        const pnlColor = hasPnl ? (tx.realized_pnl! >= 0 ? "#4ade80" : "#f87171") : "#aaa";
        const pnlStr = hasPnl
          ? `${tx.realized_pnl! >= 0 ? "+" : ""}$${Math.abs(tx.realized_pnl!).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
          : `$${tx.total_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
        const pctStr = hasPnl
          ? `${tx.realized_pnl_pct! >= 0 ? "+" : ""}${tx.realized_pnl_pct!.toFixed(1)}%`
          : "";
        const daysHeld = !isBuy ? activityDaysHeld(tx, transactions) : null;
        const rationale = parseTradeRationale(tx);
        const reasoning = rationale?.ai_reasoning || tradeExplanation(tx);
        const isExpanded = expandedId === tx.transaction_id;
        return (
          <div key={tx.transaction_id}>
            <div
              onClick={() => setExpandedId(isExpanded ? null : tx.transaction_id)}
              style={{
                display: "grid",
                gridTemplateColumns: COLS,
                padding: "5px 20px",
                borderBottom: isExpanded ? "none" : "1px solid rgba(255,255,255,0.02)",
                fontSize: 9, fontFamily: MATRIX_FONT, alignItems: "center",
                cursor: "pointer",
                background: isExpanded ? "rgba(255,255,255,0.02)" : undefined,
              }}>
              <span style={{ color: "#555", fontSize: 10 }}>
                {tx.date.slice(0, 10)}
                {tx.date.length > 10 && (
                  <span style={{ color: "#3a3a3a", display: "block", fontSize: 9 }}>
                    {tx.date.slice(11, 16)}
                  </span>
                )}
              </span>
              <span style={{ color: ac, fontWeight: 700 }}>{tx.action}</span>
              <span
                onClick={(e) => { e.stopPropagation(); onTickerClick(tx.ticker); }}
                style={{ color: "#e8ffe8", fontWeight: 700, cursor: "pointer", textDecoration: "underline", textDecorationColor: "rgba(74,222,128,0.3)" }}
              >{tx.ticker}</span>
              {/* Entry price (sells) or qty (buys) */}
              {!isBuy && tx.entry_price != null
                ? <span style={{ color: "#666" }}>${tx.entry_price.toFixed(2)}</span>
                : <span style={{ color: "#888" }}>{isBuy ? tx.shares : "—"}</span>
              }
              {/* Sell price or buy price */}
              <span style={{ color: "#888" }}>${tx.price.toFixed(2)}</span>
              {/* P&L $ (sells) or total (buys) */}
              <span style={{ color: pnlColor, fontWeight: 600 }}>
                {pnlStr}
                {/* P/L badge for sells */}
                {hasPnl && (
                  <span style={{
                    marginLeft: 5, fontSize: 7, fontWeight: 700,
                    padding: "1px 3px",
                    background: tx.realized_pnl! >= 0 ? "rgba(74,222,128,0.12)" : "rgba(248,113,113,0.12)",
                    color: tx.realized_pnl! >= 0 ? "#4ade80" : "#f87171",
                  }}>
                    {tx.realized_pnl! >= 0 ? "P" : "L"}
                  </span>
                )}
              </span>
              {/* Return % + days held (sells only) */}
              <span style={{ color: pnlColor, fontWeight: 600, fontSize: 8 }}>
                {pctStr}
                {daysHeld != null && (
                  <span style={{ display: "block", color: "#444", fontSize: 7, fontWeight: 400 }}>
                    {daysHeld}d held
                  </span>
                )}
              </span>
              <span style={{ color: "#555", fontSize: 8 }}>{tx.reason}</span>
            </div>
            {/* Expanded reasoning row */}
            {isExpanded && (
              <div style={{
                padding: "8px 20px 10px 20px",
                borderBottom: "1px solid rgba(255,255,255,0.03)",
                borderLeft: "2px solid rgba(74,222,128,0.3)",
                background: "rgba(74,222,128,0.02)",
              }}>
                <div style={{ fontSize: 9, color: "#3a5a3a", letterSpacing: "0.08em", marginBottom: 4, textTransform: "uppercase" }}>
                  {isBuy ? "Buy Reasoning" : "Sell Reasoning"}
                </div>
                <div style={{ fontSize: 11, color: "#888", lineHeight: 1.6, fontFamily: MATRIX_FONT }}>
                  {reasoning}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Logs Panel ───────────────────────────────────────────────────────────────

function LogsPanel({ scanStatus }: { scanStatus?: ScanJobStatus }) {
  const statusColor: Record<string, string> = { idle: "#555", running: "#facc15", complete: "#4ade80", error: "#f87171" };
  const sc = scanStatus?.status ?? "idle";
  return (
    <div style={{ flex: 1, overflow: "auto", minHeight: 0, padding: "16px 20px", fontFamily: MATRIX_FONT }}>
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 9, color: "#555", letterSpacing: "0.09em", marginBottom: 8 }}>SCAN STATUS</div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <span style={{
            fontSize: 11, fontWeight: 700, color: statusColor[sc] ?? "#555",
            letterSpacing: "0.08em",
            textShadow: sc === "running" ? "0 0 8px rgba(250,204,21,0.4)" : sc === "complete" ? "0 0 8px rgba(74,222,128,0.3)" : "none",
          }}>
            {sc === "running" ? "● SCANNING" : sc === "complete" ? "✓ COMPLETE" : sc === "error" ? "✗ ERROR" : "○ IDLE"}
          </span>
          {scanStatus?.started_at && (
            <span style={{ fontSize: 10, color: "#555" }}>started {scanStatus.started_at.slice(0, 19).replace("T", " ")}</span>
          )}
          {scanStatus?.finished_at && (
            <span style={{ fontSize: 10, color: "#555" }}>finished {scanStatus.finished_at.slice(0, 19).replace("T", " ")}</span>
          )}
        </div>
        {scanStatus?.error && (
          <div style={{ marginTop: 8, fontSize: 11, color: "#f87171", background: "rgba(248,113,113,0.06)", padding: "6px 10px", border: "1px solid rgba(248,113,113,0.12)" }}>
            {scanStatus.error}
          </div>
        )}
        {scanStatus?.message && (
          <div style={{ marginTop: 8, fontSize: 11, color: "#888" }}>{scanStatus.message}</div>
        )}
      </div>

      {scanStatus?.result && (
        <>
          <div style={{ fontSize: 9, color: "#555", letterSpacing: "0.09em", marginBottom: 8 }}>LAST SCAN RESULTS</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: 8, marginBottom: 16 }}>
            {[
              { l: "DISCOVERED", v: scanStatus.result.discovered },
              { l: "ADDED", v: scanStatus.result.added },
              { l: "MARKED STALE", v: scanStatus.result.marked_stale },
              { l: "REMOVED", v: scanStatus.result.removed },
              { l: "POOR REMOVED", v: scanStatus.result.poor_performers_removed },
              { l: "TOTAL ACTIVE", v: scanStatus.result.total_active },
              ...(scanStatus.result.elapsed_seconds != null
                ? [{ l: "ELAPSED", v: `${scanStatus.result.elapsed_seconds.toFixed(1)}s` }]
                : []),
            ].map((s) => (
              <div key={s.l} style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(74,222,128,0.06)", padding: "8px 10px" }}>
                <div style={{ fontSize: 9, color: "#555", letterSpacing: "0.08em", marginBottom: 4 }}>{s.l}</div>
                <div style={{ fontSize: 15, color: "#e8ffe8", fontWeight: 700 }}>{s.v}</div>
              </div>
            ))}
          </div>
          {Object.keys(scanStatus.result.sector_balanced).length > 0 && (
            <>
              <div style={{ fontSize: 9, color: "#555", letterSpacing: "0.09em", marginBottom: 8 }}>SECTOR DISTRIBUTION</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {Object.entries(scanStatus.result.sector_balanced)
                  .sort((a, b) => b[1] - a[1])
                  .map(([sector, count]) => {
                    const maxCount = Math.max(...Object.values(scanStatus.result!.sector_balanced));
                    return (
                      <div key={sector} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: 10, color: "#666", width: 160, flexShrink: 0 }}>{sector}</span>
                        <div style={{ flex: 1, height: 4, background: "rgba(255,255,255,0.04)", position: "relative" }}>
                          <div style={{
                            position: "absolute", left: 0, top: 0, bottom: 0,
                            width: `${(count / maxCount) * 100}%`,
                            background: "rgba(74,222,128,0.3)",
                          }} />
                        </div>
                        <span style={{ fontSize: 10, color: "#888", width: 20, textAlign: "right", flexShrink: 0 }}>{count}</span>
                      </div>
                    );
                  })}
              </div>
            </>
          )}
        </>
      )}

      {!scanStatus && (
        <div style={{ color: "#555", fontSize: 10, letterSpacing: "0.1em", marginTop: 24 }}>
          NO SCAN DATA — TRIGGER SCAN FROM TOPBAR
        </div>
      )}
    </div>
  );
}

// ─── History Panel ────────────────────────────────────────────────────────────

function HistoryPanel({ snapshots, startingCapital }: { snapshots: Snapshot[]; startingCapital?: number }) {
  const sorted = [...snapshots].sort((a, b) => a.date.localeCompare(b.date));
  const current = sorted.at(-1);
  const peak = sorted.reduce((best, s) => s.total_equity > best.total_equity ? s : best, sorted[0] ?? { total_equity: 0, date: "" });
  const start = startingCapital ?? sorted[0]?.total_equity ?? 0;
  const returnPct = start > 0 && current ? ((current.total_equity - start) / start) * 100 : 0;
  const col = "#38bdf8";

  const fmt$ = (n: number) => `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  const fmtPct = (n: number) => `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
  const pc = (n: number) => n >= 0 ? "#4ade80" : "#f87171";

  return (
    <div style={{ flex: 1, overflow: "auto", minHeight: 0, fontFamily: MATRIX_FONT, padding: "16px 20px" }}>

      {/* Summary cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 20 }}>
        {[
          { label: "STARTING", value: fmt$(start), color: "#888" },
          { label: "CURRENT", value: current ? fmt$(current.total_equity) : "—", color: "#ccc" },
          { label: "RETURN", value: fmtPct(returnPct), color: pc(returnPct) },
          { label: "PEAK", value: peak ? fmt$(peak.total_equity) : "—", color: col, sub: peak?.date },
        ].map(({ label, value, color, sub }) => (
          <div key={label} style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(56,189,248,0.12)", padding: "10px 12px" }}>
            <div style={{ fontSize: 8, color: "#555", letterSpacing: "0.1em", marginBottom: 4 }}>{label}</div>
            <div style={{ fontSize: 14, fontWeight: 700, color }}>{value}</div>
            {sub && <div style={{ fontSize: 9, color: "#444", marginTop: 2 }}>{sub}</div>}
          </div>
        ))}
      </div>

      {/* Table */}
      <div style={{ border: "1px solid rgba(56,189,248,0.08)" }}>
        {/* Header */}
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 1.4fr 1fr 1fr",
          padding: "5px 14px", fontSize: 8, color: "#444", letterSpacing: "0.1em",
          borderBottom: "1px solid rgba(56,189,248,0.08)",
          position: "sticky", top: 0, background: "#040608", zIndex: 2,
        }}>
          <span>DATE</span><span>EQUITY</span><span>DAY P&L</span><span>DAY %</span>
        </div>
        {[...sorted].reverse().map((s) => (
          <div key={s.date} style={{
            display: "grid", gridTemplateColumns: "1fr 1.4fr 1fr 1fr",
            padding: "6px 14px", fontSize: 11,
            borderBottom: "1px solid rgba(255,255,255,0.02)",
            alignItems: "center",
          }}>
            <span style={{ color: "#666", fontSize: 10 }}>{s.date}</span>
            <span style={{ color: "#ccc", fontWeight: 600 }}>{fmt$(s.total_equity)}</span>
            <span style={{ color: pc(s.day_pnl) }}>{s.day_pnl >= 0 ? "+" : ""}{fmt$(s.day_pnl)}</span>
            <span style={{ color: pc(s.day_pnl_pct), fontWeight: 600 }}>{fmtPct(s.day_pnl_pct)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
