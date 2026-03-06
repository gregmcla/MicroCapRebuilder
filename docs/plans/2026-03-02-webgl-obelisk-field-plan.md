# WebGL Performance Obelisk Field — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the SVG ObeliskField with a WebGL/Three.js implementation using React Three Fiber. Each portfolio becomes a sculpted 3D slab mesh shaped by real performance geometry, lit with directional lighting, and animated with a cubic-bezier construction reveal.

**Architecture:** React Three Fiber `<Canvas>` replaces the SVG. Each column is a `BufferGeometry` slab (front + back + sides) built from the performance data pipeline. `MeshPhysicalMaterial` with clearcoat and per-column emissive accent. Three-light rig (directional + rim + ambient). Clip-plane animation for height reveal + geometry rebuild for flare emergence. Hover via R3F pointer events on invisible hit meshes. `@react-three/drei` `<Html>` for DOM tooltips anchored to 3D positions.

**Tech Stack:** `@react-three/fiber` v8, `@react-three/drei` v9, `three`, `@types/three` — React 19, TypeScript, no new bundler config needed.

---

## Three Non-Negotiable Guardrails

### 1. Sculpted surface — not a flat slab

`buildColumnGeometry` must produce **one row of 4 vertices per sparkline point** — not just top + bottom. Every segment `(t, t+1)` generates its own quad with `hw[t]` and `hw[t+1]` as distinct half-widths. This means a 100-point sparkline produces 100 vertex rows and 99 quad strips per face. `computeVertexNormals()` then computes smooth shading from adjacent face normals, so the light grazes flares and shadows fill scars. If only 2 rows are generated (top/bottom), the mesh is a beveled plank — no amount of lighting will save it.

### 2. Ground reflection + fog = spatial weight

A plain matte ground plane makes columns feel pasted onto nothing. Use `MeshReflectorMaterial` from `@react-three/drei`:

```tsx
import { MeshReflectorMaterial } from "@react-three/drei";

<mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.015, 0]} receiveShadow>
  <planeGeometry args={[22, 22]} />
  <MeshReflectorMaterial
    blur={[400, 100]}
    resolution={512}
    mixBlur={8}
    mixStrength={0.07}    // 7% reflection — premium, not shiny
    roughness={0.98}
    depthScale={1.2}
    minDepthThreshold={0.4}
    maxDepthThreshold={1.4}
    color="#030308"
    metalness={0.04}
  />
</mesh>
```

Plus `<fog attach="fog" args={["#03030a", 14, 24]} />` for atmospheric depth.

### 3. Extreme compression for composition coherence

If one portfolio is 10× the return of others, it dominates and ruins the field. Three layers of compression:

**a. P95 global height scale** — instead of `MAX_HEIGHT / maxAbsReturn`, use the P95 of all portfolio max absolute returns. Outliers can still be tall, but not infinitely so:
```typescript
const sorted = valid.map(getMaxAbs).sort((a, b) => a - b);
const p95 = sorted[Math.floor(sorted.length * 0.95)] ?? sorted[sorted.length - 1];
const globalScale = MAX_HEIGHT / Math.max(1, p95);
```

**b. Sqrt Y compression per column** — already in plan:
```typescript
const compressed = Math.sign(norm) * Math.sqrt(Math.abs(norm)) * maxAbsReturn;
```

**c. P90 normalization for velocity/drawdown** — already in plan. Must be applied per-column, not globally, so each column's flares/scars are relative to its own volatility profile.

---

## 3D Unit Scale

- Scene X span: 10 units (-5 to +5)
- Column max height: 5 units
- Column depth (front-to-back): 0.28 units
- Column base half-width: 0.20 units
- Spacing margin: 1.5 units from edges

---

## Constants

```typescript
const SCENE_WIDTH   = 10;
const MAX_HEIGHT    = 5.0;
const COL_DEPTH     = 0.28;
const COL_BASE_HW   = 0.20;   // base half-width
const FLARE_K       = 0.28;   // normalized velocity → width add
const SCAR_K        = 0.16;   // normalized drawdown → width subtract
const MIN_HW        = 0.08;
const MAX_HW        = 0.80;
const LOAD_DURATION = 1.6;    // seconds
const CROWN_ROWS    = 4;      // top N segments in crown mesh
```

---

