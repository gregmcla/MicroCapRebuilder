/** Button — interactive action element.
 *  Variants:
 *    primary   — filled accent (default for CTAs)
 *    secondary — filled neutral surface
 *    ghost     — transparent, hover-on-surface (toolbars, tabs)
 *    outline   — bordered, transparent fill
 *    danger    — red treatment for destructive actions
 *  Sizes:
 *    sm — small (toolbar, modal actions)
 *    md — medium (form submit)
 *  Optional icon (left) or iconOnly for square button.
 *  @category Action
 */

import {
  forwardRef,
  type ButtonHTMLAttributes,
  type CSSProperties,
  type ReactNode,
} from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "outline" | "danger" | "success";
export type ButtonSize = "sm" | "md";

export interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "ref"> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Optional icon, rendered before children. Pass any ReactNode (SVG, text glyph). */
  icon?: ReactNode;
  /** When true, hides children and renders icon only. */
  iconOnly?: boolean;
  /** Stretches to fill its container (flex / full-width). */
  block?: boolean;
}

function sizeStyles(size: ButtonSize, iconOnly: boolean): CSSProperties {
  if (iconOnly) {
    return size === "md"
      ? { width: 32, height: 32, padding: 0 }
      : { width: 24, height: 24, padding: 0 };
  }
  return size === "md"
    ? { padding: "8px 14px", fontSize: "13px" }
    : { padding: "6px 12px", fontSize: "12px" };
}

function variantStyles(variant: ButtonVariant): { base: CSSProperties; hover: CSSProperties } {
  switch (variant) {
    case "primary":
      return {
        base: {
          background: "var(--color-accent)",
          color: "#fff",
          border: "1px solid var(--color-accent)",
        },
        hover: {
          background: "var(--color-accent-bright)",
          borderColor: "var(--color-accent-bright)",
        },
      };
    case "secondary":
      return {
        base: {
          background: "var(--surface-2)",
          color: "var(--color-text-2)",
          border: "1px solid var(--color-border-1)",
        },
        hover: {
          background: "var(--surface-3)",
          color: "var(--color-text-3)",
        },
      };
    case "ghost":
      return {
        base: {
          background: "transparent",
          color: "var(--color-text-2)",
          border: "1px solid transparent",
        },
        hover: {
          background: "rgba(255,255,255,0.05)",
          color: "var(--color-text-3)",
        },
      };
    case "outline":
      return {
        base: {
          background: "transparent",
          color: "var(--color-text-2)",
          border: "1px solid var(--color-border-1)",
        },
        hover: {
          background: "rgba(255,255,255,0.04)",
          color: "var(--color-text-3)",
          borderColor: "var(--color-border-hover)",
        },
      };
    case "danger":
      return {
        base: {
          background: "rgba(248,113,113,0.10)",
          color: "rgba(248,113,113,0.90)",
          border: "1px solid rgba(248,113,113,0.35)",
        },
        hover: {
          background: "rgba(248,113,113,0.18)",
          borderColor: "rgba(248,113,113,0.55)",
        },
      };
    case "success":
      return {
        base: {
          background: "rgba(74,222,128,0.10)",
          color: "rgba(74,222,128,0.90)",
          border: "1px solid rgba(74,222,128,0.35)",
        },
        hover: {
          background: "rgba(74,222,128,0.18)",
          borderColor: "rgba(74,222,128,0.55)",
        },
      };
  }
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "primary",
    size = "sm",
    icon,
    iconOnly = false,
    block = false,
    className,
    style,
    children,
    disabled,
    ...rest
  },
  ref,
) {
  const v = variantStyles(variant);
  const s = sizeStyles(size, iconOnly);
  const base: CSSProperties = {
    ...s,
    ...v.base,
    fontWeight: 600,
    borderRadius: "6px",
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.4 : 1,
    transition: "background 120ms, color 120ms, border-color 120ms",
    display: iconOnly ? "inline-flex" : "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: iconOnly ? 0 : 6,
    width: block ? "100%" : undefined,
    whiteSpace: "nowrap",
    letterSpacing: "0.01em",
  };

  return (
    <button
      ref={ref}
      className={className}
      style={{ ...base, ...style }}
      disabled={disabled}
      onMouseEnter={(e) => {
        if (disabled) return;
        Object.assign(e.currentTarget.style, v.hover);
      }}
      onMouseLeave={(e) => {
        if (disabled) return;
        Object.assign(e.currentTarget.style, v.base);
      }}
      {...rest}
    >
      {icon}
      {!iconOnly && children}
    </button>
  );
});

export default Button;
