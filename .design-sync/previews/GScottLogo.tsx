import { GScottLogo } from "dashboard";

const stage = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: 32,
  background: "var(--color-bg-primary, #0a0a0b)",
  borderRadius: 8,
};

/** Default — TopBar height. */
export function Default() {
  return (
    <div style={stage}>
      <GScottLogo />
    </div>
  );
}

/** Large — landing or hero treatment. */
export function Hero() {
  return (
    <div style={stage}>
      <GScottLogo height={64} />
    </div>
  );
}

/** Replay key — pass animKey to re-trigger the typewriter (here: live). */
export function ReplayKey() {
  return (
    <div style={stage}>
      <GScottLogo height={48} animKey={1} />
    </div>
  );
}
