import { useState } from "react";
import type { WeekRow } from "../api";
import { fmtDay } from "../format";
import { labelStride, useElementWidth } from "../hooks";
import { TRow, Tooltip } from "./Tooltip";

const SERIES = [
  { key: "out_cyclable_pct" as const, name: "Outbound", color: "var(--series-out)" },
  { key: "back_cyclable_pct" as const, name: "Return", color: "var(--series-back)" },
];

/** % of commute legs that were cyclable, week by week through the stay. */
export function WeeklyChart({ weekly }: { weekly: WeekRow[] }) {
  const [wrap, W] = useElementWidth<HTMLDivElement>(480);
  const [hover, setHover] = useState<number | null>(null);

  // Layout adapts to the available width.
  const narrow = W < 420;
  const L = 36, T = 12, B = 26, R = narrow ? 14 : 92;
  const H = Math.round(Math.min(280, Math.max(190, W * 0.5)));
  const n = weekly.length;
  const plotW = W - L - R;
  const step = plotW / Math.max(1, n - 1);
  const x = (i: number) => L + i * step;
  const y = (v: number) => T + ((100 - v) / 100) * (H - T - B);
  const path = (k: (typeof SERIES)[number]["key"]) =>
    weekly.map((w, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(w[k]).toFixed(1)}`).join(" ");
  const stride = labelStride(n, plotW, 52);

  const last = weekly[n - 1];
  const endLabels = !narrow && last && Math.abs(last.out_cyclable_pct - last.back_cyclable_pct) >= 8;

  function onMove(e: React.PointerEvent<SVGRectElement>) {
    const px = e.clientX - e.currentTarget.ownerSVGElement!.getBoundingClientRect().left;
    setHover(Math.max(0, Math.min(n - 1, Math.round((px - L) / step))));
  }
  function onKey(e: React.KeyboardEvent) {
    const cur = hover ?? -1;
    const i = e.key === "ArrowRight" ? Math.min(n - 1, cur + 1) : e.key === "ArrowLeft" ? Math.max(0, cur - 1) : null;
    if (i !== null) { setHover(i); e.preventDefault(); }
  }

  return (
    <div ref={wrap} style={{ position: "relative" }}>
      <div className="legend">
        {SERIES.map((s) => <span key={s.key}><i className="key-line" style={{ background: s.color }} />{s.name}</span>)}
      </div>
      <svg className="chart" width={W} height={H} tabIndex={0} onKeyDown={onKey} onBlur={() => setHover(null)}
           aria-label="Share of cyclable commute legs per week, outbound and return">
        {[0, 25, 50, 75, 100].map((v) => (
          <g key={v}>
            <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke={v === 0 ? "var(--axis)" : "var(--grid)"} />
            <text x={L - 6} y={y(v) + 4} textAnchor="end">{v}%</text>
          </g>
        ))}
        {weekly.map((w, i) => i % stride === 0 && (
          <text key={w.week} x={x(i)} y={H - 6} textAnchor="middle">{fmtDay(w.week_start)}</text>
        ))}
        {SERIES.map((s) => (
          <path key={s.key} d={path(s.key)} fill="none" stroke={s.color} strokeWidth={2}
                strokeLinejoin="round" strokeLinecap="round" />
        ))}
        {last && SERIES.map((s) => (
          <g key={s.key}>
            <circle cx={x(n - 1)} cy={y(last[s.key])} r={4} fill={s.color} stroke="var(--surface-1)" strokeWidth={2} />
            {endLabels && (
              <text className="label-primary" x={x(n - 1) + 10} y={y(last[s.key]) + 4}>
                {s.name} {Math.round(last[s.key])}%
              </text>
            )}
          </g>
        ))}
        {hover !== null && (
          <g pointerEvents="none">
            <line x1={x(hover)} x2={x(hover)} y1={T} y2={H - B} stroke="var(--axis)" />
            {SERIES.map((s) => (
              <circle key={s.key} cx={x(hover)} cy={y(weekly[hover][s.key])} r={4}
                      fill={s.color} stroke="var(--surface-1)" strokeWidth={2} />
            ))}
          </g>
        )}
        <rect x={L - step / 2} y={T} width={plotW + step} height={H - T - B} fill="transparent"
              style={{ touchAction: "pan-y" }}
              onPointerMove={onMove} onPointerDown={onMove} onPointerLeave={() => setHover(null)} />
      </svg>
      {hover !== null && (
        <Tooltip x={x(hover)} y={40} containerWidth={W}>
          <div className="t-title">Week of {fmtDay(weekly[hover].week_start)}</div>
          {SERIES.map((s) => (
            <TRow key={s.key} color={s.color} value={`${weekly[hover][s.key].toFixed(0)}%`} label={`${s.name} cyclable`} />
          ))}
          <TRow value={`${weekly[hover].out_median_feels_c.toFixed(1)} °C`} label="median feels-like, outbound" />
          <TRow value={`${weekly[hover].back_dark_pct.toFixed(0)}%`} label="return in the dark" />
        </Tooltip>
      )}
      <details>
        <summary>Table view</summary>
        <div className="table-scroll">
          <table>
            <thead><tr><th>Week of</th><th>Outbound OK</th><th>Return OK</th><th>Wet/snowing</th><th>Feels-like out</th><th>Return dark</th></tr></thead>
            <tbody>
              {weekly.map((w) => (
                <tr key={w.week}>
                  <td>{fmtDay(w.week_start)}</td><td>{w.out_cyclable_pct}%</td><td>{w.back_cyclable_pct}%</td>
                  <td>{w.wet_pct}%</td><td>{w.out_median_feels_c} °C</td><td>{w.back_dark_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
