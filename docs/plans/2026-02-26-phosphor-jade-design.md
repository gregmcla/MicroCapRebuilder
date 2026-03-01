# Phosphor Jade — Dashboard Visual Polish (Option B)

**Date:** 2026-02-26
**Scope:** Color system overhaul + targeted visual polish. No layout or functionality changes.

## Goals

Make the dashboard feel like a premium dark-mode terminal — Vercel/Linear/Godel aesthetic. Restrained, data-first, sharp.

## Color System

| Token | Value | Usage |
|-------|-------|-------|
| `--color-bg` | `#000000` | True black body background |
| `--color-surface` | `#0A0A0A` | Panel backgrounds |
| `--color-elevated` | `#111111` | Cards, hover backgrounds |
| `--color-border` | `#1E1E1E` | All borders (felt, not seen) |
| `--color-border-hover` | `#2A2A2A` | Hover border states |
| `--color-accent` | `#00D488` | Jade — primary accent |
| `--color-profit` | `#00D488` | Same as accent — jade = profit |
| `--color-loss` | `#FF4458` | Clean sharp red |
| `--color-text-primary` | `#F5F5F5` | Primary data values |
| `--color-text-secondary` | `#6A6A6A` | Labels, secondary info |
| `--color-text-muted` | `#3A3A3A` | Disabled, placeholder |

**Key principle: jade = profit.** The accent color and profit color are identical. Every jade element semantically communicates "positive / forward / active." Loss is red. Everything else is white or gray.

## Typography

- Add `font-variant-numeric: tabular-nums` to all financial values (prices, P&L, percentages) — numbers align in columns like a real terminal
- No font family change

## Component Changes

### Buttons
- **ANALYZE (primary):** Solid jade fill (`#00D488`), black text, `border-radius: 3px` — sharp, almost square
- **Secondary buttons:** Transparent, `1px solid #2A2A2A`, gray text
- **CLOSE ALL (destructive):** `1px solid #FF4458`, red text, no fill
- Remove all `rounded-lg` → use `rounded-sm` or `rounded` (3px max)

### Hover States
- Replace all fuzzy box-shadow glows with crisp `box-shadow: 0 0 0 1px #00D488` ring
- Row hover: background shifts `#000 → #111111`, plus 1px jade left border appears
- No glow at rest on anything

### Position Progress Bars
- Replace chunky colored progress bar with a single `1px` bottom border on each row
- Color encodes progress: `#FF4458` near stop loss → `#1E1E1E` neutral middle → `#00D488` near take profit
- Progress encoded in the row itself, not a separate element

### Market Ticker Banner
- Keep sparklines (user preference)
- Sparklines use jade (`#00D488`) for stroke/gradient
- Remove any remaining glow/shadow from banner border

### Mommy Avatar
- Ambient glow: `0 0 24px rgba(0, 212, 136, 0.08)` — barely there, always on
- Avatar fill/stroke: jade

### All Other Accent Colors
- All remaining `#FF6600` orange references → `#00D488` jade
- All remaining cyan references → jade
- Profit green (`text-green-400`) → jade
- Loss red (`text-red-400`) → `#FF4458`

### Borders
- All borders: `0.5px` or `1px solid #1E1E1E`
- No decorative borders, only structural

## Files to Change

1. `dashboard/src/index.css` — color tokens, base styles
2. `dashboard/src/components/MarketTickerBanner.tsx` — sparkline colors
3. `dashboard/src/components/CandlestickChart.tsx` — crosshair color
4. `dashboard/src/components/PositionRowSparkline.tsx` — stroke/gradient
5. `dashboard/src/components/MommyAvatar.tsx` — fill/stroke/glow
6. `dashboard/src/components/PositionsPanel.tsx` — progress bar → 1px border, hover states, tabular-nums
7. Global button styles or individual button components — shape + ANALYZE fill

## Out of Scope (Phase C)

- Layout changes
- Panel restructuring
- Typography/font family
- New components or features