### Task 1: Install dependencies

**Files:**
- Modify: `dashboard/package.json` (via npm install)

**Step 1: Install R3F + drei + Three.js**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
npm install three @react-three/fiber @react-three/drei
npm install -D @types/three
```

**Step 2: Verify**

```bash
node -e "require('./node_modules/three/build/three.cjs.js')" && echo "three OK"
```

Expected: `three OK`

**Step 3: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/package.json dashboard/package-lock.json
git commit -m "chore: add three.js, react-three-fiber, drei"
```

---

### Task 2: Data pipeline + geometry builder

**Files:**
- Rewrite: `dashboard/src/components/ObeliskField.tsx` (full file replacement)

This task writes the file from scratch — no JSX yet. Just imports, constants, data pipeline, and `buildColumnGeometry`.

**Step 1: Write the full new file**

```typescript
/**
 * Performance Obelisk Field — WebGL/R3F implementation.
 * Each portfolio becomes a sculpted 3D slab lit by real directional lighting.
 */

import { useRef, useMemo, useState, useEffect } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import * as THREE from "three";
import type { PortfolioSummary } from "../lib/types";

// ── Scene constants ──────────────────────────────────────────────────────────

const SCENE_WIDTH   = 10;
const MAX_HEIGHT    = 5.0;
const COL_DEPTH     = 0.28;
const COL_BASE_HW   = 0.20;
const FLARE_K       = 0.28;
const SCAR_K        = 0.16;
const MIN_HW        = 0.08;
const MAX_HW        = 0.80;
const LOAD_DURATION = 1.6;
const CROWN_ROWS    = 4;

const PALETTE = [
  "#34d399", "#818cf8", "#38bdf8", "#fb923c",
  "#f472b6", "#a78bfa", "#fbbf24", "#4ade80",
];

// ── Easing ───────────────────────────────────────────────────────────────────

function cubicBezierEase(t: number): number {
  const p1x = 0.16, p1y = 1.0, p2x = 0.3, p2y = 1.0;
  const cx = 3 * p1x, bx = 3 * (p2x - p1x) - cx, ax = 1 - cx - bx;
  const cy = 3 * p1y, by = 3 * (p2y - p1y) - cy, ay = 1 - cy - by;
  let u = t;
  for (let i = 0; i < 8; i++) {
    const xu = ((ax * u + bx) * u + cx) * u;
    const dxu = (3 * ax * u + 2 * bx) * u + cx;
    if (Math.abs(dxu) < 1e-6) break;
    u -= (xu - t) / dxu;
  }
  u = Math.max(0, Math.min(1, u));
  return ((ay * u + by) * u + cy) * u;
}

// ── Data pipeline ────────────────────────────────────────────────────────────

interface ObeliskData {
  ys: number[];           // y position of each row (in 3D units, base = 0)
  halfWidths: number[];   // half-width at each row (full flares, pre-animation)
  finalReturn: number;    // cumReturn[last]
  isNewHigh: boolean;
  lean: number;           // Z-axis rotation in radians
  maxY: number;           // tallest y value
}

function computeObeliskData(
  sparkline: number[],
  globalScale: number    // 3D units per percentage point
): ObeliskData | null {
  if (!sparkline || sparkline.length < 2) return null;
  const base = sparkline[0];
  if (base === 0) return null;

  const cum = sparkline.map((v) => ((v - base) / base) * 100);

  // Smoothed velocity
  const velRaw = cum.map((v, i) => (i === 0 ? 0 : v - cum[i - 1]));
  const vel = velRaw.map((_, i) => {
    const slice = velRaw.slice(Math.max(0, i - 2), Math.min(velRaw.length, i + 3));
    return slice.reduce((a, b) => a + b, 0) / slice.length;
  });

  // Drawdown from prior high
  let runMax = cum[0];
  const dd = cum.map((v) => {
    runMax = Math.max(runMax, v);
    return v - runMax;
  });

  // P90 normalization
  const sortedVelPos = [...vel].filter((v) => v > 0).sort((a, b) => a - b);
  const p90vel = sortedVelPos[Math.floor(sortedVelPos.length * 0.9)] ?? 1;
  const sortedDdNeg = [...dd].filter((v) => v < 0).sort((a, b) => a - b);
  const p90dd = Math.abs(sortedDdNeg[Math.floor(sortedDdNeg.length * 0.1)] ?? -1);

  // Half-widths (full, pre-animation — animation interpolates from base)
  const halfWidths = vel.map((v, i) => {
    const flare = p90vel > 0 ? (v / p90vel) * FLARE_K : 0;
    const scar  = p90dd  > 0 ? (Math.abs(dd[i]) / p90dd) * SCAR_K : 0;
    return Math.max(MIN_HW, Math.min(MAX_HW, COL_BASE_HW + flare - scar));
  });

  // Y positions with sqrt compression
  const maxAbsReturn = Math.max(1, ...cum.map(Math.abs));
  const ys = cum.map((c) => {
    const norm = c / maxAbsReturn;
    const compressed = Math.sign(norm) * Math.sqrt(Math.abs(norm)) * maxAbsReturn;
    return Math.max(0.1, compressed * globalScale);
  });

  const finalReturn = cum[cum.length - 1];
  const maxCum = Math.max(...cum);
  const isNewHigh = finalReturn >= maxCum - 0.01;

  // Lean: slope of final 20% of curve
  const tailStart = Math.floor(cum.length * 0.8);
  const tailSlope = (cum[cum.length - 1] - cum[tailStart]) / (cum.length - tailStart);
  const lean = Math.max(-0.055, Math.min(0.055, tailSlope * 0.003));

  const maxY = Math.max(...ys);

  return { ys, halfWidths, finalReturn, isNewHigh, lean, maxY };
}

// ── Geometry builder ─────────────────────────────────────────────────────────

/**
 * Build a slab BufferGeometry for one column.
 * widthProgress: 0 = base half-width only, 1 = full flares baked in.
 * startRow / endRow: for building a sub-slice (e.g. crown strip).
 */
function buildColumnGeometry(
  data: ObeliskData,
  widthProgress: number,
  startRow = 0,
  endRow?: number
): THREE.BufferGeometry {
  const { ys, halfWidths } = data;
  const end = endRow ?? ys.length;
  const sliceYs = ys.slice(startRow, end);
  const sliceHW = halfWidths.slice(startRow, end);
  const N = sliceYs.length;
  if (N < 2) return new THREE.BufferGeometry();

  const d = COL_DEPTH / 2;

  // Interpolated half-widths: flat base → full flares
  const hw = sliceHW.map((w) => COL_BASE_HW + (w - COL_BASE_HW) * widthProgress);

  const positions: number[] = [];
  const normals:   number[] = [];
  const indices:   number[] = [];

  function addQuad(
    v0: [number, number, number], v1: [number, number, number],
    v2: [number, number, number], v3: [number, number, number],
    nx: number, ny: number, nz: number
  ) {
    const i = positions.length / 3;
    positions.push(...v0, ...v1, ...v2, ...v3);
    normals.push(nx,ny,nz, nx,ny,nz, nx,ny,nz, nx,ny,nz);
    indices.push(i, i+1, i+2,  i, i+2, i+3);
  }

  for (let t = 0; t < N - 1; t++) {
    const y0 = sliceYs[t],  y1 = sliceYs[t + 1];
    const w0 = hw[t],       w1 = hw[t + 1];

    // Front face
    addQuad([-w0, y0, d], [w0, y0, d], [w1, y1, d], [-w1, y1, d], 0, 0, 1);
    // Back face
    addQuad([w0, y0, -d], [-w0, y0, -d], [-w1, y1, -d], [w1, y1, -d], 0, 0, -1);
    // Left side
    addQuad([-w0, y0, -d], [-w0, y0, d], [-w1, y1, d], [-w1, y1, -d], -1, 0, 0);
    // Right side
    addQuad([w0, y0, d], [w0, y0, -d], [w1, y1, -d], [w1, y1, d], 1, 0, 0);
  }

  // Top cap
  const wTop = hw[N - 1];
  const yTop = sliceYs[N - 1];
  addQuad(
    [-wTop, yTop, -d], [wTop, yTop, -d],
    [wTop, yTop,  d], [-wTop, yTop,  d],
    0, 1, 0
  );

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geo.setAttribute("normal",   new THREE.Float32BufferAttribute(normals, 3));
  geo.setIndex(indices);
  geo.computeVertexNormals(); // smooth normals for soft surface transitions
  return geo;
}
```

