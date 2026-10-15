/** The Syntropix mark: a hexagonal lattice of glowing skill nodes joined by
 * flowing edges around a spinning core. Pure SVG + CSS animation; motion stops
 * when the user prefers reduced motion. */
const NODE_COLORS = ["#22d3ee", "#60a5fa", "#a78bfa", "#e879f9", "#a78bfa", "#60a5fa"];

export function SyntropixLogo({ size = 220, animated = true, className = "" }: { size?: number; animated?: boolean; className?: string }) {
  const c = 100;
  const R = 62; // outer hexagon radius
  const r = 30; // inner triangle radius
  const outer = Array.from({ length: 6 }, (_, i) => {
    const a = (Math.PI / 3) * i - Math.PI / 2;
    return [c + R * Math.cos(a), c + R * Math.sin(a)] as const;
  });
  const inner = Array.from({ length: 3 }, (_, i) => {
    const a = ((2 * Math.PI) / 3) * i + Math.PI / 6;
    return [c + r * Math.cos(a), c + r * Math.sin(a)] as const;
  });
  const hex = outer.map((p) => p.join(",")).join(" ");
  const tri = inner.map((p) => p.join(",")).join(" ");
  const spokes = outer.map(([x, y], i) => {
    const [ix, iy] = inner[Math.floor(i / 2) % 3]!;
    return { x1: x, y1: y, x2: ix, y2: iy, k: i };
  });

  return (
    <svg
      viewBox="0 0 200 200"
      width={size}
      height={size}
      role="img"
      aria-label="Syntropix logo: a network of connected skills"
      className={`syx-logo ${animated ? "syx-anim" : ""} ${className}`}
    >
      <defs>
        <radialGradient id="syx-bg" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#7c3aed" stopOpacity="0.28" />
          <stop offset="55%" stopColor="#1e1b4b" stopOpacity="0.12" />
          <stop offset="100%" stopColor="#000" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="syx-edge" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#22d3ee" />
          <stop offset="50%" stopColor="#a78bfa" />
          <stop offset="100%" stopColor="#e879f9" />
        </linearGradient>
        <filter id="syx-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2.4" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <style>{`
        .syx-anim .syx-orbit { transform-origin: 100px 100px; animation: syx-spin 40s linear infinite; }
        .syx-anim .syx-orbit2 { transform-origin: 100px 100px; animation: syx-spin 26s linear infinite reverse; }
        .syx-anim .syx-core { transform-origin: 100px 100px; animation: syx-spin 6s linear infinite; }
        .syx-anim .syx-flow { stroke-dasharray: 4 6; animation: syx-dash 2.4s linear infinite; }
        .syx-anim .syx-node { animation: syx-pulse 2.8s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }
        .syx-anim .syx-halo { animation: syx-breathe 5s ease-in-out infinite; transform-origin: 100px 100px; }
        @keyframes syx-spin { to { transform: rotate(360deg); } }
        @keyframes syx-dash { to { stroke-dashoffset: -20; } }
        @keyframes syx-pulse { 0%,100% { opacity: .75; transform: scale(1); } 50% { opacity: 1; transform: scale(1.35); } }
        @keyframes syx-breathe { 0%,100% { opacity: .6; transform: scale(.96); } 50% { opacity: 1; transform: scale(1.04); } }
        @media (prefers-reduced-motion: reduce) { .syx-logo * { animation: none !important; } }
      `}</style>

      <circle className="syx-halo" cx={c} cy={c} r="96" fill="url(#syx-bg)" />
      <g className="syx-orbit" fill="none" stroke="#a78bfa" strokeOpacity="0.18">
        <circle cx={c} cy={c} r="88" strokeDasharray="2 5" />
        <circle cx={c} cy={c - 88} r="1.6" fill="#22d3ee" stroke="none" />
      </g>
      <g className="syx-orbit2" fill="none" stroke="#22d3ee" strokeOpacity="0.14">
        <circle cx={c} cy={c} r="78" />
        <circle cx={c + 78} cy={c} r="1.4" fill="#e879f9" stroke="none" />
      </g>

      {/* lattice */}
      <polygon points={hex} fill="none" stroke="url(#syx-edge)" strokeOpacity="0.55" strokeWidth="1.1" />
      <polygon points={tri} fill="none" stroke="url(#syx-edge)" strokeOpacity="0.5" strokeWidth="1" />
      {spokes.map((s) => (
        <line key={s.k} {...s} stroke="url(#syx-edge)" strokeOpacity="0.4" strokeWidth="0.9" />
      ))}
      {outer.map(([x, y], i) => (
        <line key={`c${i}`} x1={x} y1={y} x2={c} y2={c} stroke="#a78bfa" strokeOpacity="0.16" strokeWidth="0.7" />
      ))}
      <polygon className="syx-flow" points={hex} fill="none" stroke="#e0f2fe" strokeOpacity="0.55" strokeWidth="0.9" />

      {/* core */}
      <circle cx={c} cy={c} r="16" fill="#0b0b14" stroke="#a78bfa" strokeOpacity="0.5" />
      <g className="syx-core" fill="none">
        <circle cx={c} cy={c} r="12" stroke="#22d3ee" strokeWidth="1.4" strokeDasharray="18 8" />
        <circle cx={c} cy={c} r="7.5" stroke="#e879f9" strokeWidth="1.2" strokeDasharray="10 5" />
      </g>
      <circle cx={c} cy={c} r="3.2" fill="#f5f3ff" filter="url(#syx-glow)" />

      {/* nodes */}
      <g filter="url(#syx-glow)">
        {outer.map(([x, y], i) => (
          <circle key={i} className="syx-node" style={{ animationDelay: `${i * 0.45}s` }} cx={x} cy={y} r="4.2" fill={NODE_COLORS[i]} />
        ))}
        {inner.map(([x, y], i) => (
          <circle key={`i${i}`} className="syx-node" style={{ animationDelay: `${0.2 + i * 0.6}s` }} cx={x} cy={y} r="2.8" fill="#c4b5fd" />
        ))}
      </g>
    </svg>
  );
}
