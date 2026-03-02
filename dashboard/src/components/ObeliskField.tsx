/**
 * Performance Obelisk Field — WebGL/R3F implementation.
 * Each portfolio becomes a sculpted 3D slab lit by real directional lighting.
 * One vertex row per sparkline point ensures continuous surface variation.
 */

import { useRef, useMemo, useState, useEffect } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, MeshReflectorMaterial } from "@react-three/drei";
import * as THREE from "three";
import type { PortfolioSummary } from "../lib/types";

// ── Constants ────────────────────────────────────────────────────────────────

const SCENE_WIDTH   = 10;
const MAX_HEIGHT    = 5.0;
const COL_DEPTH     = 0.28;
const COL_BASE_HW   = 0.20;   // base half-width
const FLARE_K       = 0.30;   // normalized velocity → half-width addition
const SCAR_K        = 0.18;   // normalized drawdown → half-width subtraction
const MIN_HW        = 0.08;
const MAX_HW        = 0.82;
const LOAD_DURATION = 1.6;    // seconds
const CROWN_ROWS    = 5;      // top N segments treated as crown (higher emissive)

const PALETTE = [
  "#34d399", "#818cf8", "#38bdf8", "#fb923c",
  "#f472b6", "#a78bfa", "#fbbf24", "#4ade80",
];

// ── Cubic-bezier easing: cubic-bezier(0.16, 1, 0.3, 1) ──────────────────────

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
  ys: number[];           // y position of each row (3D units, base=0)
  halfWidths: number[];   // full half-width at each row (pre-animation)
  finalReturn: number;    // cumulative return at last sparkline point
  isNewHigh: boolean;     // ended at all-time high
  lean: number;           // Z-axis rotation radians (-0.055 to +0.055)
  maxY: number;           // tallest y value
}

function computeObeliskData(
  sparkline: number[],
  globalScale: number     // 3D units per percentage point (P95-based)
): ObeliskData | null {
  if (!sparkline || sparkline.length < 2) return null;
  const base = sparkline[0];
  if (base === 0) return null;

  // 1. Cumulative return at each step
  const cum = sparkline.map((v) => ((v - base) / base) * 100);

  // 2. Smoothed velocity (5-point moving average of first derivative)
  const velRaw = cum.map((v, i) => (i === 0 ? 0 : v - cum[i - 1]));
  const vel = velRaw.map((_, i) => {
    const s = velRaw.slice(Math.max(0, i - 2), Math.min(velRaw.length, i + 3));
    return s.reduce((a, b) => a + b, 0) / s.length;
  });

  // 3. Drawdown from prior high
  let runMax = cum[0];
  const dd = cum.map((v) => {
    runMax = Math.max(runMax, v);
    return v - runMax; // always <= 0
  });

  // 4. P90 normalization — per-column so each portfolio's geometry is coherent
  const posVel = [...vel].filter((v) => v > 0).sort((a, b) => a - b);
  const p90vel = posVel.length > 0 ? posVel[Math.floor(posVel.length * 0.9)] : 1;
  const negDd  = [...dd].filter((v) => v < 0).sort((a, b) => a - b);
  const p90dd  = negDd.length > 0 ? Math.abs(negDd[Math.floor(negDd.length * 0.1)]) : 1;

  // 5. Half-widths: continuous per segment (one entry per sparkline point)
  const halfWidths = vel.map((v, i) => {
    const flare = p90vel > 0 ? (Math.max(0, v) / p90vel) * FLARE_K : 0;
    const scar  = p90dd  > 0 ? (Math.abs(dd[i]) / p90dd) * SCAR_K : 0;
    return Math.max(MIN_HW, Math.min(MAX_HW, COL_BASE_HW + flare - scar));
  });

  // 6. Y positions with sqrt compression (prevents extreme portfolios dominating)
  const maxAbsReturn = Math.max(1, ...cum.map(Math.abs));
  const ys = cum.map((c) => {
    const norm = c / maxAbsReturn;
    const compressed = Math.sign(norm) * Math.sqrt(Math.abs(norm)) * maxAbsReturn;
    const y3d = compressed * globalScale;
    return Math.max(0.1, y3d); // minimum 0.1 units for negative-return stub
  });

  const finalReturn = cum[cum.length - 1];
  const maxCum = Math.max(...cum);
  const isNewHigh = finalReturn >= maxCum - 0.01;

  // 7. Lean: slope of final 20% of return curve
  const tailStart = Math.floor(cum.length * 0.8);
  const tailSlope = tailStart < cum.length - 1
    ? (cum[cum.length - 1] - cum[tailStart]) / (cum.length - tailStart)
    : 0;
  const lean = Math.max(-0.055, Math.min(0.055, tailSlope * 0.003));

  const maxY = Math.max(...ys);

  return { ys, halfWidths, finalReturn, isNewHigh, lean, maxY };
}