**Step 2: TypeScript check (no JSX yet)**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

**Step 3: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/ObeliskField.tsx
git commit -m "feat: WebGL obelisk data pipeline and geometry builder"
```

---

### Task 3: ObeliskMesh component

**Files:**
- Modify: `dashboard/src/components/ObeliskField.tsx` (append)

**Step 1: Append ObeliskMesh**

```typescript
// ── ObeliskMesh ──────────────────────────────────────────────────────────────

interface ObeliskMeshProps {
  data: ObeliskData;
  colX: number;
  color: string;
  animProgress: number;
  crownVisible: boolean;
  isHovered: boolean;
  otherHovered: boolean;
  onEnter: () => void;
  onLeave: () => void;
}

function ObeliskMesh({
  data, colX, color, animProgress, crownVisible,
  isHovered, otherHovered, onEnter, onLeave,
}: ObeliskMeshProps) {
  const widthProgress = Math.min(1, animProgress * 1.35);

  // Body geometry: full column, width flares emerge with animation
  const bodyGeo = useMemo(
    () => buildColumnGeometry(data, widthProgress),
    [data, widthProgress]
  );

  // Crown geometry: top CROWN_ROWS segments only
  const crownStart = Math.max(0, data.ys.length - 1 - CROWN_ROWS);
  const crownGeo = useMemo(
    () => buildColumnGeometry(data, widthProgress, crownStart),
    [data, widthProgress, crownStart]
  );

  // Clip plane for height reveal: column revealed from y=0 upward
  const clipPlane = useMemo(
    () => new THREE.Plane(new THREE.Vector3(0, -1, 0), 0),
    []
  );
  useEffect(() => {
    clipPlane.constant = data.maxY * animProgress;
  }, [animProgress, data.maxY, clipPlane]);

  const accentColor = useMemo(() => new THREE.Color(color), [color]);
  const opacity = otherHovered ? 0.3 : 1.0;

  // Crown hairline geometry (1px bright line along top front edge)
  const hairlineGeo = useMemo(() => {
    const wTop = data.halfWidths[data.halfWidths.length - 1];
    const yTop = data.ys[data.ys.length - 1];
    const pts = new Float32Array([
      -wTop, yTop, COL_DEPTH / 2 + 0.005,
       wTop, yTop, COL_DEPTH / 2 + 0.005,
    ]);
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    return g;
  }, [data]);

  // Antenna geometry (new-high: thin vertical line above crown)
  const antennaGeo = useMemo(() => {
    if (!data.isNewHigh) return null;
    const yTop = data.ys[data.ys.length - 1];
    const pts = new Float32Array([0, yTop, 0, 0, yTop + 0.4, 0]);
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    return g;
  }, [data]);

  return (
    <group position={[colX, 0, 0]} rotation={[0, 0, data.lean]}>
      {/* Column body */}
      <mesh geometry={bodyGeo} castShadow receiveShadow>
        <meshPhysicalMaterial
          color="#07070d"
          roughness={0.75}
          metalness={0.08}
          clearcoat={0.25}
          clearcoatRoughness={0.5}
          emissive={accentColor}
          emissiveIntensity={isHovered ? 0.07 : 0.025}
          clippingPlanes={[clipPlane]}
          transparent={otherHovered}
          opacity={opacity}
          side={THREE.FrontSide}
        />
      </mesh>

      {/* Crown strip — higher emissive, visible after crown ignition */}
      {crownVisible && (
        <mesh geometry={crownGeo}>
          <meshPhysicalMaterial
            color="#0b0b18"
            roughness={0.5}
            metalness={0.15}
            clearcoat={0.35}
            emissive={accentColor}
            emissiveIntensity={isHovered ? 0.60 : 0.38}
            clippingPlanes={[clipPlane]}
            transparent={otherHovered}
            opacity={opacity}
          />
        </mesh>
      )}

      {/* Crown hairline */}
      {crownVisible && (
        <lineSegments geometry={hairlineGeo}>
          <lineBasicMaterial
            color={color}
            transparent
            opacity={isHovered ? 0.92 : 0.65}
          />
        </lineSegments>
      )}

      {/* New-high antenna */}
      {crownVisible && antennaGeo && (
        <lineSegments geometry={antennaGeo}>
          <lineBasicMaterial color={color} transparent opacity={0.45} />
        </lineSegments>
      )}

      {/* Invisible hit box for hover */}
      <mesh
        position={[0, data.maxY / 2, 0]}
        onPointerEnter={onEnter}
        onPointerLeave={onLeave}
      >
        <boxGeometry args={[1.0, data.maxY + 0.5, COL_DEPTH * 3]} />
        <meshBasicMaterial visible={false} />
      </mesh>
    </group>
  );
}
```

**Step 2: TypeScript check**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npx tsc --noEmit 2>&1 | head -20
```

