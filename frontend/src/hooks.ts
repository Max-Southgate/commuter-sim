import { useEffect, useLayoutEffect, useRef, useState } from "react";

/**
 * Live width of an element. Charts draw at this real pixel width (instead of scaling a
 * fixed drawing), so text stays a constant size and layouts can adapt to the space.
 */
export function useElementWidth<T extends HTMLElement>(fallback = 600) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(fallback);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    setWidth(el.clientWidth);
    const ro = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

export type Theme = "light" | "dark";

/** Light by default; the choice is remembered in localStorage. index.html applies it before first paint. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() =>
    localStorage.getItem("theme") === "dark" ? "dark" : "light",
  );
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);
  return [theme, setTheme] as const;
}

/** Show every k-th label so labels of roughly `labelPx` width never collide in `plotPx`. */
export function labelStride(count: number, plotPx: number, labelPx: number, multipleOf = 1): number {
  const k = Math.max(1, Math.ceil((count * labelPx) / Math.max(1, plotPx)));
  return Math.ceil(k / multipleOf) * multipleOf;
}
