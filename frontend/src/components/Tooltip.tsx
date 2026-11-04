import type { ReactNode } from "react";

/** Positioned inside a `position: relative` chart wrapper. Flips left near the right edge. */
export function Tooltip({ x, y, containerWidth, children }: {
  x: number; y: number; containerWidth: number; children: ReactNode;
}) {
  const flip = x > containerWidth * 0.62;
  return (
    <div
      className="tooltip"
      role="status"
      style={{
        top: y,
        left: flip ? undefined : x + 14,
        right: flip ? containerWidth - x + 14 : undefined,
      }}
    >
      {children}
    </div>
  );
}

export function TRow({ color, value, label, kind = "line" }: {
  color?: string; value: ReactNode; label: ReactNode; kind?: "line" | "rect";
}) {
  return (
    <div className="t-row">
      {color && <i className={kind === "line" ? "key-line" : "key-rect"} style={{ background: color }} />}
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}
