import { useState } from "react";
import { Tabs, type TabItem } from "dashboard";

const stage = {
  padding: 16,
  background: "var(--color-bg-elevated, #141416)",
  borderRadius: 8,
  minWidth: 480,
};

const FOCUS_TABS: ReadonlyArray<TabItem<"actions" | "risk" | "performance" | "report">> = [
  { key: "actions", label: "Actions" },
  { key: "risk", label: "Risk" },
  { key: "performance", label: "Performance" },
  { key: "report", label: "Report" },
];

/** FocusPane vocabulary — the canonical right-rail tab strip. */
export function FocusPane() {
  const [active, setActive] = useState<"actions" | "risk" | "performance" | "report">("actions");
  return (
    <div style={stage}>
      <Tabs items={FOCUS_TABS} value={active} onChange={setActive} />
      <div style={{ padding: 16, fontSize: 12, color: "var(--color-text-secondary)" }}>
        Active tab body: <code>{active}</code>
      </div>
    </div>
  );
}

const BRIEF_TABS: ReadonlyArray<TabItem<"thesis" | "trades" | "factors" | "audit">> = [
  { key: "thesis", label: "Thesis" },
  { key: "trades", label: "Trades" },
  { key: "factors", label: "Factors" },
  { key: "audit", label: "Audit" },
];

/** Intelligence-brief vocabulary — same primitive, different keys. */
export function IntelligenceBrief() {
  const [active, setActive] = useState<"thesis" | "trades" | "factors" | "audit">("thesis");
  return (
    <div style={stage}>
      <Tabs items={BRIEF_TABS} value={active} onChange={setActive} />
    </div>
  );
}

/** Disabled-tab demonstration. */
export function WithDisabled() {
  const [active, setActive] = useState<"a" | "b" | "c">("a");
  const items: ReadonlyArray<TabItem<"a" | "b" | "c">> = [
    { key: "a", label: "Available" },
    { key: "b", label: "Loading…", disabled: true },
    { key: "c", label: "Locked", disabled: true },
  ];
  return (
    <div style={stage}>
      <Tabs items={items} value={active} onChange={setActive} />
    </div>
  );
}
