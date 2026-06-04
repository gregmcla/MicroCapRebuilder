import type { DigestNarrative, CrossPortfolioMover } from "../../lib/types";

function MoversBlock({ top, bottom }: { top: CrossPortfolioMover[]; bottom: CrossPortfolioMover[] }) {
  if (top.length === 0 && bottom.length === 0) return null;
  const Row = ({ m, positive }: { m: CrossPortfolioMover; positive: boolean }) => {
    const pct = m.day_change_pct ?? m.pnl_pct;
    return (
      <div className="mrow">
        <span className="mtk mono">{m.ticker}</span>
        <span className="mpf">{m.portfolio_name}</span>
        <span className={`mpct mono ${positive ? "grn" : "red"}`}>{pct >= 0 ? "+" : ""}{pct.toFixed(1)}%</span>
      </div>
    );
  };
  return (
    <div className="movers">
      {top.length > 0 && <>
        <div className="mhdr grn">Top Movers</div>
        {top.slice(0, 5).map((m) => <Row key={`t-${m.ticker}:${m.portfolio_id}`} m={m} positive />)}
      </>}
      {bottom.length > 0 && <>
        <div className="mhdr red">Bottom Movers</div>
        {bottom.slice(0, 5).map((m) => <Row key={`b-${m.ticker}:${m.portfolio_id}`} m={m} positive={false} />)}
      </>}
    </div>
  );
}

export default function GScottRead({ n, onRefresh, refreshing, topMovers = [], bottomMovers = [] }: { n?: DigestNarrative; onRefresh: () => void; refreshing: boolean; topMovers?: CrossPortfolioMover[]; bottomMovers?: CrossPortfolioMover[] }) {
  if (!n) return <div className="reg"><div className="lbl">GScott's read</div><div className="nar skeleton" style={{ height: 220 }} /></div>;
  return (
    <div className="reg">
      <div className="lbl">GScott's read</div>
      <div className="nar">
        <div className="head">
          <div className="ava">G</div>
          <div><div className="who">GScott</div><div className="sub">Daily intelligence · the whole book, in plain English</div></div>
          <div className="live">
            {n.generated_at && <span>Updated {new Date(n.generated_at).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</span>}
            <button className="narrefresh" onClick={onRefresh} disabled={refreshing} aria-label="Refresh GScott's read" title="Regenerate read">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={refreshing ? "spin" : ""}><path d="M23 4v6h-6"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
            </button>
          </div>
        </div>
        <div className="body">
          <div className="main">
            <div className="thesis">{n.thesis}</div>
            <p>{n.body}</p>
            {n.callout && <div className="callout"><div className="cdot" /><div className="ctx">{n.callout}</div></div>}
          </div>
          <div className="vr" />
          <div className="rail">
            <div className="posture">{n.posture_label}</div>
            <div className="gauge">
              <div className="grow"><span>Defensive</span><span>Neutral</span><span>Aggressive</span></div>
              <div className="gtrack"><div className="gthumb" style={{ left: `${Math.round(n.posture * 100)}%` }} /></div>
            </div>
            <div className="tag"><div className="meta"><div className="h">Working</div><div className="v grn">{n.working.join(" · ")}</div></div></div>
            <div className="tag"><div className="meta"><div className="h">Watching</div><div className="v red">{n.watching.join(" · ")}</div></div></div>
            <MoversBlock top={topMovers} bottom={bottomMovers} />
          </div>
        </div>
      </div>
    </div>
  );
}
