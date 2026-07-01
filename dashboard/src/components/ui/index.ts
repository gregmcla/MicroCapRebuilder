/** Reusable UI primitives for the GScott dashboard.
 *  Add new primitives here as they're extracted from inlined usage.
 */
export { Modal, ModalHeader, ModalBody, ModalFooter } from "./Modal";
export type {
  ModalProps,
  ModalVariant,
  ModalHeaderProps,
  ModalBodyProps,
  ModalFooterProps,
} from "./Modal";

export { Button } from "./Button";
export type { ButtonProps, ButtonVariant, ButtonSize } from "./Button";

export { Tabs } from "./Tabs";
export type { TabsProps, TabItem } from "./Tabs";

export { default as Toaster } from "./Toaster";

export { FlashValue } from "./FlashValue";

export { MilestoneBadge } from "./MilestoneBadge";

export { Badge, HeatBadge, RegimeBadge, SourceBadge, AiDrivenBadge } from "./Badge";
export type {
  BadgeProps,
  BadgeTone,
  BadgeVariant,
  BadgeSize,
  HeatBadgeProps,
  RegimeBadgeProps,
  SourceBadgeProps,
} from "./Badge";
