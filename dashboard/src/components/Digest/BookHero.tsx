import type React from "react";
import type { DigestData } from "../../lib/types";

const fmt$ = (n: number) => "$" + Math.round(n).toLocaleString();
const RANGES = ["1W", "1M", "3M", "YTD", "ALL"] as const;
const keyAct = (fn: () => void) => (e: React.KeyboardEvent) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fn(); }
};

export default function BookHero({ data, range, onRange }:
  { data: DigestData["book"]; range: string; onRange: (r: string) => void }) {
  const { book, spy } = data.curve;
  const pts = (arr: number[]) => {
    if (arr.length < 2) return "";
    const max = Math.max(...arr), min = Math.min(...arr), span = max - min || 1;
    return arr.map((v, i) =>
      `${(i / (arr.length - 1)) * 600},${118 - ((v - min) / span) * 92 - 13}`).join(" ");
  };
  const up = data.day_pnl >= 0;
  return (
    <div className="reg r1">
      <div className="left">
        <div className="lbl">Total Book · {data.health.green + data.health.red} active</div>
        <div className="big mono">{fmt$(data.equity)}</div>
        <div className={`day ${up ? "grn" : "red"}`}>
          <span className="mono">{up ? "+" : ""}{fmt$(data.day_pnl)}</span>
          <span className="t1">·</span>
          <span className="mono">{up ? "+" : ""}{data.day_pnl_pct}%</span> <span className="t1">today</span>
        </div>
        <div className="chips">
          <div className="chip"><div className="k">Health</div>
            <div className="v"><span className="grn">{data.health.green}</span><span className="t0"> / </span><span className="red">{data.health.red}</span></div></div>
          <div className="chip"><div className="k">vs SPY · all-time</div>
            <div className={`v mono ${data.vs_spy_alltime_pct >= 0 ? "grn" : "red"}`}>{data.vs_spy_alltime_pct >= 0 ? "+" : ""}{data.vs_spy_alltime_pct}%</div></div>
          <div className="chip"><div className="k">vs SPY · today</div>
            <div className="v acc mono">{data.vs_spy_today_pct >= 0 ? "+" : ""}{data.vs_spy_today_pct}%</div></div>
        </div>
      </div>
      <div className="chartwrap">
        <div className="charttop">
          <div className="legend"><span><i style={{ background: "var(--green)" }} />You</span><span><i className="dashed" />SPY</span></div>
          <div className="ranges">{RANGES.map(r =>
            <span key={r} className={r === range ? "on" : ""} onClick={() => onRange(r)}
              role="button" tabIndex={0} onKeyDown={keyAct(() => onRange(r))}>{r}</span>)}</div>
        </div>
        <div className="chartbox">
          <div className="delta">▲ {up ? "+" : ""}{fmt$(data.day_pnl)}</div>
          <svg className="chart" viewBox="0 0 600 118" preserveAspectRatio="none">
            {spy.length >= 2 && <polyline points={pts(spy)} fill="none" stroke="rgba(255,255,255,.26)" strokeWidth="1.5" strokeDasharray="5 5" />}
            {book.length >= 2 && <polyline points={pts(book)} fill="none" stroke="var(--green)" strokeWidth="2.6" strokeLinejoin="round" strokeLinecap="round" className="curveline" />}
          </svg>
        </div>
      </div>
    </div>
  );
}
