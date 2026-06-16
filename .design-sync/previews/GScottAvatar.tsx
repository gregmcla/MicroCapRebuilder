import { GScottAvatar } from "dashboard";

const stage = {
  display: "flex",
  alignItems: "center",
  gap: 24,
  padding: 32,
  background: "var(--color-bg-primary, #0a0a0b)",
  borderRadius: 8,
};

/** Default — chat-strip size with breathing violet glow. */
export function Default() {
  return (
    <div style={stage}>
      <GScottAvatar />
    </div>
  );
}

/** Three sizes side-by-side — see how the glow scales. */
export function Sizes() {
  return (
    <div style={stage}>
      <GScottAvatar size={32} />
      <GScottAvatar size={64} />
      <GScottAvatar size={128} />
    </div>
  );
}