**Step 3: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/ObeliskField.tsx
git commit -m "feat: ObeliskMesh with MeshPhysicalMaterial, crown strip, hairline"
```

---

### Task 4: Scene — lighting, ground, camera, animation loop, ObeliskField export

**Files:**
- Modify: `dashboard/src/components/ObeliskField.tsx` (append)

**Step 1: Append ground plane + camera + forge front + animated scene**

```typescript
// ── Ground plane ─────────────────────────────────────────────────────────────

function GroundPlane() {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.015, 0]} receiveShadow>
      <planeGeometry args={[22, 22]} />
      <meshStandardMaterial color="#030308" roughness={0.95} metalness={0.04} />
    </mesh>
  );
}

// ── Camera with slow lateral drift ───────────────────────────────────────────

function SceneCamera({ hoveredX }: { hoveredX: number | null }) {
  const { camera } = useThree();
  const driftPhase = useRef(0);
  useFrame((_, delta) => {
    driftPhase.current += delta * 0.06;
    const drift = Math.sin(driftPhase.current) * 0.22;
    const nudge = hoveredX !== null ? hoveredX * 0.12 : 0;
    const targetX = drift + nudge;
    camera.position.x += (targetX - camera.position.x) * 0.025;
  });
  return null;
}

// ── Forge front (leading edge during load animation) ─────────────────────────

