# design-sync — repo notes for MicroCapRebuilder

## Why this repo is off-script-ish

The dashboard at `dashboard/` is a **private Vite app**, not a published component
library. There's no library `dist/`, no `module` field, and screen-level
components are tightly bound to live state (Zustand store + React Query +
the local FastAPI). The /design-sync converter expects a published library
shape — we work around that by:

- Authoring a tiny "library entry" at `dashboard/src/design-system/index.tsx`
  that re-exports only the **4 truly standalone** visuals (`GScottLogo`,
  `GScottAvatar`, `VDivider`, `IndexPill`).
- Pinning each via `cfg.componentSrcMap` so component discovery doesn't need
  a real `.d.ts` ship.
- Pointing `cfg.cssEntry` at the Vite-compiled stylesheet (Tailwind v4
  utilities + the `@theme` tokens) — NOT at `src/index.css`, which starts
  with `@import "tailwindcss"` and won't resolve once shipped.

## Re-sync steps (mandatory before running the converter)

1. `cd dashboard && npx vite build`
   (Skip `npm run build` — the dashboard has pre-existing TS errors that block
   `tsc -b`. Vite's bundle is correct without typecheck.)
2. `cp dashboard/dist/assets/index-*.css dashboard/dist/styles.css`
   (Stable filename so `cfg.cssEntry` doesn't track the hash.)
3. Then run the converter from the repo root as described in the skill.

## What is NOT synced (deliberate)

Everything under `dashboard/src/components/` that isn't in the 4-component
list above. Reason: each one imports from `lib/store` (Zustand) or
`lib/api` / `@tanstack/react-query` hooks (live API) and won't render in
isolation. A future "Plan B" pass would extract real primitives
(`Button`, `Card`, `Modal`, `Badge`) from the inlined usage in
`TopBar.tsx` / `PositionsPanel.tsx` etc. before syncing them.

## Tokens come from `dashboard/src/index.css`

The `@theme { ... }` block at the top of `dashboard/src/index.css` is the
authoritative token source. The compiled CSS we ship has those baked in
as `:root` custom properties. If you add a token there, rebuild Vite
before re-syncing (step 1 above).

## Fonts

DM Sans + JetBrains Mono + Azeret Mono are loaded from Google Fonts in
`dashboard/index.html`. The synced `styles.css` `@import`s the same URLs so
the design agent gets the same typography out of the box. No font files
are bundled.

## Modal primitive — outlier modals NOT migrated (Phase 1)

`dashboard/src/components/ui/Modal.tsx` covers the 3 shared shells —
**BuyModal**, **SellModal** (default variant), and **CompanyInfoModal**
(glass variant). Two outliers were left inlined because their shells are
intentionally different designs, not duplicates:

- **CreatePortfolioModal** — wizard shell: `surface-0` background (darker
  than `surface-1`), fixed 520px width with `90vh` max + scroll,
  `×` close (no ESC chip), and notably **no escape-to-close** today.
  Looks like its own "wizard" variant. Migrating would either dilute the
  Modal primitive or change visual behavior. Leave alone until there's a
  second wizard-style modal worth abstracting.
- **PortfolioSettingsModal** — settings-drawer shell: `bg-elevated`
  background, fixed 600px, bordered header strip (`padding 14px 18px` +
  `border-bottom`), `×` close. Distinct enough it deserves its own
  variant if a second settings modal ever ships.

If Greg later wants escape-to-close added to CreatePortfolioModal, that
is a separate UX decision, not a refactor.

## Re-sync risks

- **CSS hash drift.** `dashboard/dist/assets/index-<hash>.css` changes every
  build. The `cp ... dist/styles.css` step in "Re-sync steps" is what
  stabilizes the path — skip it and `[CSS_IMPORT_MISSING]` will fire.
- **Pre-existing TS errors in dashboard/.** Block `npm run build`. If they
  ever get fixed, you can switch the re-sync workflow back to `npm run build`.
  Until then, `vite build` only.
- **Inlined originals of `VDivider` and `IndexPill`.** They still exist
  inside `dashboard/src/components/TopBar.tsx`. If TopBar's copies drift
  from the design-system copies, the synced version is the authoritative
  one — fix the divergence by importing from `src/design-system/` in TopBar
  (or live with two copies; the dashboard hasn't broken).
- **Plan B is the follow-up.** Until primitives (`Button`, `Card`, etc.) are
  extracted from inlined usage, the synced surface stays at 4 components.