// ── Geometry builder ─────────────────────────────────────────────────────────

/**
 * Build a sculpted slab BufferGeometry.
 *
 * CRITICAL: One vertex row per sparkline point. N points → N rows → N-1 quad
 * strips per face. This produces continuous surface variation that the
 * directional light can graze, revealing flares and shadowing scars.
 *
 * widthProgress 0→1: animates from flat base width to full flares.
 * startRow/endRow: build a sub-slice (e.g., crown strip).
 */
function buildColumnGeometry(
  data: ObeliskData,
  widthProgress: number,
  startRow = 0,
  endRow?: number
): THREE.BufferGeometry {
  const end = endRow ?? data.ys.length;
  const sliceYs = data.ys.slice(startRow, end);
  const sliceHW = data.halfWidths.slice(startRow, end);
  const N = sliceYs.length;

  if (N < 2) return new THREE.BufferGeometry();

  const d = COL_DEPTH / 2;

  // Interpolate half-widths: flat base (COL_BASE_HW) → full flares at widthProgress=1
  const hw = sliceHW.map((w) => COL_BASE_HW + (w - COL_BASE_HW) * widthProgress);

  const positions: number[] = [];
  const normals:   number[] = [];
  const indices:   number[] = [];

  // Adds a quad as 2 triangles. Winding: counter-clockwise for outward normals.
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

  // One quad strip per adjacent row pair: N points → N-1 strips per face
  for (let t = 0; t < N - 1; t++) {
    const y0 = sliceYs[t],   y1 = sliceYs[t + 1];
    const w0 = hw[t],         w1 = hw[t + 1];

    // Front face (z = +d), normal pointing toward camera
    addQuad(
      [-w0, y0, d], [w0, y0, d],
      [w1, y1, d], [-w1, y1, d],
      0, 0, 1
    );
    // Back face (z = -d), winding reversed
    addQuad(
      [w0, y0, -d], [-w0, y0, -d],
      [-w1, y1, -d], [w1, y1, -d],
      0, 0, -1
    );
    // Left side face
    addQuad(
      [-w0, y0, -d], [-w0, y0,  d],
      [-w1, y1,  d], [-w1, y1, -d],
      -1, 0, 0
    );
    // Right side face
    addQuad(
      [w0, y0,  d], [w0, y0, -d],
      [w1, y1, -d], [w1, y1,  d],
      1, 0, 0
    );
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
  // computeVertexNormals averages face normals at shared vertices → smooth shading
  // so light grazes flares and pools in scar concavities
  geo.computeVertexNormals();
  return geo;
}

// ── ObeliskMesh ──────────────────────────────────────────────────────────────

interface ObeliskMeshProps {
  data: ObeliskData;
  colX: number;
  color: string;
  animProgress: number;     // 0→1 load animation
  crownVisible: boolean;    // crown ignition sequencing
  isHovered: boolean;
  otherHovered: boolean;    // another column is hovered — dim this one
  onEnter: () => void;
  onLeave: () => void;
}

function ObeliskMesh({
  data, colX, color, animProgress, crownVisible,
  isHovered, otherHovered, onEnter, onLeave,
}: ObeliskMeshProps) {
  // Width flares emerge slightly ahead of height (1.35x multiplier, clamped to 1)
  const widthProgress = Math.min(1, animProgress * 1.35);

  // Full column body geometry — one row per sparkline point (sculpted surface)
  const bodyGeo = useMemo(
    () => buildColumnGeometry(data, widthProgress),
    [data, widthProgress]
  );

  // Crown strip: top CROWN_ROWS segments only — higher emissive after ignition
  const crownStart = Math.max(0, data.ys.length - 1 - CROWN_ROWS);
  const crownGeo = useMemo(
    () => buildColumnGeometry(data, widthProgress, crownStart),
    [data, widthProgress, crownStart]
  );

  // Clip plane: reveals column from y=0 upward as animProgress goes 0→1
  const clipPlane = useMemo(
    () => new THREE.Plane(new THREE.Vector3(0, -1, 0), 0),
    []
  );
  useEffect(() => {
    clipPlane.constant = data.maxY * animProgress;
  }, [animProgress, data.maxY, clipPlane]);

  const accentColor = useMemo(() => new THREE.Color(color), [color]);
  const opacity = otherHovered ? 0.28 : 1.0;

  // Crown hairline: crisp 1px bright line along the top front edge
  const hairlineGeo = useMemo(() => {
    const wTop = data.halfWidths[data.halfWidths.length - 1];
    const yTop = data.ys[data.ys.length - 1];
    const pts = new Float32Array([
      -wTop, yTop, COL_DEPTH / 2 + 0.006,
       wTop, yTop, COL_DEPTH / 2 + 0.006,
    ]);
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    return g;
  }, [data]);

  // Antenna: thin vertical line above crown for new-high portfolios
  const antennaGeo = useMemo(() => {
    if (!data.isNewHigh) return null;
    const yTop = data.ys[data.ys.length - 1];
    const pts = new Float32Array([0, yTop, 0,  0, yTop + 0.42, 0]);
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    return g;
  }, [data]);

  return (
    <group position={[colX, 0, 0]} rotation={[0, 0, data.lean]}>
      {/* Column body: heavy stone-like obsidian surface */}
      <mesh geometry={bodyGeo} castShadow receiveShadow>
        <meshPhysicalMaterial
          color="#07070d"
          roughness={0.76}
          metalness={0.08}
          clearcoat={0.22}
          clearcoatRoughness={0.5}
          emissive={accentColor}
          emissiveIntensity={isHovered ? 0.07 : 0.022}
          clippingPlanes={[clipPlane]}
          transparent={otherHovered}
          opacity={opacity}
          side={THREE.FrontSide}
        />
      </mesh>

      {/* Crown strip: higher emissive — ignites after body animation completes */}
      {crownVisible && (
        <mesh geometry={crownGeo} castShadow>
          <meshPhysicalMaterial
            color="#0b0b18"
            roughness={0.5}
            metalness={0.14}
            clearcoat={0.32}
            emissive={accentColor}
            emissiveIntensity={isHovered ? 0.62 : 0.36}
            clippingPlanes={[clipPlane]}
            transparent={otherHovered}
            opacity={opacity}
          />
        </mesh>
      )}

      {/* Crown hairline: architectural sharp edge, not a blob */}
      {crownVisible && (
        <lineSegments geometry={hairlineGeo}>
          <lineBasicMaterial
            color={color}
            transparent
            opacity={isHovered ? 0.94 : 0.62}
          />
        </lineSegments>
      )}

      {/* New-high antenna: vertical energy line above crown */}
      {crownVisible && antennaGeo && (
        <lineSegments geometry={antennaGeo}>
          <lineBasicMaterial color={color} transparent opacity={0.42} />
        </lineSegments>
      )}

      {/* Invisible hit box for hover detection — wider than column for easy targeting */}
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