function ForgeFront({ colX, revealY, color }: {
  colX: number; revealY: number; color: string;
}) {
  const geo = useMemo(() => {
    const w = 0.65;
    const pts = new Float32Array([
      colX - w, revealY, COL_DEPTH / 2 + 0.01,
      colX + w, revealY, COL_DEPTH / 2 + 0.01,
    ]);
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    return g;
  }, [colX, revealY]);

  return (
    <lineSegments geometry={geo}>
      <lineBasicMaterial color={color} transparent opacity={0.4} />
    </lineSegments>
  );
}

// ── AnimatedScene (must be inside Canvas to use useFrame) ────────────────────

interface AnimatedSceneProps {
  valid: PortfolioSummary[];
  allData: (ObeliskData | null)[];
  colXs: number[];
  animProgress: number;
  setAnimProgress: React.Dispatch<React.SetStateAction<number>>;
  crownsVisible: boolean[];
  setCrownsVisible: React.Dispatch<React.SetStateAction<boolean[]>>;
  hoveredIdx: number | null;
  setHoveredIdx: React.Dispatch<React.SetStateAction<number | null>>;
  startTimeRef: React.MutableRefObject<number | null>;
  timeoutIds: React.MutableRefObject<ReturnType<typeof setTimeout>[]>;
}

