/** Wraps a numeric readout and briefly flashes green/red when `value` changes —
 *  the live-ticker cue. Layout-stable (negative-margin padding), and the flash
 *  is reduced-motion-safe (see .flash-up / .flash-down in index.css). */

import type { CSSProperties, ReactNode } from "react";
import { useValueFlash } from "../../hooks/useValueFlash";

export function FlashValue({
  value,
  children,
  style,
  className,
  title,
}: {
  value: number;
  children: ReactNode;
  style?: CSSProperties;
  className?: string;
  title?: string;
}) {
  const { dir, nonce } = useValueFlash(value);
  const flashClass = dir ? `flash-${dir}` : "";
  return (
    <span
      // Re-mount on each change so the CSS animation replays even when the
      // direction repeats (up → up).
      key={nonce}
      className={[flashClass, className].filter(Boolean).join(" ") || undefined}
      title={title}
      style={{ borderRadius: "3px", padding: "0 3px", margin: "0 -3px", ...style }}
    >
      {children}
    </span>
  );
}
