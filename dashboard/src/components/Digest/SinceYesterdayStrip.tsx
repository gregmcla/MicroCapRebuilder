import type { DigestData } from "../../lib/types";

export default function SinceYesterdayStrip({ recap }: { recap: DigestData["recap"] }) {
  const swing = recap.swings.map(s => `${s.ticker} ${s.pct >= 0 ? "+" : ""}${s.pct}%`).join(" · ");
  return (
    <div className="reg" style={{ borderBottom: "none" }}>
      <div className="lbl">Since yesterday's close</div>
      <div className="tlrow">
        <div className="tlnode"><div className="dot"><span className="d-grn" /></div>
          <div className="h">{recap.buys.count} buys executed</div>
          <div className="d">Deployed ${Math.round(recap.buys.deployed).toLocaleString()}.</div></div>
        <div className="tlnode"><div className="dot"><span className="d-red" /></div>
          <div className="h">{recap.exits.count} exits</div>
          <div className="d">Stops & take-profits triggered.</div></div>
        <div className="tlnode"><div className="dot"><span className="d-acc" /></div>
          <div className="h">Biggest swings <span className="tm">live</span></div>
          <div className="d"><span className="mono">{swing}</span></div></div>
        <div className="tlnode"><div className="dot"><span className="d-out" /></div>
          <div className="h">Regime steady</div>
          <div className="d" title="Market regime and the strategy's current risk score (lower = more cautious)"><span className="acc">{recap.regime.label}</span>
            {recap.regime.risk > 0 && <> · risk <span className="mono">{recap.regime.risk}</span>{recap.regime.risk_prev > 0 && <>, down from <span className="mono">{recap.regime.risk_prev}</span></>}</>}</div></div>
      </div>
    </div>
  );
}