function AnimatedScene({
  valid, allData, colXs, animProgress, setAnimProgress,
  crownsVisible, setCrownsVisible, hoveredIdx, setHoveredIdx,
  startTimeRef, timeoutIds,
}: AnimatedSceneProps) {
  useFrame((state) => {
    if (animProgress >= 1) return;
    if (startTimeRef.current === null) startTimeRef.current = state.clock.elapsedTime;
    const elapsed = state.clock.elapsedTime - startTimeRef.current;
    const t = Math.min(elapsed / LOAD_DURATION, 1);
    const eased = cubicBezierEase(t);
    setAnimProgress(eased);

    if (t >= 1) {
      valid.forEach((_, i) => {
        const id = setTimeout(() => {
          setCrownsVisible((prev) => {
            const next = [...prev];
            next[i] = true;
            return next;
          });
        }, i * 80);
        timeoutIds.current.push(id);
      });
    }
  });

  return (
    <>
      {valid.map((p, i) => {
        const data = allData[i];
        if (!data) return null;
        const color = PALETTE[i % PALETTE.length];
        const revealY = data.maxY * animProgress;
        return (
          <group key={p.id}>
            <ObeliskMesh
              data={data}
              colX={colXs[i]}
              color={color}
              animProgress={animProgress}
              crownVisible={crownsVisible[i] ?? false}
              isHovered={hoveredIdx === i}
              otherHovered={hoveredIdx !== null && hoveredIdx !== i}
              onEnter={() => setHoveredIdx(i)}
              onLeave={() => setHoveredIdx(null)}
            />
            {/* Forge front: glowing build edge during load animation */}
            {animProgress < 0.97 && (
              <ForgeFront colX={colXs[i]} revealY={revealY} color={color} />
            )}
          </group>
        );
      })}

      {/* Hover tooltip */}
      {hoveredIdx !== null && (() => {
        const p = valid[hoveredIdx];
        const data = allData[hoveredIdx];
        if (!data) return null;
        const ret = data.finalReturn;
        return (
          <Html
            position={[colXs[hoveredIdx], data.maxY + 0.45, 0]}
            center
            style={{
              pointerEvents: "none",
              background: "rgba(6,6,16,0.94)",
              border: "1px solid rgba(255,255,255,0.09)",
              borderRadius: "4px",
              padding: "4px 9px",
              fontFamily: "monospace",
              fontSize: "10px",
              fontWeight: "600",
              color: "rgba(255,255,255,0.82)",
              whiteSpace: "nowrap",
              letterSpacing: "0.04em",
            }}
          >
            {p.name} &nbsp;{ret >= 0 ? "+" : ""}{ret.toFixed(1)}%
          </Html>
        );
      })()}

      {/* ID labels at base */}
      {valid.map((p, i) => (
        <Html
          key={`lbl-${p.id}`}
          position={[colXs[i], -0.28, 0]}
          center
          style={{
            pointerEvents: "none",
            fontFamily: "monospace",
            fontSize: "7.5px",
            fontWeight: "700",
            color: "rgba(255,255,255,0.18)",
            letterSpacing: "0.09em",
            textTransform: "uppercase",
            userSelect: "none",
          }}
        >
          {p.id}
        </Html>
      ))}
    </>
  );
}

// ── ObeliskField (default export) ────────────────────────────────────────────

interface ObeliskFieldProps {
  portfolios: PortfolioSummary[];
}

