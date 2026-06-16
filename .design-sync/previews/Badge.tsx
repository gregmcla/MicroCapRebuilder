import { Badge, HeatBadge, RegimeBadge, AiDrivenBadge } from "dashboard";

const stage = {
  display: "flex",
  flexWrap: "wrap" as const,
  alignItems: "center",
  gap: 8,
  padding: 16,
  background: "var(--color-bg-elevated, #141416)",
  borderRadius: 8,
};

/** All 6 tones, soft variant (default). */
export function Tones() {
  return (
    <div style={stage}>
      <Badge tone="profit">PROFIT</Badge>
      <Badge tone="loss">LOSS</Badge>
      <Badge tone="warning">WARNING</Badge>
      <Badge tone="accent">ACCENT</Badge>
      <Badge tone="info">INFO</Badge>
      <Badge tone="neutral">NEUTRAL</Badge>
    </div>
  );
}

/** Variants of the same tone — filled, soft, outline. */
export function Variants() {
  return (
    <div style={stage}>
      <Badge tone="accent" variant="filled">FILLED</Badge>
      <Badge tone="accent" variant="soft">SOFT</Badge>
      <Badge tone="accent" variant="outline">OUTLINE</Badge>
    </div>
  );
}

/** Sizes — xs (default) and sm. */
export function Sizes() {
  return (
    <div style={stage}>
      <Badge tone="profit" size="xs">XS</Badge>
      <Badge tone="profit" size="sm">SM</Badge>
    </div>
  );
}

/** HeatBadge — watchlist social heat. SPIKING gets a pulse. */
export function Heat() {
  return (
    <div style={stage}>
      <HeatBadge heat="WARM" />
      <HeatBadge heat="HOT" />
      <HeatBadge heat="SPIKING" />
      {/* COLD renders nothing — verifies null guard. */}
      <HeatBadge heat="COLD" />
    </div>
  );
}

/** RegimeBadge — market regime BULL/BEAR/SIDEWAYS. */
export function Regime() {
  return (
    <div style={stage}>
      <RegimeBadge regime="BULL" />
      <RegimeBadge regime="BEAR" />
      <RegimeBadge regime="SIDEWAYS" />
    </div>
  );
}

/** AiDrivenBadge — single-use brand pill. */
export function AiDriven() {
  return (
    <div style={stage}>
      <AiDrivenBadge />
      <AiDrivenBadge size="sm" />
    </div>
  );
}
