import { useState } from "react";
import type React from "react";
import { useQueryClient } from "@tanstack/react-query";
import "./digest.css";
import { useDigest, useDigestNarrative } from "../../hooks/useDigest";
import { usePortfolioStore } from "../../lib/store";
import { api } from "../../lib/api";
import BookHero from "./BookHero";
import GScottRead from "./GScottRead";
import PortfolioCompare from "./PortfolioCompare";
import SinceYesterdayStrip from "./SinceYesterdayStrip";
import OverviewPage from "../OverviewPage";
import DigestActions from "./DigestActions";

const keyAct = (fn: () => void) => (e: React.KeyboardEvent) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fn(); }
};

export default function DailyDigest() {
  const [range, setRange] = useState("3M");
  const [gridView, setGridView] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio);
  const qc = useQueryClient();
  const { data, isLoading } = useDigest(range);
  const { data: narrative } = useDigestNarrative(range);

  const refreshRead = async () => {
    setRefreshing(true);
    try {
      const fresh = await api.getDigestNarrative(range, true);
      qc.setQueryData(["digest-narrative", range], fresh);
    } catch (e) { console.error("refresh read failed", e); }
    finally { setRefreshing(false); }
  };

  if (gridView) {
    return (
      <div className="digest">
        <div className="reg" style={{ borderBottom: "none" }}>
          <div className="gridtoggle" onClick={() => setGridView(false)}
            role="button" tabIndex={0} onKeyDown={keyAct(() => setGridView(false))}>&#9666; Back to Digest</div>
        </div>
        <OverviewPage />
      </div>
    );
  }
  if (isLoading || !data) return <div className="digest"><div className="reg skeleton" style={{ height: 600 }} /></div>;

  return (
    <div className="digest">
      <DigestActions />
      <div className="aurora" />
      <BookHero data={data.book} range={range} onRange={setRange} />
      <GScottRead n={narrative} onRefresh={refreshRead} refreshing={refreshing} />
      <PortfolioCompare rows={data.portfolios.filter(p => !p.error)} onGrid={() => setGridView(true)} onSelect={setPortfolio} />
      <SinceYesterdayStrip recap={data.recap} />
    </div>
  );
}
