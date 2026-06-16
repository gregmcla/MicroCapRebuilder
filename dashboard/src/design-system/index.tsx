/** GScott design system — public surface for sync to claude.ai/design.
 *  Re-exports the foundational visual primitives. Screen-level components in
 *  dashboard/src/components/ are intentionally NOT exported: they bind to
 *  live data (Zustand store, React Query, the API).
 */
export { default as GScottLogo } from "../components/GScottLogo";
export { default as GScottAvatar } from "../components/GScottAvatar";
export { VDivider } from "./VDivider";
export { IndexPill, type IndexPillProps } from "./IndexPill";

// Plan B primitives — extracted from inlined usage across the dashboard.
export { Modal, ModalHeader, ModalBody, ModalFooter } from "../components/ui/Modal";
export type {
  ModalProps,
  ModalVariant,
  ModalHeaderProps,
  ModalBodyProps,
  ModalFooterProps,
} from "../components/ui/Modal";

export { Button } from "../components/ui/Button";
export type { ButtonProps, ButtonVariant, ButtonSize } from "../components/ui/Button";

export {
  Badge,
  HeatBadge,
  RegimeBadge,
  SourceBadge,
  AiDrivenBadge,
} from "../components/ui/Badge";
export type {
  BadgeProps,
  BadgeTone,
  BadgeVariant,
  BadgeSize,
  HeatBadgeProps,
  RegimeBadgeProps,
  SourceBadgeProps,
} from "../components/ui/Badge";
