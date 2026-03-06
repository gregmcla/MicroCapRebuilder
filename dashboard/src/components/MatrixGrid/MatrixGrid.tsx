import { useState, useMemo, useEffect, useRef, useCallback } from "react";
import type { MatrixGridProps, MatrixPosition } from "./types";
import { pc, pbg, fv, MATRIX_FONT } from "./constants";
import Sparkline from "./Sparkline";
import AllocRing from "./AllocRing";
import Waveform from "./Waveform";
import Reticle from "./Reticle";
import TickerTape from "./TickerTape";
import DetailCard from "./DetailCard";
import BackgroundCanvas from "./BackgroundCanvas";
import EKGStrip from "./EKGStrip";

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
}: MatrixGridProps) {
  const [hovIdx, setHovIdx] = useState<number | null>(null);
  const [sortBy, setSortBy] = useState<"value" | "perf" | "alpha" | "portfolio">("value");
  const [filterP, setFilterP] = useState<string | null>(initialFilter ?? null);
  const [mounted, setMounted] = useState(false);
  const [boot, setBoot] = useState(0);
  const [clock, setClock] = useState("");
  const [glitchIdx, setGlitchIdx] = useState(-1);
  const [anomalies, setAnomalies] = useState(new Set<number>());
  const [selectedPos, setSelectedPos] = useState<MatrixPosition | null>(null);
  const [breathPhase, setBreathPhase] = useState(0);
  const [bootLines, setBootLines] = useState<string[]>([]);
  const mouseXRef = useRef(-1000);
  const mouseYRef = useRef(-1000);
  const gridRef = useRef<HTMLDivElement>(null);
  const breathFrameRef = useRef<number>(0);

  // Boot sequence
  useEffect(() => {
    BOOT_LINES.forEach((line, i) => {
      setTimeout(() => setBootLines((prev) => [...prev, line]), i * 120);
    });
    setTimeout(() => setBoot(1), 300);
    setTimeout(() => setBoot(2), 700);
    setTimeout(() => { setBoot(3); setMounted(true); }, 1100);
  }, []);

  // Clock
  useEffect(() => {
    const tick = () => {
      const d = new Date();
      setClock(
        d.toLocaleTimeString("en-US", { hour12: false }) +
        "." + String(d.getMilliseconds()).padStart(3, "0")
      );
    };
    tick();
    const i = setInterval(tick, 47);
    return () => clearInterval(i);
  }, []);

  // Glitch effect
  useEffect(() => {
    if (positions.length === 0) return;
    let timeoutId: ReturnType<typeof setTimeout>;
    const schedule = () => {
      const delay = 2500 + Math.random() * 4000;
      timeoutId = setTimeout(() => {
        setGlitchIdx(Math.floor(Math.random() * positions.length));
        setTimeout(() => setGlitchIdx(-1), 100);
        schedule();
      }, delay);
    };
    schedule();
    return () => clearTimeout(timeoutId);
  }, [positions.length]);

  // Anomaly scanner
  useEffect(() => {
    if (positions.length === 0) return;
    const i = setInterval(() => {
      const newA = new Set<number>();
      const count = Math.min(3, positions.length);
      for (let j = 0; j < count; j++) newA.add(Math.floor(Math.random() * positions.length));
      setAnomalies(newA);
      setTimeout(() => setAnomalies(new Set()), 2000);
    }, 5000);
    return () => clearInterval(i);
  }, [positions.length]);

  // Breathing wave
  useEffect(() => {
    const tick = () => {
      setBreathPhase((prev) => prev + 0.02);
      breathFrameRef.current = requestAnimationFrame(tick);
    };
    breathFrameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(breathFrameRef.current);
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "1") setSortBy("value");
      if (e.key === "2") setSortBy("perf");
      if (e.key === "3") setSortBy("alpha");
      if (e.key === "4") setSortBy("portfolio");
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

  // Sorted / filtered positions
  const sorted = useMemo(() => {
    let arr = [...positions];
    if (filterP) arr = arr.filter((p) => p.portfolioId === filterP);
    if (sortBy === "value") arr.sort((a, b) => b.value - a.value);
    else if (sortBy === "perf") arr.sort((a, b) => b.perf - a.perf);
    else if (sortBy === "alpha") arr.sort((a, b) => a.ticker.localeCompare(b.ticker));
    else if (sortBy === "portfolio") arr.sort((a, b) => a.portfolioId.localeCompare(b.portfolioId) || b.value - a.value);
    return arr;
  }, [positions, sortBy, filterP]);

  const maxVal = useMemo(() => Math.max(...positions.map((p) => p.value), 1), [positions]);
  const hovered = hovIdx !== null ? sorted[hovIdx] : null;
  const totalVal = positions.reduce((s, p) => s + p.value, 0);
  const avgP = positions.length > 0
    ? (positions.reduce((s, p) => s + p.perf, 0) / positions.length).toFixed(1)
    : "0.0";
  const wins = positions.filter((p) => p.perf > 0).length;
  const top = positions.length > 0 ? [...positions].sort((a, b) => b.perf - a.perf)[0] : null;
  const bot = positions.length > 0 ? [...positions].sort((a, b) => a.perf - b.perf)[0] : null;
  const tickers = useMemo(() => [...new Set(positions.map((p) => p.ticker))], [positions]);

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
        .matrix-cell:hover { background: rgba(74,222,128,0.035) !important; }
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

        {/* HEADER */}
        <div style={{ padding: "10px 20px 0", display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 20 }}>
            <div>
              <div style={{ fontSize: 7, color: "#4ade8044", letterSpacing: "0.2em", marginBottom: 3 }}>
                SYS::MATRIX_v3.0
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                <span style={{ fontSize: 18, fontWeight: 700, color: "#e8ffe8", letterSpacing: "0.08em", textShadow: "0 0 25px rgba(74,222,128,0.12)" }}>
                  THE MATRIX
                </span>
                <span style={{ fontSize: 8, color: "#f87171", letterSpacing: "0.06em", border: "1px solid #f8717133", padding: "1px 5px", background: "rgba(248,113,113,0.05)" }}>
                  LIVE
                </span>
              </div>
            </div>
            <AllocRing positions={positions} portfolios={portfolios} />
            <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 2 }}>
              {(["FEED", "SYNC", "SCAN", "EKG", "THREAT"] as const).map((s, i) => (
                <div key={s} style={{
                  display: "flex", alignItems: "center", gap: 3, fontSize: 7,
                  color: i === 4 ? (anomalies.size > 0 ? "#f87171" : "#222") : "#333",
                  letterSpacing: "0.1em", transition: "color 0.3s",
                }}>
                  <span style={{
                    display: "inline-block", width: 4, height: 4, borderRadius: "50%",
                    background: i === 4 ? (anomalies.size > 0 ? "#f87171" : "#222") : "#4ade80",
                    boxShadow: i === 4 && anomalies.size > 0 ? "0 0 6px #f8717166" : i < 4 ? "0 0 4px #4ade8044" : "none",
                    transition: "all 0.3s",
                  }} />
                  {s}
                </div>
              ))}
            </div>
          </div>

          <div style={{ display: "flex", gap: 16, alignItems: "flex-end" }}>
            {[
              { l: "POS", v: String(sorted.length), c: "#e8ffe8" },
              { l: "EQUITY", v: `$${totalVal.toLocaleString()}`, c: "#e8ffe8" },
              { l: "AVG P&L", v: `${avgP}%`, c: pc(parseFloat(avgP)) },
            ].map((s) => (
              <div key={s.l} style={{ textAlign: "right" }}>
                <div style={{ fontSize: 7, color: "#222", letterSpacing: "0.14em" }}>{s.l}</div>
                <div style={{ fontSize: 13, color: s.c, fontWeight: 600 }}>{s.v}</div>
              </div>
            ))}
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 7, color: "#222", letterSpacing: "0.14em" }}>W/L</div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>
                <span style={{ color: "#4ade80" }}>{wins}</span>
                <span style={{ color: "#151515" }}>/</span>
                <span style={{ color: "#f87171" }}>{positions.length - wins}</span>
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 7, color: "#222", letterSpacing: "0.14em" }}>SYS.CLK</div>
              <div style={{ fontSize: 10, color: "#4ade8044" }}>{clock}</div>
            </div>
          </div>
        </div>

        {/* EKG VITALS */}
        {showEKG && (
          <div style={{
            height: 48, margin: "4px 20px 0",
            border: "1px solid rgba(74,222,128,0.04)",
            position: "relative", overflow: "hidden", background: "rgba(0,0,0,0.2)",
            flexShrink: 0,
          }}>
            <EKGStrip portfolios={portfolios} />
            <div style={{ position: "absolute", top: 2, right: 6, fontSize: 7, color: "#222", letterSpacing: "0.12em" }}>
              PORTFOLIO VITALS
            </div>
          </div>
        )}

        {/* TICKER TAPE */}
        {showTickerTape && positions.length > 0 && (
          <div style={{ margin: "4px 20px 0", flexShrink: 0 }}>
            <TickerTape positions={positions} />
          </div>
        )}

        {/* CONTROLS */}
        <div style={{ padding: "6px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", flexShrink: 0 }}>
          <div style={{ display: "flex", gap: 1, alignItems: "center" }}>
            <span style={{ fontSize: 7, color: "#1a1a1a", letterSpacing: "0.14em", marginRight: 8 }}>SORT</span>
            {(["value", "perf", "alpha", "portfolio"] as const).map((k, n) => (
              <button key={k} className="matrix-sb" onClick={() => setSortBy(k)} style={{
                padding: "2px 8px", fontSize: 8, letterSpacing: "0.08em", textTransform: "uppercase",
                fontFamily: MATRIX_FONT,
                background: sortBy === k ? "rgba(74,222,128,0.07)" : "transparent",
                color: sortBy === k ? "#4ade80" : "#1e1e1e",
                border: sortBy === k ? "1px solid rgba(74,222,128,0.12)" : "1px solid transparent",
                cursor: "pointer", transition: "all 0.15s",
              }}>
                {sortBy === k && <span style={{ marginRight: 3 }}>&#9658;</span>}
                {k}
                <span style={{ fontSize: 6, color: "#1a1a1a", marginLeft: 4 }}>[{n + 1}]</span>
              </button>
            ))}
          </div>
          <div style={{ display: "flex", gap: 2 }}>
            {onBack && (
              <button onClick={onBack} style={{
                padding: "2px 7px", fontSize: 7, fontFamily: MATRIX_FONT,
                background: "transparent", color: "#333",
                border: "1px solid rgba(255,255,255,0.04)",
                cursor: "pointer", letterSpacing: "0.08em", marginRight: 8,
              }}>&larr; BACK</button>
            )}
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
          </div>
        </div>

        {/* GRID (with 3D parallax) */}
        <div style={{ flex: 1, padding: "4px 14px", overflow: "auto", minHeight: 0 }}>
          <div
            ref={gridRef}
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(112px, 1fr))",
              gap: 2, alignContent: "start",
              transition: "transform 0.1s ease-out",
              transformStyle: "preserve-3d",
            }}
          >
            {sorted.map((pos, i) => {
              const isHov = hovIdx === i;
              const isGlitch = glitchIdx === i;
              const isAnomaly = anomalies.has(positions.indexOf(pos));
              const barW = (pos.value / maxVal) * 100;
              const breath = Math.sin(breathPhase + i * 0.08) * 0.3;

              return (
                <div
                  key={`${pos.ticker}-${pos.portfolioId}-${i}`}
                  className="matrix-cell"
                  onMouseEnter={() => setHovIdx(i)}
                  onMouseLeave={() => setHovIdx(null)}
                  onClick={() => {
                    setSelectedPos(pos);
                    onPositionClick?.(pos);
                  }}
                  style={{
                    background: pbg(pos.perf),
                    padding: "6px 6px 4px",
                    cursor: "crosshair",
                    position: "relative",
                    overflow: "hidden",
                    opacity: mounted ? 0.85 + breath * 0.15 : 0,
                    transform: mounted ? `translateZ(${breath * 2}px)` : "translateY(6px)",
                    transition: "opacity 0.3s, transform 0.4s, background 0.15s",
                    transitionDelay: mounted ? `${Math.min(i * 10, 800)}ms` : "0ms",
                    borderLeft: `2px solid ${pos.portfolioColor}${isHov ? "99" : "10"}`,
                    animation: isGlitch
                      ? "matrixGlitch 0.1s ease"
                      : isAnomaly
                      ? "matrixAnomalyPulse 0.8s ease infinite"
                      : "none",
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

                  {/* Reticles */}
                  <div className="matrix-ret" style={{ position: "absolute", inset: 0, opacity: isHov ? 1 : 0, transition: "opacity 0.12s", pointerEvents: "none" }}>
                    <Reticle color="#4ade80" s={5} />
                  </div>

                  {/* Anomaly indicator */}
                  {isAnomaly && (
                    <div style={{ position: "absolute", top: 2, right: 3, fontSize: 6, color: "#f87171", textShadow: "0 0 4px rgba(248,113,113,0.5)" }}>&#9888;</div>
                  )}

                  {/* Value bar */}
                  <div style={{
                    position: "absolute", bottom: 0, left: 0,
                    width: `${barW}%`, height: isHov ? 2 : 1,
                    background: `linear-gradient(90deg,${pos.portfolioColor}${isHov ? "55" : "12"},transparent)`,
                    transition: "all 0.15s",
                  }} />

                  {/* Ticker + all-time perf */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                    <span className="matrix-tk" style={{ fontSize: 10, fontWeight: 600, color: "#555", letterSpacing: "0.04em", transition: "all 0.12s" }}>
                      {pos.ticker}
                    </span>
                    <span style={{ fontSize: 8, fontWeight: 500, color: pc(pos.perf) }}>
                      {pos.perf > 0 ? "+" : ""}{pos.perf.toFixed(1)}
                    </span>
                  </div>

                  {/* Value + sparkline */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginTop: 2 }}>
                    <span style={{ fontSize: 7, color: "#292929" }}>{fv(pos.value)}</span>
                    <Sparkline data={pos.sparkline} color={pos.perf >= 0 ? "#4ade80" : "#f87171"} w={40} h={12} />
                  </div>

                  {/* Day change micro bar */}
                  <div style={{ marginTop: 3, height: 2 }}>
                    <div style={{
                      width: `${Math.min(100, Math.abs(pos.day) * 25)}%`,
                      height: "100%",
                      background: pos.day >= 0 ? "rgba(74,222,128,0.25)" : "rgba(248,113,113,0.25)",
                      transition: "width 0.3s",
                    }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* STATUS BAR */}
        <div style={{
          padding: "4px 20px",
          borderTop: "1px solid rgba(74,222,128,0.04)",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          fontSize: 7, color: "#1a1a1a", letterSpacing: "0.1em", flexShrink: 0,
        }}>
          <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
            {top && <span>&#9650; <span style={{ color: "#4ade80" }}>{top.ticker} +{top.perf.toFixed(1)}%</span></span>}
            {bot && <span>&#9660; <span style={{ color: "#f87171" }}>{bot.ticker} {bot.perf.toFixed(1)}%</span></span>}
            <span style={{ color: "#161616" }}>&#9474;</span>
            <span>KEYS: [1-4] SORT &middot; [ESC] RESET &middot; CLICK CELL FOR DETAIL</span>
          </div>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <Waveform width={100} height={12} />
            <span>MATRIX::v3.0</span>
            <span style={{ color: "#4ade8044", animation: "matrixBlink 2s step-end infinite" }}>&#9632; LIVE</span>
          </div>
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
              <div style={{ fontSize: 6, color: "#222", letterSpacing: "0.14em" }}>{s.l}</div>
              <div style={{ fontSize: 11, color: s.c ?? "#888", fontWeight: 500 }}>{s.v}</div>
            </div>
          ))}
          <div style={{ flex: 1, display: "flex", justifyContent: "flex-end" }}>
            <Sparkline data={hovered.sparkline} color={hovered.perf >= 0 ? "#4ade80" : "#f87171"} w={110} h={24} />
          </div>
        </div>
      )}

      {/* DETAIL CARD OVERLAY */}
      <DetailCard pos={selectedPos} onClose={() => setSelectedPos(null)} />
    </div>
  );
}
