/** Modal — shared shell for all GScott modals.
 *  Compound API: <Modal><Modal.Header/><Modal.Body/><Modal.Footer/></Modal>.
 *  Centralizes backdrop, click-outside-to-close, escape-to-close, and aria.
 *  @category Layout
 */

import { useEffect, type ReactNode, type CSSProperties } from "react";

export type ModalVariant = "default" | "glass";

export interface ModalProps {
  /** Called when user closes via backdrop click, escape, or the header close button. */
  onClose: () => void;
  /** Max width of the inner card. Default 400px. Pass any CSS value. */
  maxWidth?: number | string;
  /** Visual style. `default` = elevated surface; `glass` = blurred translucent (used by CompanyInfoModal). */
  variant?: ModalVariant;
  /** Disable backdrop-click-to-close. Default true. */
  closeOnBackdrop?: boolean;
  /** Disable escape-to-close. Default true. */
  closeOnEscape?: boolean;
  /** Optional aria-label for the dialog. */
  ariaLabel?: string;
  children: ReactNode;
}

const BACKDROP: CSSProperties = {
  background: "rgba(0,0,0,0.6)",
  backdropFilter: "blur(4px)",
};

const CARD_DEFAULT: CSSProperties = {
  background: "var(--surface-1)",
  border: "1px solid var(--border-2)",
  boxShadow: "0 24px 48px rgba(0,0,0,0.5)",
};

const CARD_GLASS: CSSProperties = {
  background: "rgba(18,18,28,0.92)",
  border: "1px solid rgba(255,255,255,0.10)",
  boxShadow: "0 24px 64px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.08)",
  backdropFilter: "blur(24px)",
};

export function Modal({
  onClose,
  maxWidth = 400,
  variant = "default",
  closeOnBackdrop = true,
  closeOnEscape = true,
  ariaLabel,
  children,
}: ModalProps) {
  useEffect(() => {
    if (!closeOnEscape) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, closeOnEscape]);

  const cardStyle: CSSProperties =
    variant === "glass" ? CARD_GLASS : CARD_DEFAULT;
  const cardRadius = variant === "glass" ? "rounded-2xl" : "rounded-xl";
  const cardPositioning = variant === "glass" ? "relative w-full mx-4" : "w-full";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={BACKDROP}
      onClick={closeOnBackdrop ? onClose : undefined}
      role="dialog"
      aria-modal="true"
      aria-label={ariaLabel}
    >
      <div
        className={`${cardRadius} p-5 ${cardPositioning}`}
        style={{ ...cardStyle, maxWidth }}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

export interface ModalHeaderProps {
  /** Render the close button. Pass the same onClose used by Modal. */
  onClose?: () => void;
  /** Close button style. `esc` = bordered ESC chip (default).
   *  `x` = round ✕ button (glass-variant convention).
   *  When the parent Modal uses `variant="glass"`, default flips to `x`. */
  closeStyle?: "esc" | "x";
  /** Custom className for the header row (defaults to `flex items-center justify-between mb-4`). */
  className?: string;
  /** Header content — usually the title plus any inline status (P&L, tags, etc.). */
  children: ReactNode;
}

export function ModalHeader({
  onClose,
  closeStyle = "esc",
  className = "flex items-center justify-between mb-4",
  children,
}: ModalHeaderProps) {
  return (
    <div className={className}>
      <div className="flex items-center gap-2 min-w-0">{children}</div>
      {onClose && (closeStyle === "x" ? <CloseX onClose={onClose} /> : <CloseEsc onClose={onClose} />)}
    </div>
  );
}

function CloseEsc({ onClose }: { onClose: () => void }) {
  return (
    <button
      onClick={onClose}
      className="text-xs rounded px-2 py-1 transition-colors"
      style={{ color: "var(--text-1)", border: "1px solid var(--border-1)" }}
      onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-3)"; }}
      onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-1)"; }}
      aria-label="Close"
    >
      ESC
    </button>
  );
}

function CloseX({ onClose }: { onClose: () => void }) {
  return (
    <button
      onClick={onClose}
      className="absolute top-4 right-4 text-xs rounded-full w-6 h-6 flex items-center justify-center transition-colors"
      style={{ color: "var(--text-1)", background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.08)" }}
      onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.12)"; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.06)"; }}
      aria-label="Close"
    >
      ✕
    </button>
  );
}

export interface ModalBodyProps {
  className?: string;
  style?: CSSProperties;
  children: ReactNode;
}

export function ModalBody({ className, style, children }: ModalBodyProps) {
  return (
    <div className={className} style={style}>
      {children}
    </div>
  );
}

export interface ModalFooterProps {
  className?: string;
  children: ReactNode;
}

export function ModalFooter({
  className = "flex items-center justify-end gap-2 mt-4",
  children,
}: ModalFooterProps) {
  return <div className={className}>{children}</div>;
}

Modal.Header = ModalHeader;
Modal.Body = ModalBody;
Modal.Footer = ModalFooter;

export default Modal;
