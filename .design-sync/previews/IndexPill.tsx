import { IndexPill } from "dashboard";

const stripWrap = {
  display: "flex",
  alignItems: "center",
  padding: "12px 0",
  background: "var(--color-bg-elevated, #141416)",
  borderRadius: 8,
};

/** The three indices as they appear in the live TopBar: S&P, RUT, VIX. */
export function MarketStrip() {
  return (
    <div style={stripWrap}>
      <IndexPill label="S&amp;P" value={5942.18} changePct={0.42} />
      <IndexPill label="RUT" value={2118.04} changePct={-0.61} />
      <IndexPill label="VIX" value={16.42} changePct={2.18} isVix />
    </div>
  );
}

/** Bullish — green percent, value in light text. */
export function Up() {
  return (
    <div style={stripWrap}>
      <IndexPill label="S&amp;P" value={5942.18} changePct={1.24} />
    </div>
  );
}

/** Bearish — red percent. */
export function Down() {
  return (
    <div style={stripWrap}>
      <IndexPill label="QQQ" value={508.91} changePct={-1.83} />
    </div>
  );
}

/** VIX rising — fear gauge invert: red on the way up (bad), amber label. */
export function VixRising() {
  return (
    <div style={stripWrap}>
      <IndexPill label="VIX" value={24.7} changePct={5.4} isVix />
    </div>
  );
}

/** VIX falling — fear easing: green on the way down (good), amber label. */
export function VixEasing() {
  return (
    <div style={stripWrap}>
      <IndexPill label="VIX" value={13.1} changePct={-3.8} isVix />
    </div>
  );
}
