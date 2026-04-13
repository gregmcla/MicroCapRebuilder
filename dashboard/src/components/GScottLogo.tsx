/** GScott Terminal wordmark — terminal prompt style with neon glow.
 *  "GScott" renders large + bold; "Terminal" renders smaller in accent purple.
 *  Pass `animKey` (increment it) to trigger the typewriter replay.
 */
import { useState, useEffect } from "react";

const TEXT_GSCOTT   = "GScott";
const TEXT_TERMINAL = " Terminal";
const FULL_TEXT     = TEXT_GSCOTT + TEXT_TERMINAL; // 15 chars

// Courier New monospace: char advance ≈ fontSize × 0.6
const FONT_A = 82;   // "GScott"
const FONT_B = 62;   // " Terminal"
const CW_A   = Math.round(FONT_A * 0.6);  // 49px per char
const CW_B   = Math.round(FONT_B * 0.6);  // 37px per char

const TEXT_X  = 168;                           // x where "GScott" starts
const TEXT_Y  = 168;                           // shared baseline
// Cursor left edge after N characters typed
function cursorX(chars: number): number {
  if (chars <= TEXT_GSCOTT.length) return TEXT_X + chars * CW_A;
  return TEXT_X + TEXT_GSCOTT.length * CW_A + (chars - TEXT_GSCOTT.length) * CW_B;
}

// SVG canvas — wide enough for full text + cursor + margins
const VB_W = 760;
const VB_H = 256;

export default function GScottLogo({
  height   = 32,
  animKey,
}: {
  height?:  number;
  animKey?: number;
}) {
  const [chars,  setChars]  = useState(FULL_TEXT.length); // start fully typed
  const [typing, setTyping] = useState(false);

  // When animKey changes → reset and replay
  useEffect(() => {
    if (animKey === undefined) return;
    setChars(0);
    setTyping(true);
  }, [animKey]);

  // Advance one character every 65 ms
  useEffect(() => {
    if (!typing) return;
    if (chars >= FULL_TEXT.length) { setTyping(false); return; }
    const t = setTimeout(() => setChars(c => c + 1), 65);
    return () => clearTimeout(t);
  }, [typing, chars]);

  const displayA = TEXT_GSCOTT.slice(0, Math.min(chars, TEXT_GSCOTT.length));
  const displayB = TEXT_TERMINAL.slice(0, Math.max(0, chars - TEXT_GSCOTT.length));
  const cx       = cursorX(chars);
  const done     = !typing && chars >= FULL_TEXT.length;

  const w = Math.round(height * (VB_W / VB_H));

  return (
    <svg
      viewBox={`0 0 ${VB_W} ${VB_H}`}
      width={w}
      height={height}
      xmlns="http://www.w3.org/2000/svg"
      style={{ display: "block", flexShrink: 0 }}
    >
      <defs>
        <filter id="lg-glow-prompt" x="-40%" y="-60%" width="180%" height="220%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="6" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id="lg-glow-text" x="-10%" y="-30%" width="120%" height="160%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="3.5" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id="lg-glow-terminal" x="-10%" y="-40%" width="120%" height="180%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="2.5" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id="lg-glow-cursor" x="-120%" y="-100%" width="340%" height="300%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="6" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id="lg-glow-scan" x="0%" y="-200%" width="100%" height="500%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="2" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <clipPath id="lg-bounds">
          <rect width={VB_W} height={VB_H}/>
        </clipPath>
      </defs>

      {/* Corner brackets — using accent-adjacent dim tones */}
      <g stroke="#2a1f5a" strokeWidth="1.2" fill="none" opacity="0.8" strokeLinecap="square">
        <polyline points="28,18 28,44 54,44"/>
        <polyline points={`${VB_W-28},18 ${VB_W-28},44 ${VB_W-54},44`}/>
        <polyline points={`28,238 28,212 54,212`}/>
        <polyline points={`${VB_W-28},238 ${VB_W-28},212 ${VB_W-54},212`}/>
      </g>

      {/* Horizontal rule */}
      <line x1="28" y1="192" x2={VB_W-28} y2="192" stroke="#2a1f5a" strokeWidth="0.6" opacity="0.7"/>

      {/* Depth > layers */}
      <text x="52" y="168" fontFamily="'Courier New', Courier, monospace" fontSize="82" fill="#1a1050" opacity="0.5">&gt;&gt;</text>
      <text x="68" y="168" fontFamily="'Courier New', Courier, monospace" fontSize="82" fill="#2e1d80" opacity="0.4">&gt;</text>

      {/* Primary > prompt — new accent #8B5CF6 */}
      <text x="82" y="168" fontFamily="'Courier New', Courier, monospace" fontSize="82" fill="#8B5CF6" filter="url(#lg-glow-prompt)">&gt;</text>

      {/* "GScott" — large, bold, --text-primary */}
      <text
        x={TEXT_X}
        y={TEXT_Y}
        fontFamily="'Courier New', Courier, monospace"
        fontSize={FONT_A}
        fontWeight="bold"
        fill="#F8FAFC"
        letterSpacing="-1"
        filter="url(#lg-glow-text)"
      >
        {displayA}
      </text>

      {/* " Terminal" — smaller, accent purple #8B5CF6 */}
      {displayB.length > 0 && (
        <text
          x={TEXT_X + TEXT_GSCOTT.length * CW_A}
          y={TEXT_Y}
          fontFamily="'Courier New', Courier, monospace"
          fontSize={FONT_B}
          fontWeight="normal"
          fill="#8B5CF6"
          letterSpacing="0"
          filter="url(#lg-glow-terminal)"
        >
          {displayB}
        </text>
      )}

      {/* Cursor — solid while typing, blinking when idle */}
      <rect x={cx} y="96" width="11" height="68" fill="#8B5CF6" filter="url(#lg-glow-cursor)">
        {done ? (
          <animate
            attributeName="opacity"
            values="1;1;0;0;1"
            keyTimes="0;0.45;0.5;0.95;1"
            dur="1.2s"
            repeatCount="indefinite"
          />
        ) : (
          <animate attributeName="opacity" values="1" dur="1s" repeatCount="indefinite"/>
        )}
      </rect>

      {/* Sweeping scan line — accent-tinted */}
      <g clipPath="url(#lg-bounds)" filter="url(#lg-glow-scan)">
        <rect width={VB_W} height="3" fill="#8B5CF6" opacity="0.10">
          <animateTransform attributeName="transform" type="translate" from="0,-4" to={`0,${VB_H+4}`} dur="4s" repeatCount="indefinite"/>
        </rect>
      </g>
    </svg>
  );
}
