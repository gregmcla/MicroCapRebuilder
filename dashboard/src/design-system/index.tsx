/** GScott design system — public surface for sync to claude.ai/design.
 *  Re-exports the four standalone visual primitives. The screen-level
 *  components in dashboard/src/components/ are intentionally NOT exported:
 *  they bind to live data (Zustand store, React Query, the API).
 */
export { default as GScottLogo } from "../components/GScottLogo";
export { default as GScottAvatar } from "../components/GScottAvatar";
export { VDivider } from "./VDivider";
export { IndexPill, type IndexPillProps } from "./IndexPill";
