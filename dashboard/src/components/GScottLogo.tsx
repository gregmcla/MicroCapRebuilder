/** GScott wordmark — terminal prompt style with neon glow. */

export default function GScottLogo({ height = 32 }: { height?: number }) {
  const w = Math.round(height * (560 / 256));
  return (
    <svg
      viewBox="0 0 560 256"
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
        <filter id="lg-glow-cursor" x="-120%" y="-100%" width="340%" height="300%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="6" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id="lg-glow-scan" x="0%" y="-200%" width="100%" height="500%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="2" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <clipPath id="lg-bounds">
          <rect width="560" height="256"/>
        </clipPath>
      </defs>

      {/* Corner brackets */}
      <g stroke="#2a1f5a" strokeWidth="1.2" fill="none" opacity="0.8" strokeLinecap="square">
        <polyline points="28,18 28,44 54,44"/>
        <polyline points="532,18 532,44 506,44"/>
        <polyline points="28,238 28,212 54,212"/>
        <polyline points="532,238 532,212 506,212"/>
      </g>

      {/* Horizontal rule */}
      <line x1="28" y1="192" x2="532" y2="192" stroke="#2a1f5a" strokeWidth="0.6" opacity="0.7"/>

      {/* Depth > layers */}
      <text x="52" y="168" fontFamily="'Courier New', Courier, monospace" fontSize="82" fill="#1a1050" opacity="0.5">&gt;&gt;</text>
      <text x="68" y="168" fontFamily="'Courier New', Courier, monospace" fontSize="82" fill="#2e1d80" opacity="0.4">&gt;</text>

      {/* Primary > prompt */}
      <text x="82" y="168" fontFamily="'Courier New', Courier, monospace" fontSize="82" fill="#8b6fff" filter="url(#lg-glow-prompt)">&gt;</text>

      {/* GScott logotype */}
      <text x="168" y="168" fontFamily="'Courier New', Courier, monospace" fontSize="82" fontWeight="bold" fill="#eeeeff" letterSpacing="-1" filter="url(#lg-glow-text)">GScott</text>

      {/* Blinking cursor */}
      <rect x="462" y="96" width="11" height="68" fill="#00f5ff" filter="url(#lg-glow-cursor)">
        <animate attributeName="opacity" values="1;1;0;0;1" keyTimes="0;0.45;0.5;0.95;1" dur="1.2s" repeatCount="indefinite"/>
      </rect>

      {/* Sweeping scan line */}
      <g clipPath="url(#lg-bounds)" filter="url(#lg-glow-scan)">
        <rect width="560" height="3" fill="#6040d0" opacity="0.12">
          <animateTransform attributeName="transform" type="translate" from="0,-4" to="0,260" dur="4s" repeatCount="indefinite"/>
        </rect>
      </g>
    </svg>
  );
}
