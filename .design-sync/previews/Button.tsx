import { Button } from "dashboard";

const stage = {
  display: "flex",
  flexWrap: "wrap" as const,
  alignItems: "center",
  gap: 8,
  padding: 16,
  background: "var(--color-bg-elevated, #141416)",
  borderRadius: 8,
};

/** All 6 variants in default size. */
export function Variants() {
  return (
    <div style={stage}>
      <Button variant="primary">Primary</Button>
      <Button variant="secondary">Secondary</Button>
      <Button variant="ghost">Ghost</Button>
      <Button variant="outline">Outline</Button>
      <Button variant="danger">Danger</Button>
      <Button variant="success">Success</Button>
    </div>
  );
}

/** Sizes — sm (default) and md. */
export function Sizes() {
  return (
    <div style={stage}>
      <Button variant="primary" size="sm">Small</Button>
      <Button variant="primary" size="md">Medium</Button>
      <Button variant="secondary" size="sm">Small</Button>
      <Button variant="secondary" size="md">Medium</Button>
    </div>
  );
}

/** Disabled — opacity drop, no hover. */
export function Disabled() {
  return (
    <div style={stage}>
      <Button variant="primary" disabled>Primary</Button>
      <Button variant="danger" disabled>Danger</Button>
      <Button variant="success" disabled>Success</Button>
    </div>
  );
}

/** Block — fills container, side-by-side. */
export function Block() {
  return (
    <div style={{ ...stage, flexWrap: "nowrap", width: 360 }}>
      <Button variant="secondary" size="md" block>Cancel</Button>
      <Button variant="success" size="md" block>Confirm</Button>
    </div>
  );
}

/** Icon-only — square button. */
export function IconOnly() {
  return (
    <div style={stage}>
      <Button variant="ghost" iconOnly icon={<span>⚙</span>} aria-label="Settings" />
      <Button variant="outline" iconOnly icon={<span>↗</span>} aria-label="Open external" />
      <Button variant="danger" iconOnly icon={<span>✕</span>} aria-label="Close" />
    </div>
  );
}
