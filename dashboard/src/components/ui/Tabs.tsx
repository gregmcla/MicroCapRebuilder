/** Tabs — horizontal tab strip with active-underline indicator.
 *  Controlled via `value` + `onChange`. Generic over the tab key type.
 *  Used by FocusPane, IntelligenceBrief, and any context-switch layout.
 *  @category Layout
 */

import type { CSSProperties, ReactNode } from "react";

export interface TabItem<K extends string = string> {
  /** Stable key matched against `value`. */
  key: K;
  /** Visible label. Pass a node if you need a badge or count. */
  label: ReactNode;
  /** Optional disabled state. */
  disabled?: boolean;
}

export interface TabsProps<K extends string = string> {
  /** Tabs to render. */
  items: ReadonlyArray<TabItem<K>>;
  /** Currently active tab key. */
  value: K;
  /** Called when a tab is clicked. */
  onChange: (key: K) => void;
  /** Override the underline + container styling. */
  className?: string;
  style?: CSSProperties;
}

const labelStyle: CSSProperties = {
  background: "none",
  border: "none",
  cursor: "pointer",
  fontWeight: 500,
  transition: "color 120ms",
};

export function Tabs<K extends string = string>({
  items,
  value,
  onChange,
  className,
  style,
}: TabsProps<K>) {
  return (
    <div
      className={["flex items-center shrink-0 border-b", className].filter(Boolean).join(" ")}
      style={{ borderColor: "var(--color-border)", ...style }}
      role="tablist"
    >
      {items.map((it) => {
        const active = it.key === value;
        return (
          <button
            key={it.key}
            onClick={() => !it.disabled && onChange(it.key)}
            disabled={it.disabled}
            role="tab"
            aria-selected={active}
            className="px-4 py-2.5 text-xs transition-colors relative"
            style={{
              ...labelStyle,
              color: active ? "var(--color-accent-bright)" : "var(--color-text-secondary)",
              opacity: it.disabled ? 0.4 : 1,
              cursor: it.disabled ? "not-allowed" : "pointer",
            }}
            onMouseEnter={(e) => {
              if (!active && !it.disabled) {
                e.currentTarget.style.color = "var(--color-text-2)";
              }
            }}
            onMouseLeave={(e) => {
              if (!active && !it.disabled) {
                e.currentTarget.style.color = "var(--color-text-secondary)";
              }
            }}
          >
            {it.label}
            {active && (
              <span
                className="absolute bottom-0 left-0 right-0 h-[2px]"
                style={{ background: "var(--color-accent)" }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}

export default Tabs;
