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
  const last = (a: number[]) => (a.length >= 2 ? a[a.length - 1] - 100 : 0);
  const bookRet = +last(book).toFixed(2);
  const spyRet = +last(spy).toFixed(2);
  const alpha = +(bookRet - spyRet).toFixed(2);
  const pct = (v: number) => (v >= 0 ? "+" : "") + v + "%";
  const sc = (v: number) => (v >= 0 ? "grn" : "red");
  const pts = (arr: number[]) => {
    if (arr.length < 2) return "";
    const max = Math.max(...arr), min = Math.min(...arr), span = max - min || 1;
    return arr.map((v, i) =>
      `${(i / (arr.length - 1)) * 600},${118 - ((v - min) / span) * 92 - 13}`).join(" ");
  };
  const up = data.day_pnl >= 0;
  const ahPnl = data.extended_hours_pnl ?? 0;
  const showAh = (data.session_status === "after_hours" || data.session_status === "pre_market") && Math.abs(ahPnl) >= 0.5;
  const ahLabel = data.session_status === "pre_market" ? "PRE" : "AH";
  const ahCls = ahPnl >= 0 ? "grn" : "red";
  return (
    <div className="reg r1">
      <div className="left">
        <div className="lbl">Total Book · {data.health.green + data.health.red} active</div>
        <div className="big mono">{fmt$(data.equity)}</div>
        <div className={`day ${up ? "grn" : "red"}`}>
          <span className="mono">{up ? "+" : ""}{fmt$(data.day_pnl)}</span>
          <span className="t1">·</span>
          <span className="mono">{up ? "+" : ""}{data.day_pnl_pct}%</span> <span className="t1">today</span>
          {showAh && (
            <span className={`mono t1 ${ahCls}`} style={{ marginLeft: 6, opacity: 0.75, fontSize: "0.85em" }} title={`Extended-hours (${ahLabel})`}>
              ({ahPnl >= 0 ? "+" : ""}{fmt$(ahPnl)} {ahLabel})
            </span>
          )}
        </div>
        <div className="chips">
          <div className="chip" title="Positions in the green vs in the red right now">
            <div className="k">Health</div>
            <div className="v"><span className="grn">{data.health.green}</span><span className="t0"> / </span><span className="red">{data.health.red}</span></div></div>
          <div className="chip" title="Your return today minus the S&P 500's return today (positive = outperforming)">
            <div className="k">vs SPY · today</div>
            <div className="v acc mono">{data.vs_spy_today_pct >= 0 ? "+" : ""}{data.vs_spy_today_pct}%</div></div>
        </div>
      </div>
      <div className="chartwrap">
        <div className="charttop">
          <div className="legend">
            <span><i style={{ background: "var(--green)" }} />You <b className={sc(bookRet)}>{pct(bookRet)}</b></span>
            <span><i className="dashed" />SPY <b className={sc(spyRet)}>{pct(spyRet)}</b></span>
            <span className="alpha">α <b className={sc(alpha)}>{pct(alpha)}</b></span>
          </div>
          <div className="ranges">{RANGES.map(r =>
            <span key={r} className={r === range ? "on" : ""} onClick={() => onRange(r)}
              role="button" tabIndex={0} onKeyDown={keyAct(() => onRange(r))}>{r}</span>)}</div>
        </div>
        <div className="chartbox">
          <div className="delta">{bookRet >= 0 ? "▲" : "▼"} {pct(bookRet)}</div>
          <svg className="chart" viewBox="0 0 600 118" preserveAspectRatio="none">
            {spy.length >= 2 && <polyline points={pts(spy)} fill="none" stroke="rgba(255,255,255,.26)" strokeWidth="1.5" strokeDasharray="5 5" />}
            {book.length >= 2 && <polyline points={pts(book)} fill="none" stroke="var(--green)" strokeWidth="2.6" strokeLinejoin="round" strokeLinecap="round" className="curveline" />}
          </svg>
        </div>
      </div>
    </div>
  );
}
