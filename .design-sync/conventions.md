# GScott Design System

A dark-mode trading-cockpit design system. Built with Tailwind v4 and CSS
custom properties. Originated in the **GScott Terminal** dashboard
(`MicroCapRebuilder`), which is a multi-portfolio paper-trading
application. Use this system to build interfaces with the same monochrome
+ violet-accent feel — high information density, tabular numerics,
restrained motion.

## Setup

There is no root provider — the components are uncontextualized SVG /
markup that read CSS custom properties from their ancestor. Wrap any
screen you build in a container that sets the dark background and the
default text color, and import the shipped stylesheet at the document
root.

```html
<link rel="stylesheet" href="styles.css">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@300;400;500&display=swap" rel="stylesheet">
```

Fonts are **runtime-loaded** (DM Sans, JetBrains Mono — and Azeret Mono
for editorial typography). The shipped bundle does not include `.woff2`
files; include the Google Fonts `<link>` above in every design's head. If
you don't, components fall back to system sans/mono.

## Styling idiom: Tailwind v4 utilities + CSS variables

This DS uses Tailwind v4 utility classes for layout and CSS custom
properties for color, typography, and motion. Always reference colors
through tokens — never hardcode hex.

### Surfaces (dark, layered)

| Token | Use |
|---|---|
| `var(--color-bg-primary)` | Page background (`#0a0a0b` — near-black) |
| `var(--color-bg-surface)` | Card/panel base |
| `var(--color-bg-elevated)` | Elevated panel (headers, toolbars) |
| `var(--color-surface-2)` | Hover/focused panel |
| `var(--color-surface-3)` | Modal / overlay |
| `var(--color-surface-4)` | Highest layer (popovers) |

### Borders (rgba, opacity-based)

| Token | Use |
|---|---|
| `var(--color-border)`     | Default separators |
| `var(--border-1)`         | Subtle (used by `VDivider`) |
| `var(--color-border-hover)` | Hover-state border |
| `var(--border-3)`         | Strong emphasis border |

### Text (opacity-based on white)

| Token | Use |
|---|---|
| `var(--color-text-primary)`   | Primary copy (95% white) |
| `var(--color-text-2)`         | Standard data values (68%) |
| `var(--color-text-secondary)` | Labels, captions (48%) |
| `var(--color-text-muted)`     | De-emphasized (32%) |

### Accent — violet

| Token | Use |
|---|---|
| `var(--color-accent)`         | Primary accent (`#7c5cfc`) — CTAs, focus rings, selected state |
| `var(--color-accent-bright)`  | Active/hover variant |
| `var(--color-accent-dim)`     | Filled background (12% alpha) |
| `var(--color-accent-cyan)`    | Secondary accent (cyan-teal) |

### Semantic data colors

Use these for ANY financial readout — positive vs negative is
load-bearing in trading UI. Never substitute generic green/red.

| Token | Meaning |
|---|---|
| `var(--color-profit)` | Gains, up moves, healthy state |
| `var(--color-loss)`   | Losses, down moves, risk |
| `var(--color-warning)`| Amber: VIX, freshness/staleness, caution |

**VIX inversion idiom**: For VIX (fear gauge) specifically, sentiment
flips — a rising VIX is *bad*, falling is *good*. See `IndexPill` with
`isVix={true}` — label/value render in amber, percent-change color
inverts. Apply the same idiom to any "fear" indicator.

## Typography

- `var(--font-sans)` → DM Sans (UI labels, copy)
- `var(--font-mono)` → JetBrains Mono (data, code, ticker symbols)
- Numeric data ALWAYS uses `tabular-nums` so digits don't jitter when
  values update. Combine `font-mono tabular-nums` for any number that
  changes live (price, P&L, percent).
- Use `.font-data` as a shortcut for `font-family: var(--font-mono)`.

## Motion

The DS is restrained — no decorative animation. Three patterns:

- **Cascade in**: stagger nodes on mount with `class="anim d1"`,
  `class="anim d2"`, … through `d10` (30 ms steps). Use for list rows,
  card grids, brief reveal.
- **Pulse**: `.animate-pulse-slow` (data getting stale),
  `.animate-pulse-fast` (data critically stale), `.animate-live-pulse`
  (live update indicator).
- **Card hover**: `.card-hover` lifts by 1px, brightens border, gradient
  background. Apply to any clickable surface.

## Radius

- `var(--radius)` 8px — default cards/buttons
- `var(--radius-sm)` 6px — small chips
- `var(--radius-xs)` 4px — micro elements
- `var(--radius-lg)` / `var(--radius-xl)` / `var(--radius-2xl)` — modals,
  hero cards

## Where the truth lives

- **Tokens & utilities**: `styles.css` (transitively `@imports`
  `_ds_bundle.css`, which is the full compiled stylesheet of every
  `var(--*)` and every utility class).
