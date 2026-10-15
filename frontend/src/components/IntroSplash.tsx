import { useEffect, useRef, useState } from "react";

import { SyntropixLogo } from "./SyntropixLogo";

/**
 * Start-up animation: a network mesh drifts in, nodes link up as they come near
 * each other with signals running along the links, then the whole mesh pulls
 * together into the Syntropix lattice and the app fades in.
 *
 * Plays on every app start; skipped for reduced motion and in tests.
 * Click, Esc, Enter or Space skips it.
 */
const KEY = "syntropix-intro-seen";
const T_MESH = 1500; // free mesh
const T_FORM = 2600; // nodes travel into the logo
const T_LOGO = 3500; // logo + wordmark settle
const T_END = 4100; // fade out done
const COLORS = ["#22d3ee", "#60a5fa", "#a78bfa", "#e879f9"];

interface Node {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  c: string;
  tx: number; // target in the logo
  ty: number;
  keep: boolean; // part of the final lattice
}

function shouldShow(): boolean {
  if (import.meta.env.MODE === "test") return false;
  try {
    // every app start (a fresh load); moving between pages inside the app doesn't replay it
    return !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return true;
  }
}

/** The logo's node positions (same geometry as SyntropixLogo), in its 200x200 box. */
function latticePoints(): [number, number][] {
  const outer = Array.from({ length: 6 }, (_, i) => {
    const a = (Math.PI / 3) * i - Math.PI / 2;
    return [100 + 62 * Math.cos(a), 100 + 62 * Math.sin(a)] as [number, number];
  });
  const inner = Array.from({ length: 3 }, (_, i) => {
    const a = ((2 * Math.PI) / 3) * i + Math.PI / 6;
    return [100 + 30 * Math.cos(a), 100 + 30 * Math.sin(a)] as [number, number];
  });
  return [...outer, ...inner, [100, 100]];
}

const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);
const clamp = (t: number) => Math.max(0, Math.min(1, t));

