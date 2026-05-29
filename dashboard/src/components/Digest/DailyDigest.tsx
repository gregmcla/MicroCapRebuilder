import { useState } from "react";
import "./digest.css";
import { useDigest, useDigestNarrative } from "../../hooks/useDigest";
import BookHero from "./BookHero";
import GScottRead from "./GScottRead";
import PortfolioCompare from "./PortfolioCompare";
import SinceYesterdayStrip from "./SinceYesterdayStrip";
import OverviewPage from "../OverviewPage";

export default function DailyDigest() {
  const [range, setRange] = useState("3M");
  const [gridView, setGridView] = useState(false);
  const { data, isLoading } = useDigest(range);
  const { data: narrative } = useDigestNarrative(range);
  const now = new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

  if (gridView) {
    return (
      <div className="digest">
        <div className="reg" style={{ borderBottom: "none" }}>
          <div className="gridtoggle" onClick={() => setGridView(false)}>&#9666; Back to Digest</div>
        </div>
        <OverviewPage />
      </div>
    );
  }
  if (isLoading || !data) return <div className="digest"><div className="reg skeleton" style={{ height: 600 }} /></div>;

  return (
    <div className="digest">
      <div className="aurora" />
      <BookHero data={data.book} range={range} onRange={setRange} />
      <GScottRead n={narrative} time={now} />
      <PortfolioCompare rows={data.portfolios.filter(p => !p.error)} onGrid={() => setGridView(true)} />
      <SinceYesterdayStrip recap={data.recap} />
    </div>
  );
}
