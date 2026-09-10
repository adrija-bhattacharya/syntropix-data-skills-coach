import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useTheme } from "../lib/theme";

interface Cmd {
  label: string;
  hint?: string;
  run: () => void;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const nav = useNavigate();
  const { theme, setTheme } = useTheme();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) {
      setQ("");
      setSel(0);
      queueMicrotask(() => inputRef.current?.focus());
    }
  }, [open]);

  if (!open) return null;

  const go = (path: string) => () => {
    nav(path);
    setOpen(false);
  };
  const cmds: Cmd[] = [
    { label: "New goal", hint: "home", run: go("/") },
    { label: "Teacher console", hint: "constraints & Pareto", run: go("/teacher") },
    {
      label: theme === "light" ? "Switch to dark" : "Switch to light",
      hint: "theme",
      run: () => {
        setTheme(theme === "light" ? "dark" : "light");
        setOpen(false);
      },
    },
  ];
  const list = cmds.filter((c) => c.label.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="cmdk-scrim" onMouseDown={() => setOpen(false)}>
      <div className="cmdk" role="dialog" aria-label="Command palette" onMouseDown={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          placeholder="Type a command…"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setSel(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") setSel((s) => Math.min(s + 1, list.length - 1));
            else if (e.key === "ArrowUp") setSel((s) => Math.max(s - 1, 0));
            else if (e.key === "Enter") list[sel]?.run();
          }}
        />
        <ul>
          {list.map((c, i) => (
            <li
              key={c.label}
              aria-selected={i === sel}
              onMouseEnter={() => setSel(i)}
              onClick={() => c.run()}
            >
              <span>{c.label}</span>
              {c.hint && <span style={{ marginLeft: "auto", color: "var(--ink-2)", fontSize: 12 }}>{c.hint}</span>}
            </li>
          ))}
          {list.length === 0 && <li style={{ color: "var(--ink-2)" }}>No matches</li>}
        </ul>
      </div>
    </div>
  );
}
