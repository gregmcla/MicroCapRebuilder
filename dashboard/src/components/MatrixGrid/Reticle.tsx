interface ReticleProps {
  color?: string;
  s?: number;
}

export default function Reticle({ color = "#22C55E", s = 7 }: ReticleProps) {
  const b = `1px solid ${color}55`;
  return (
    <>
      <div style={{ position: "absolute", top: 0, left: 0, width: s, height: s, borderTop: b, borderLeft: b }} />
      <div style={{ position: "absolute", top: 0, right: 0, width: s, height: s, borderTop: b, borderRight: b }} />
      <div style={{ position: "absolute", bottom: 0, left: 0, width: s, height: s, borderBottom: b, borderLeft: b }} />
      <div style={{ position: "absolute", bottom: 0, right: 0, width: s, height: s, borderBottom: b, borderRight: b }} />
    </>
  );
}
