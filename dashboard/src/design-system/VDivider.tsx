/** 1px vertical separator at 24px tall. Used between sections of the TopBar.
 *  @category Layout
 */
export function VDivider() {
  return (
    <div
      style={{
        width: "1px",
        height: "24px",
        background: "var(--border-1)",
        flexShrink: 0,
        opacity: 0.5,
      }}
    />
  );
}

export default VDivider;
