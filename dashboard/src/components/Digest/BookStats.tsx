import type { OverviewData } from "../../lib/types";

const usd = (n: number) => "$" + Math.round(n).toLocaleString();
const signedUsd = (n: number) => (n >= 0 ? "+" : "−") + "$" + Math.round(Math.abs(n)).toLocaleString();
const pct = (n: number) => (n >= 0 ? "+" : "") + n.toFixed(1) + "%";
const sc = (n: number) => (n > 0 ? "grn" : n < 0 ? "red" : "");

/**
 * Aggregate totals across all active portfolios, shown beneath BookHero on the
 * digest home. BookHero covers "today" (equity + day P&L); this covers the
 * all-time / capital picture. Fed by the overview endpoint (active-only totals),
 * so it stays consistent with BookHero's "N active" count.
 */
export default function BookStats({ ov }: { ov?: OverviewData }) {
  if (!ov) return null;
  const equity = ov.total_equity ?? 0;
  const cash = ov.total_cash ?? 0;
  const deployed = Math.max(0, equity - cash);
  const startingCapital = ov.total_starting_capital ?? 0;
  const allTime = ov.total_all_time_pnl ?? 0;
  const ret = ov.total_return_pct ?? 0;
  const positions = ov.total_positions ?? 0;

  const stats: { k: string; v: string; c?: string }[] = [
    { k: "Total Equity", v: usd(equity) },
    { k: "Starting Capital", v: usd(startingCapital) },
    { k: "All-Time P&L", v: signedUsd(allTime), c: sc(allTime) },
    { k: "Return", v: pct(ret), c: sc(ret) },
    { k: "Deployed", v: usd(deployed) },
    { k: "Cash", v: usd(cash) },
    { k: "Positions", v: String(positions) },
  ];

  return (
    <div className="reg bookstats">
      <div className="lbl">All Portfolios</div>
      <div className="row">
        {stats.map((s) => (
          <div className="chip" key={s.k}>
            <div className="k">{s.k}</div>
            <div className={`v mono ${s.c ?? ""}`}>{s.v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
