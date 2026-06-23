import { useState } from "react";
import type React from "react";
import type { DigestPortfolio } from "../../lib/types";

const keyAct = (fn: () => void) => (e: React.KeyboardEvent) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fn(); }
};

const SORTS = ["Working", "Today", "Equity", "vs SPY", "Name"] as const;
const fmtM = (n: number) => n >= 1e6 ? `$${(n / 1e6).toFixed(2)}M` : `$${Math.round(n / 1e3)}k`;
const sgn = (v: number) => (v >= 0 ? "+" : "") + v + "%";
// Compact signed dollars for the sub-line next to a % column.
const fmt$ = (n: number) => {
  const a = Math.abs(n), s = n >= 0 ? "+" : "-";
  if (a >= 1e6) return `${s}$${(a / 1e6).toFixed(2)}M`;
  if (a >= 1e3) return `${s}$${(a / 1e3).toFixed(1)}k`;
  return `${s}$${Math.round(a)}`;
};

function sparkPts(arr: number[]) {
  if (arr.length < 2) return "";
  const max = Math.max(...arr), min = Math.min(...arr), span = max - min || 1;
  return arr.map((v, i) => `${(i / (arr.length - 1)) * 84},${26 - ((v - min) / span) * 23 - 1}`).join(" ");
}

export default function PortfolioCompare({ rows, onGrid, onSelect }: { rows: DigestPortfolio[]; onGrid: () => void; onSelect: (id: string) => void }) {
  const [sort, setSort] = useState<string>("Working");
  const sorted = [...rows].sort((a, b) => {
    switch (sort) {
      case "Today": return b.day_pct - a.day_pct;
      case "Equity": return b.equity - a.equity;
      case "vs SPY": return b.vs_bench_pct - a.vs_bench_pct;
      case "Name": return a.name.localeCompare(b.name);
      default: return b.vs_bench_pct - a.vs_bench_pct;
    }
  });
  const cls = (v: number) => (v >= 0 ? "grn" : "red");
  return (
    <div className="reg">
      <div className="r3head">
        <div className="sorts">{SORTS.map(s =>
          <span key={s} className={s === sort ? "on" : ""} onClick={() => setSort(s)}
            role="button" tabIndex={0} onKeyDown={keyAct(() => setSort(s))}>{s}</span>)}</div>
        <div className="gridtoggle" onClick={onGrid}
          role="button" tabIndex={0} onKeyDown={keyAct(onGrid)}>▦ Grid view</div>
      </div>
      <div className="colhdr"><div>#</div><div>Portfolio</div><div>Equity</div><div>Today</div><div>Total</div><div>vs Bench</div><div style={{ textAlign: "right" }}>30d</div><div>Trend</div></div>
      {sorted.map((p, i) => {
        const pill = p.trend === "ahead" ? "up" : p.trend === "fading" ? "dn" : "fl";
        const w = Math.min(44, Math.abs(p.vs_bench_pct));
        return (
          <div className={`prow ${i === 0 ? "leader" : ""}`} key={p.id}
            onClick={() => onSelect(p.id)}
            role="button"
            tabIndex={0}
            onKeyDown={keyAct(() => onSelect(p.id))}>
            <div className="rank">{String(i + 1).padStart(2, "0")}</div>
            <div><div className="pname">{p.name}</div><div className="pstrat">{p.strategy}</div></div>
            <div className="num mono">{fmtM(p.equity)}</div>
            <div className={`num ${cls(p.day_pct)}`}>{sgn(p.day_pct)}<span className="subusd">{fmt$(p.day_pnl)}</span>{(() => {
              const ah = p.extended_hours_pnl ?? 0;
              const showAh = (p.session_status === "after_hours" || p.session_status === "pre_market") && Math.abs(ah) >= 0.5;
              if (!showAh) return null;
              const lbl = p.session_status === "pre_market" ? "PRE" : "AH";
              return (
                <span className={`subusd ${cls(ah)}`} style={{ marginLeft: 4, opacity: 0.7 }} title={`Extended-hours (${lbl})`}>
                  ({ah >= 0 ? "+" : ""}{fmt$(ah)} {lbl})
                </span>
              );
            })()}</div>
            <div className={`num ${cls(p.total_pct)}`}>{sgn(p.total_pct)}<span className="subusd">{fmt$(p.all_time_pnl)}</span></div>
            <div className="vsbar"><span className={`num ${cls(p.vs_bench_pct)}`}>{sgn(p.vs_bench_pct)}</span>
              <span className="track"><span className="fill" style={p.vs_bench_pct >= 0
                ? { left: "50%", right: `${50 - w}%`, background: "var(--green)" }
                : { right: "50%", left: `${50 - w}%`, background: "var(--red)" }} /></span></div>
            <svg className="spark" viewBox="0 0 84 26"><polyline points={sparkPts(p.sparkline)} fill="none"
              stroke={p.trend === "fading" ? "var(--red)" : p.trend === "flat" ? "rgba(255,255,255,.4)" : "var(--green)"} strokeWidth="2" strokeLinecap="round" /></svg>
            <span className={`pill ${pill}`}>{p.trend}</span>
          </div>
        );
      })}
    </div>
  );
}
