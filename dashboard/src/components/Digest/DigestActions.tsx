/** DigestActions — sticky action bar for the Daily Digest home (Update All / Scan All / Analyze All / + New). */

import { usePortfolioActions } from "../../hooks/usePortfolioActions";
import CreatePortfolioModal from "../CreatePortfolioModal";

const VERB: Record<string, string> = { update: "Updating", scan: "Scanning", analyze: "Analyzing" };

export default function DigestActions() {
  const a = usePortfolioActions();
  const busy = !!a.status?.running;

  return (
    <div className="digest-actions">
      <div className="digest-status-wrap">
        {a.status && (
          a.status.running ? (
            <div className="digest-status running">
              <span className="dspin" />
              {VERB[a.status.kind]} {a.status.current ?? ""} · {Math.min(a.status.done + 1, a.status.total)}/{a.status.total}…
            </div>
          ) : a.status.error ? (
            <div className="digest-status err">⚠ {a.status.error}</div>
          ) : (
            <div className="digest-status done">✓ {a.status.summary}</div>
          )
        )}
      </div>
      <div className="digest-actions-btns">
        <button className="dbtn" onClick={a.updateAll} disabled={busy}>Update All</button>
        <button className="dbtn" onClick={a.scanAll} disabled={busy}>Scan All</button>
        <button className="dbtn" onClick={a.analyzeAll} disabled={busy}>Analyze All</button>
        <button className="dbtn primary" onClick={() => a.setShowCreate(true)}>+ New</button>
      </div>
      {a.showCreate && <CreatePortfolioModal onClose={() => a.setShowCreate(false)} />}
    </div>
  );
}