export function IntroSplash() {
  const [show, setShow] = useState(shouldShow);
  const [phase, setPhase] = useState<"mesh" | "logo" | "out">("mesh");
  const canvas = useRef<HTMLCanvasElement>(null);
  const logo = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!show) return;
    const done = () => {
      try {
        sessionStorage.setItem(KEY, "1");
      } catch {
        /* ignore */
      }
      setShow(false);
    };
    const skip = (e: KeyboardEvent) => {
      if (["Escape", "Enter", " "].includes(e.key)) done();
    };
    window.addEventListener("keydown", skip);

    const cv = canvas.current;
    const ctx = cv?.getContext("2d");
    if (!cv || !ctx) {
      done();
      return () => window.removeEventListener("keydown", skip);
    }
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let W = 0;
    let H = 0;
    const resize = () => {
      W = window.innerWidth;
      H = window.innerHeight;
      cv.width = W * dpr;
      cv.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    // first guess at where the logo sits; measured from the real element when the mesh starts to form
    let size = 260;
    let cx = W / 2;
    let cy = H / 2 - 80;
    const toScreen = ([x, y]: [number, number]) => [cx + ((x - 100) * size) / 200, cy + ((y - 100) * size) / 200];
    const targets = latticePoints().map(toScreen);
    let aimed = false;
    const aim = () => {
      const box = logo.current?.getBoundingClientRect();
      if (box && box.width > 0) {
        const scale = 0.9; // the logo is scaled to 90% until it appears
        size = box.width / scale;
        cx = box.left + box.width / 2;
        cy = box.top + box.height / 2;
      }
      const pts = latticePoints().map(toScreen);
      nodes.forEach((p, i) => {
        const [x, y] = p.keep ? pts[i]! : [cx + (Math.random() - 0.5) * 24, cy + (Math.random() - 0.5) * 24];
        p.tx = x!;
        p.ty = y!;
      });
    };
    const n = Math.round(Math.min(110, Math.max(55, (W * H) / 14000)));
    const nodes: Node[] = Array.from({ length: n }, (_, i) => {
      const keep = i < targets.length;
      const [tx, ty] = keep ? targets[i]! : [cx + (Math.random() - 0.5) * 30, cy + (Math.random() - 0.5) * 30];
      return {
        x: Math.random() * W,
        y: Math.random() * H,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        r: keep ? 3.2 : 1.2 + Math.random() * 1.8,
        c: COLORS[i % COLORS.length]!,
        tx: tx!,
        ty: ty!,
        keep,
      };
    });
    const pulses: { a: number; b: number; t: number; v: number }[] = [];
    const LINK = Math.min(170, Math.max(110, W / 9));

    const start = performance.now();
    let raf = 0;
    let lastPhase = "mesh";
    const frame = (now: number) => {
      const t = now - start;
      const form = ease(clamp((t - T_MESH) / (T_FORM - T_MESH))); // 0 -> 1 while converging
      const fade = clamp((t - T_LOGO) / (T_END - T_LOGO));
      if (!aimed && t >= T_MESH) {
        aim();
        aimed = true;
      }
      const nextPhase = t < T_FORM ? "mesh" : t < T_LOGO ? "logo" : "out";
      if (nextPhase !== lastPhase) {
        lastPhase = nextPhase;
        setPhase(nextPhase);
      }
      if (t >= T_END) {
        done();
        return;
      }

      ctx.clearRect(0, 0, W, H);
      // background glow
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(W, H) * 0.6);
      g.addColorStop(0, `rgba(124,58,237,${0.18 + 0.12 * form})`);
      g.addColorStop(1, "rgba(7,8,12,0)");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);

      // move: free drift, then spring toward the lattice
      for (const p of nodes) {
        if (form === 0) {
          p.x += p.vx;
          p.y += p.vy;
          if (p.x < 0 || p.x > W) p.vx *= -1;
          if (p.y < 0 || p.y > H) p.vy *= -1;
        } else {
          p.x += (p.tx - p.x) * (0.06 + 0.2 * form);
          p.y += (p.ty - p.y) * (0.06 + 0.2 * form);
        }
      }

      // links by proximity (fade as the mesh condenses)
      const linkAlpha = (1 - form * 0.85) * (1 - fade);
      ctx.lineWidth = 0.8;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i]!;
          const b = nodes[j]!;
          const d = Math.hypot(a.x - b.x, a.y - b.y);
          if (d < LINK) {
            const k = (1 - d / LINK) * linkAlpha;
            const grad = ctx.createLinearGradient(a.x, a.y, b.x, b.y);
            grad.addColorStop(0, hexA(a.c, k * 0.55));
            grad.addColorStop(1, hexA(b.c, k * 0.55));
            ctx.strokeStyle = grad;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
            if (form === 0 && pulses.length < 40 && Math.random() < 0.0016) pulses.push({ a: i, b: j, t: 0, v: 0.015 + Math.random() * 0.02 });
          }
        }
      }

      // signals running along links
      for (let k = pulses.length - 1; k >= 0; k--) {
        const s = pulses[k]!;
        s.t += s.v;
        if (s.t >= 1 || form > 0.6) {
          pulses.splice(k, 1);
          continue;
        }
        const a = nodes[s.a]!;
        const b = nodes[s.b]!;
        const x = a.x + (b.x - a.x) * s.t;
        const y = a.y + (b.y - a.y) * s.t;
        ctx.fillStyle = "rgba(240,249,255,0.95)";
        ctx.shadowColor = "#a78bfa";
        ctx.shadowBlur = 12;
        ctx.beginPath();
        ctx.arc(x, y, 1.8, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      // nodes (the extras dissolve into the core)
      for (const p of nodes) {
        const alpha = (p.keep ? 1 : 1 - form) * (1 - fade);
        if (alpha <= 0.01) continue;
        ctx.fillStyle = hexA(p.c, alpha);
        ctx.shadowColor = p.c;
        ctx.shadowBlur = p.keep ? 14 : 8;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r * (p.keep ? 1 + form * 0.4 : 1), 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.shadowBlur = 0;
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("keydown", skip);
    };
  }, [show]);

  if (!show) return null;
  return (
    <div
      role="presentation"
      onClick={() => {
        try {
          sessionStorage.setItem(KEY, "1");
        } catch {
          /* ignore */
        }
        setShow(false);
      }}
      className={`fixed inset-0 z-[100] bg-[#07080c] cursor-pointer transition-opacity duration-500 ${phase === "out" ? "opacity-0" : "opacity-100"}`}
    >
      <canvas ref={canvas} className="absolute inset-0 w-full h-full" aria-hidden />
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none" style={{ paddingBottom: 0 }}>
        <div ref={logo} className={`transition-all duration-700 ${phase === "mesh" ? "opacity-0 scale-90" : "opacity-100 scale-100"}`} style={{ marginTop: -80 }}>
          <SyntropixLogo size={260} className="drop-shadow-[0_0_40px_rgba(148,125,255,0.45)]" />
        </div>
        <h1
          className={`mt-2 font-headline-xl text-[3rem] font-bold text-on-surface transition-all duration-1000 ${phase === "mesh" ? "opacity-0 tracking-[0.6em]" : "opacity-100 tracking-[0.14em]"}`}
        >
          SYNTRO<span className="bg-gradient-to-r from-[#a78bfa] to-[#e879f9] bg-clip-text text-transparent">PIX</span>
        </h1>
        <p className={`mt-2 font-label-badge text-label-badge text-on-surface-variant uppercase tracking-[0.3em] transition-opacity duration-1000 delay-300 ${phase === "mesh" ? "opacity-0" : "opacity-100"}`}>
          Connecting your skills…
        </p>
      </div>
      <span className="absolute bottom-6 right-6 font-label-annotation text-label-annotation text-outline">Click or press Esc to skip</span>
    </div>
  );
}

function hexA(hex: string, a: number): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${Math.max(0, Math.min(1, a)).toFixed(3)})`;
}
