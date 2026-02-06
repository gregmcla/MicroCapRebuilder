/** Mommy avatar — sleek silhouette with cyan glow breathing animation. */

export default function MommyAvatar({ size = 48 }: { size?: number }) {
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      {/* Outer glow — breathing animation */}
      <div
        className="absolute inset-0 rounded-full animate-pulse"
        style={{
          background:
            "radial-gradient(circle, rgba(34,211,238,0.25) 0%, rgba(34,211,238,0) 70%)",
          animationDuration: "3s",
        }}
      />

      {/* Avatar circle */}
      <svg
        viewBox="0 0 48 48"
        width={size}
        height={size}
        className="relative"
      >
        {/* Background circle */}
        <circle cx="24" cy="24" r="23" fill="#141920" stroke="#22D3EE" strokeWidth="1.5" strokeOpacity="0.4" />

        {/* Silhouette — stylized female bust */}
        <g fill="#22D3EE" fillOpacity="0.85">
          {/* Hair */}
          <ellipse cx="24" cy="16" rx="9" ry="10" />
          {/* Face overlay */}
          <ellipse cx="24" cy="18" rx="7" ry="8" fill="#141920" />
          {/* Face */}
          <ellipse cx="24" cy="18.5" rx="6.5" ry="7" fill="#22D3EE" fillOpacity="0.85" />
          {/* Hair drape left */}
          <path d="M15 16 Q14 24 16 28 Q18 24 17 18 Z" />
          {/* Hair drape right */}
          <path d="M33 16 Q34 24 32 28 Q30 24 31 18 Z" />
          {/* Neck */}
          <rect x="21" y="25" width="6" height="4" rx="2" />
          {/* Shoulders / bust silhouette */}
          <path d="M14 38 Q14 30 21 29 L27 29 Q34 30 34 38 Z" />
        </g>

        {/* Eye highlights */}
        <circle cx="21" cy="17" r="1" fill="#0B0E14" />
        <circle cx="27" cy="17" r="1" fill="#0B0E14" />
        <circle cx="21.4" cy="16.7" r="0.35" fill="#F1F5F9" />
        <circle cx="27.4" cy="16.7" r="0.35" fill="#F1F5F9" />

        {/* Subtle smile */}
        <path
          d="M21.5 21 Q24 23.5 26.5 21"
          fill="none"
          stroke="#0B0E14"
          strokeWidth="0.8"
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
}