- **Component API & usage**: per-component `<Name>.d.ts` (props) and
  `<Name>.prompt.md` (usage notes) inside `components/<group>/<Name>/`.
- **Working examples**: each component ships a preview `.html` rendered
  from a real authored example in `_preview/`. Use those as templates.

## Idiomatic snippet

A toolbar strip — the canonical GScott pattern: dark elevated band, mono
data, violet accent for action, semantic colors for P&L, dividers
between sections.

```jsx
<div className="flex items-center gap-4 px-4 py-2"
     style={{ background: "var(--color-bg-elevated)", borderRadius: "var(--radius)" }}>
  <GScottLogo height={28} />
  <VDivider />
  <div>
    <div style={{ fontSize: 9, textTransform: "uppercase",
                  color: "var(--color-text-muted)" }}>Equity</div>
    <div className="font-mono tabular-nums"
         style={{ fontSize: 14, color: "var(--color-text-primary)" }}>
      $142,318.04
    </div>
  </div>
  <VDivider />
  <IndexPill label="S&amp;P" value={5942.18} changePct={0.42} />
  <IndexPill label="VIX" value={16.42} changePct={2.18} isVix />
</div>
```

That snippet exercises every concern above: the elevated surface, the
violet brand via `GScottLogo`, the `VDivider` rhythm, mono+tabular for
numbers, semantic color in `IndexPill`, and the VIX inversion idiom.

## Interactive primitives — Modal, Button, Badge

These are the extracted-from-inlined-usage primitives. Always compose
with them instead of re-rolling a styled `<button>` or `<div>`.

### Modal

Default variant for action modals (buy/sell/confirm). Glass variant for
overlay info panels (company profile, ticker info). The Modal owns
backdrop, click-outside-to-close, escape-to-close, and the dialog aria.

```jsx
<Modal onClose={close} maxWidth={400} ariaLabel="Buy AAPL">
  <Modal.Header onClose={close}>
    <span className="font-mono font-bold" style={{ fontSize: 18 }}>
      Buy AAPL
    </span>
  </Modal.Header>
  <Modal.Body>{/* form, copy, etc. */}</Modal.Body>
  <Modal.Footer>
    <Button variant="secondary" size="md" onClick={close}>Cancel</Button>
    <Button variant="success" size="md" onClick={confirm}>Confirm</Button>
  </Modal.Footer>
</Modal>
```

For glass variant (translucent, larger blur, rounded-2xl), use
`variant="glass"`. The close button there is conventionally an
absolutely-positioned ✕ rather than the ESC chip; render it inline in
the modal body when needed (the default ModalHeader still works but
the ✕ style is the established idiom).

### Button

Six variants. Pick by *semantic action*, not by color:

| Variant | When |
|---|---|
| `primary` | Default CTA. Filled violet accent. |
| `secondary` | Cancel, dismiss, "stay here." Filled neutral surface. |
| `ghost` | Tertiary controls in dense toolbars (tabs, command bars). Transparent. |
| `outline` | Restraint. Bordered, no fill. Good for "Reset", "Skip". |
| `danger` | Destructive: Sell, Delete, Close-All. Red treatment. |
| `success` | Affirmative for trading: Buy, Confirm Order. Green treatment. |

Sizes: `sm` (default, 12px text) for compact toolbars, `md` (13px) for
form-shaped action rows. Pass `block` to make the button fill its
container (used inside modal footers with `flex gap-2`).

Icon support: `icon={<svg/>}` renders on the left; `iconOnly` makes the
button square. Hover treatment is centralized — do NOT re-add
onMouseEnter/onMouseLeave styling at the call site.

### Badge

`tone` × `variant` × `size`. The base `<Badge>` covers any colored label.

Domain helpers wrap it with mapping logic — use these instead of writing
your own color tables:

- `<HeatBadge heat={c.social_heat} />` — watchlist social heat.
  `WARM` / `HOT` render in amber/orange; `SPIKING` renders red with a
  pulse animation. `COLD` and missing render nothing.
- `<RegimeBadge regime="BULL" />` — market regime. `BULL` → profit
  green, `BEAR` → loss red, `SIDEWAYS` → neutral.
- `<SourceBadge source="MOMENTUM_BREAKOUT" labels={SOURCE_LABELS} />`
  — watchlist discovery source. Pass `labels` to remap full keys to
  3-letter abbreviations (the dashboard's `SOURCE_LABELS` is a map of
  this shape).
- `<AiDrivenBadge />` — the "AI" pill that flags AI-driven portfolios
  and proposals. Always violet, always soft variant.

Tones available on plain `<Badge>`:
`profit | loss | warning | accent | neutral | info`. Map any new domain
enum to a tone in a sibling helper component, not inline at the call
site.