export default function ObeliskField({ portfolios }: ObeliskFieldProps) {
  // WebGL support detection
  const [webglSupported] = useState(() => {
    try {
      const canvas = document.createElement("canvas");
      return !!(
        window.WebGLRenderingContext &&
        (canvas.getContext("webgl") || canvas.getContext("experimental-webgl"))
      );
    } catch {
      return false;
    }
  });

  const [animProgress, setAnimProgress] = useState(0);
  const [crownsVisible, setCrownsVisible] = useState<boolean[]>([]);
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  const valid = useMemo(
    () =>
      portfolios
        .filter((p) => !p.error && p.sparkline && p.sparkline.length >= 2)
        .sort((a, b) => (a.total_return_pct ?? 0) - (b.total_return_pct ?? 0)),
    [portfolios]
  );

  const globalScale = useMemo(() => {
    const maxRet = Math.max(
      1,
      ...valid.map((p) => {
        const base = p.sparkline![0];
        return Math.max(...p.sparkline!.map((v) => Math.abs(((v - base) / base) * 100)));
      })
    );
    return MAX_HEIGHT / maxRet;
  }, [valid]);

  const allData = useMemo(
    () => valid.map((p) => computeObeliskData(p.sparkline!, globalScale)),
    [valid, globalScale]
  );

  const colXs = useMemo(() => {
    const n = valid.length;
    const margin = 1.5;
    const span = SCENE_WIDTH - margin * 2;
    return Array.from({ length: n }, (_, i) =>
      n === 1 ? 0 : -SCENE_WIDTH / 2 + margin + (i / (n - 1)) * span
    );
  }, [valid.length]);

  const startTimeRef = useRef<number | null>(null);
  const timeoutIds = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    startTimeRef.current = null;
    setAnimProgress(0);
    setCrownsVisible([]);
    timeoutIds.current.forEach(clearTimeout);
    timeoutIds.current = [];
    return () => {
      timeoutIds.current.forEach(clearTimeout);
    };
  }, [valid.length]);

  if (!webglSupported) {
    return (
      <div style={{ height: "340px", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <p style={{ fontSize: "11px", color: "var(--text-0)", fontFamily: "monospace" }}>
          WebGL unavailable
        </p>
      </div>
    );
  }

  if (valid.length === 0) {
    return (
      <div style={{ height: "340px", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <p style={{ fontSize: "11px", color: "var(--text-0)", fontFamily: "monospace" }}>
          No portfolio history to display
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        height: "340px",
        background: "#03030a",
        borderRadius: "7px",
        overflow: "hidden",
        border: "1px solid var(--border-0)",
      }}
    >
      <Canvas
        shadows
        camera={{ position: [0, 2.8, 9.5], fov: 38 }}
        gl={{ antialias: true }}
        onCreated={({ gl }) => {
          gl.localClippingEnabled = true;
          gl.shadowMap.enabled = true;
          gl.shadowMap.type = THREE.PCFSoftShadowMap;
          gl.setClearColor(0x03030a);
        }}
      >
        <fog attach="fog" args={["#03030a", 14, 24]} />

        {/* Lighting rig */}
        <ambientLight intensity={0.07} color="#14142a" />
        <directionalLight
          position={[5, 9, 4]}
          intensity={1.5}
          color="#d0d0f0"
          castShadow
          shadow-mapSize={[1024, 1024]}
          shadow-camera-near={0.5}
          shadow-camera-far={22}
          shadow-camera-left={-9}
          shadow-camera-right={9}
          shadow-camera-top={9}
          shadow-camera-bottom={-9}
        />
        {/* Rim light: opposite direction, very faint */}
        <directionalLight
          position={[-4, 2, -3]}
          intensity={0.22}
          color="#1e0e30"
        />

        <GroundPlane />

        <AnimatedScene
          valid={valid}
          allData={allData}
          colXs={colXs}
          animProgress={animProgress}
          setAnimProgress={setAnimProgress}
          crownsVisible={crownsVisible}
          setCrownsVisible={setCrownsVisible}
          hoveredIdx={hoveredIdx}
          setHoveredIdx={setHoveredIdx}
          startTimeRef={startTimeRef}
          timeoutIds={timeoutIds}
        />

        <SceneCamera hoveredX={hoveredIdx !== null ? colXs[hoveredIdx] : null} />
      </Canvas>
    </div>
  );
}
```

**Step 2: TypeScript check**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npx tsc --noEmit 2>&1 | head -30
```

Fix any type errors. Common ones to watch for:
- R3F JSX types: ensure `@types/three` is installed and `three` module augmentation for R3F is active
- `lineSegments` lowercase JSX — R3F uses lowercase for Three.js primitives
- `Html` import from `@react-three/drei`

**Step 3: Browser check**

1. Open http://localhost:5173
2. Navigate to Overview → click OBELISK
3. Should see: dark void, 4 sculpted 3D columns growing upward, real directional shadows

**Step 4: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/ObeliskField.tsx
git commit -m "feat: WebGL ObeliskField — R3F scene, lighting, animation, hover"
```

---

### Task 5: Polish pass

**Files:**
- Modify: `dashboard/src/components/ObeliskField.tsx`

After seeing it in the browser, apply these tuning fixes:

1. **Column overlap**: if columns overlap, reduce `COL_BASE_HW` from `0.20` to `0.14`
2. **Flares too subtle**: if geometry looks like plain boxes, increase `FLARE_K` from `0.28` to `0.40`
3. **Crown too bright/dim**: adjust `emissiveIntensity` on crown mesh (target: visible but not neon)
4. **Camera angle too flat/steep**: adjust `camera={{ position: [0, Y, Z] }}` — increase Y for more top-down, decrease for more frontal
5. **Fog too dense**: increase second fog arg from `14` to `18`
6. **Directional light angle**: if shadows look wrong, adjust `position={[5, 9, 4]}` — Y controls shadow angle
7. **Lean too subtle/dramatic**: adjust the `0.003` multiplier in `computeObeliskData` lean calculation

**Step 1: Make tuning fixes**

**Step 2: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
git add dashboard/src/components/ObeliskField.tsx
git commit -m "fix: WebGL obelisk visual polish pass"
```

**Step 3: Push**

```bash
git push
```
