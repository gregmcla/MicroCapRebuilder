# Map + Chart Critique
Date: 2026-03-27

---

## ConstellationMap: What Makes It Look Bad

### The Core Problem: Wrong Metaphor for the Data
The solar-system metaphor (portfolios = suns, positions = orbiting planets) creates gorgeous sci-fi imagery that communicates **almost nothing useful**. The orbital radius is fixed by ring assignment, not data. The angular position is meaningless. The only real data encoded is: planet color (P&L direction), planet size (market value). Everything else is decoration fighting for attention.

### Specific Visual Problems

**1. Color uses portfolio hue, not performance**
The biggest visual element (the sun, orbit rings, sun label) use `sunColor()` which maps to green/amber/red based on total return. Planet colors map to P&L. But the sun's color also dominates the coronas and orbit rings — so the map is simultaneously saying "portfolio is up" (green sun) and "position is losing" (red planet) without a clear hierarchy. The viewer's eye doesn't know what to read first.

**2. Background is too "ambient space" — no structure**
`#05060f` with a radial vignette burn from the outer rim. This looks like Windows XP starfield. It gives no spatial context for where portfolios are or how they relate. The slight vignette darkening makes the edges feel unfinished.

**3. Sun labels are microscopic and wrong-colored**
8.5px monospace above the corona. On a 360px-tall canvas with 13 portfolios arranged in a circle, most labels are clipped, overlapping orbit rings from adjacent portfolios, and 72% opacity on top of a dark background. Virtually unreadable.

**4. Planet labels appear BELOW the planet, not inside**
`drawPlanetLabel()` renders the ticker 4px below the bottom edge of the planet. On small planets (r < 7 = hidden entirely), and on the largest (r=13), the label is only shown when radius >= 7. With 13 portfolios and 35 planets, labels are pointing in all directions from tiny specks, creating a floating-label soup.

**5. Orbit rings are identical dashed gray lines**
All orbit rings are `rgba(portfolioColor, 0.13)` with identical dash pattern. When 13 portfolios share the space, you can't tell which rings belong to which portfolio. The dashes overlap, creating a continuous noise pattern in the center of the canvas.

**6. Physics: no physics — it's just orbital animation**
Planets orbit at fixed radii with fixed speeds. "Physics" is just trigonometry. Nothing responds to data dynamically. Repulsion, clustering, spring forces — none of this exists. The result is mechanical clock-rotation, not an organic system. The orbital animation makes high-value positions blur together.

**7. Size encoding is too compressed**
`planetR()` = `clamp(sqrt(mv / 700), 5, 13)`. With 13 portfolios of similar equity (~$50K-$200K each and positions of ~$1K-$20K), most planets will cluster between 5-9px radius. The size differentiation is barely visible. You can't tell a $5K position from a $15K position at a glance.

**8. With 13 portfolios, total visual chaos**
13 solar systems in a circle → suns placed on a ~37% radius circle. At 800px wide, the orbit rings of adjacent portfolio systems overlap each other. Planets from portfolio A orbit into the space of portfolio B. The canvas becomes an undifferentiated blob.

### What "Good" Would Look Like
- Coloring by **performance** (green→red gradient) is the most scannable encoding
- Nodes sized by **position value** relative to portfolio total (not absolute market value)
- Ticker text + % return **inside or adjacent to each node** (not floating below)
- Positions **force-directed** by portfolio membership (spring forces toward portfolio centroid)
- Portfolio centroids fixed in a grid/circle, not colliding with each other
- Clean dark background with subtle star field, not a vignette burn
- Glow intensity as a data signal (volatility, P&L magnitude)

---

## PerformanceChart: What Makes It Look Bad

### Specific Visual Problems

**1. Color palette is electric/neon — all colors fight equally**
`#00ffcc`, `#bf7fff`, `#ffb340`, `#00cfff`, `#ff5fa0`... Every color is at maximum saturation. With 13 lines on screen, all at full intensity with screen-blend glow, the chart looks like a fiber optics bundle exploded. Nothing stands out because everything is equally loud. The eye has nowhere to rest.

**2. Glow is 3-pass but too wide — it bleeds everywhere**
Pass 1: blur(10px), lineWidth=22, alpha=0.55 (screen blend). This creates a 44px soft halo around every line. With 13 lines, the entire chart interior is filled with overlapping glow halos. Individual lines lose their identity — what you see is a blurry multicolor smear, not distinct data series.

**3. Echo trails create noise before the line lands**
Three echo trails (offsets: 0.06, 0.12, 0.22) draw blurred versions of each line slightly behind. With 13 series × 3 echoes = 39 additional blur-rendered paths per frame. The trails don't read as "temporal echo" — they read as smearing. The chart looks out-of-focus.

**4. Area fills overlap and muddy the background**
Each series draws a filled area from line down to zone bottom at `globalAlpha=0.26 * glowAlpha`. With 13 areas filled with 13 different screen-blend colors, the background has lost all definition. The green/red background zones are completely drowned out.

