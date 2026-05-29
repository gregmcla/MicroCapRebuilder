import type { DigestNarrative } from "../../lib/types";

export default function GScottRead({ n, time }: { n?: DigestNarrative; time: string }) {
  if (!n) return <div className="reg"><div className="lbl">GScott's read</div><div className="nar skeleton" style={{ height: 220 }} /></div>;
  return (
    <div className="reg">
      <div className="lbl">GScott's read</div>
      <div className="nar">
        <div className="head">
          <div className="ava">G</div>
          <div><div className="who">GScott</div><div className="sub">Daily intelligence · the whole book, in plain English</div></div>
          <div className="live"><i />Live read · {time}</div>
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
          </div>
        </div>
      </div>
    </div>
  );
}
