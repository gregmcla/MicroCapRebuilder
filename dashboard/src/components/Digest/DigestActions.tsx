/** DigestActions — sticky action bar for the Daily Digest home (Update All / Scan All / Analyze All / + New). */

import { usePortfolioActions } from "../../hooks/usePortfolioActions";
import CreatePortfolioModal from "../CreatePortfolioModal";

export default function DigestActions() {
  const a = usePortfolioActions();

  return (
    <div className="digest-actions">
      <button className="dbtn" onClick={a.updateAll} disabled={a.updatingAll}>
        {a.updatingAll ? (a.updateLabel ?? "Updating…") : (a.updateLabel ?? "Update All")}
      </button>
      <button className="dbtn" onClick={a.scanAll} disabled={a.scanRunning}>
        {a.scanRunning ? `Scanning ${a.scanLabel ?? ""}`.trim() : (a.scanLabel ?? "Scan All")}
      </button>
      <button className="dbtn" onClick={a.analyzeAll} disabled={a.analyzeRunning}>
        {a.analyzeRunning
          ? `Analyzing ${a.analyzeLabel ?? ""}`.trim()
          : (a.analyzeLabel ?? "Analyze All")}
      </button>
      <button className="dbtn primary" onClick={() => a.setShowCreate(true)}>
        + New
      </button>
      {a.showCreate && (
        <CreatePortfolioModal onClose={() => a.setShowCreate(false)} />
      )}
    </div>
  );
}