**5. Rank strip at bottom is too small and hard to parse**
`stripH = 14px`. A colored bar showing which portfolio is leading each day is a great idea, but at 14px with 13 possible colors, it looks like a broken progress bar. The label "RANK" at 6px in the gutter is invisible.

**6. Right-side labels are 8.5px monospace — too small, too long**
Format: `"ID  +XX.X%"`. At 8.5px with 13 labels stacked (with collision avoidance pushing them down), many labels run off the bottom of the chart. The ID shown is the portfolio ID (e.g., `MICROCAP-MOMENTUM-COMPOUNDER`) not the human name. Nobody will know which portfolio that is.

**7. Hover tooltip shows ALL 13 series simultaneously**
At `cardH = rows.length * LINE_H + PAD_H * 2 = 13*16 + 16 = 224px`, the tooltip is taller than the chart at 340px height. It covers the chart data it's meant to explain.

**8. Zero line is invisible**
`ctx.strokeStyle = "rgba(255,255,255,0.10)"`. In the chaos of 13 glowing lines with 39 echo trails, the zero line is invisible. The most important reference point — "am I up or down?" — cannot be found.

**9. X-axis labels use "time ago" format instead of dates**
`daysAgo()` returns "4mo", "1y", "2w". On a chart where portfolios have different start dates, these relative labels are confusing. "4mo" from what? Better: show start/middle/end dates as fixed anchors.

### What "Good" Would Look Like
- **Tighter glow**: lineWidth 1.5, shadowBlur 4-6px only — not 22px wide halos
- **Color palette**: distinct hues spaced around the color wheel, medium saturation, not neon
- **Hover isolation**: hovered line goes to 3px weight, others fade to 0.2 opacity — clear focus
- **Legend**: right-side vertical list sorted by return, portfolio name + current %, readable size (11px)
- **Tooltip**: max 5 entries, positioned to never cover data
- **Zero line**: make it the most prominent horizontal rule on the chart
- **Drop echoes**: or reduce to 1 very subtle echo (offset 0.06, opacity 0.15)

---

## Design Decisions (Iteration 2)

### ConstellationMap: Go With Enhanced Physics Simulation (Option A)

**Rationale:** The solar system metaphor is wrong but the canvas physics simulation idea is right. The problem isn't the approach, it's the execution. A properly done force-directed node network with performance coloring and real ticker labels is the most distinctively different from a standard chart, while still being information-dense.

**Key design decisions:**

1. **Color encoding**: Performance-based, not portfolio-based
   - `perf >= +10%` → `#4ade80` (bright green)
   - `perf 0→+10%` → interpolate white → green
   - `perf -10→0%` → interpolate red → white
   - `perf <= -10%` → `#f87171` (bright red)

2. **Node sizing**: `radius = clamp(sqrt(value/maxValue) * 40 + 8, 8, 48)` — relative to largest position

3. **Glow encoding**: `shadowBlur = 4 + abs(perf) * 0.8` capped at 24 — magnitude of P&L drives glow intensity

4. **Text on node face**: ticker in bold monospace, perf% below it. Font size proportional to radius.

5. **Physics**: Spring force toward portfolio centroid (strength 0.02), inter-node repulsion (k=800×r_i×r_j/d²), soft boundary, damping 0.88

6. **Portfolio grouping**: Faint dashed rings around each portfolio cluster, portfolioAbbr label near centroid

7. **Background**: `#08090d`, subtle radial gradient from center, sparse static star field

8. **Hover**: Dim others to 0.25 opacity, glassmorphic tooltip showing ticker, portfolio, perf%, value, day%

### PerformanceChart: Surgical Improvements to Existing Canvas

**Key design decisions:**

1. **New palette**: Distinct medium-saturation hues spaced around wheel (sky blue, violet, orange, emerald, pink, yellow, teal, rose, lime, blue, purple, green, orange-red, cyan, fuchsia)

2. **Line rendering**: 1.5px default, 3px hovered. `shadowBlur` 3px (not 22px wide blur halos). Remove 3-pass glow, use simple shadowBlur instead. Keep screen blend for lines. Dim non-hovered series to 0.2 opacity.

3. **Drop echo trails entirely**: They create too much noise. The animation draw-on effect is enough drama.

4. **Zero line**: `rgba(255,255,255,0.2)`, lineWidth 1.5 — make it visible.

5. **Legend**: Right-side vertical list. Each entry: 8px dot + name (16 char truncated) + return %. Sorted by return desc. Replace rank strip with this.

6. **Hover tooltip**: Max 5 visible entries, positioned to not overflow.

7. **Y-axis**: Fewer labels (0%, ±25%, ±50%, ±100%), cleaner.

8. **Area fills**: Reduce opacity to 0.10 (from 0.26) to reduce background mudding.

**CRITICAL PRESERVED**: Dual-zone Y-scale logic unchanged. `ctx.save()`/`ctx.restore()` clipping per series unchanged. `pts.length < 2` guard calls `ctx.restore()` before `continue`.
