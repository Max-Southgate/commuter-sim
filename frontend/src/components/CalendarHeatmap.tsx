import { useRef, useState } from "react";
import type { Climatology } from "../api";
import { fmtWeekday, monthOf, svgPoint } from "../format";
import { TRow, Tooltip } from "./Tooltip";

const CELL = 10, GAP = 2, L = 38, T = 18;
const LEVELS = [
  { v: 0, name: "Neither leg cyclable", color: "var(--seq-0)" },
  { v: 1, name: "One leg cyclable", color: "var(--seq-1)" },
  { v: 2, name: "Both legs cyclable", color: "var(--seq-2)" },
];

/** Every past winter (rows) replayed onto your stay's working days (columns). */
export function CalendarHeatmap({ calendar, perYear }: {
  calendar: Climatology["calendar"]; perYear: NonNullable<Climatology["per_year"]>;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<{ r: number; c: number; px: number; py: number } | null>(null);
  const { years, dates, values } = calendar;
  const W = L + dates.length * CELL + 4;
  const H = T + years.length * CELL + 2;

  const monthStarts = dates
    .map((d, i) => ({ d, i }))
    .filter(({ d, i }) => i === 0 || monthOf(d) !== monthOf(dates[i - 1]));

  function onMove(e: React.PointerEvent<SVGRectElement>) {
    const p = svgPoint(e, W, H);
    const c = Math.floor((p.x - L) / CELL), r = Math.floor((p.y - T) / CELL);
    if (r < 0 || c < 0 || r >= years.length || c >= dates.length || values[r][c] === null) { setHover(null); return; }
    setHover({ r, c, px: (L + c * CELL + CELL / 2) * p.scale, py: (T + r * CELL) * p.scale });
  }

  const hv = hover ? values[hover.r][hover.c] : null;
  return (
    <div ref={wrap} style={{ position: "relative" }}>
      <div className="legend">
        {LEVELS.map((l) => <span key={l.v}><i className="key-rect" style={{ background: l.color }} />{l.name}</span>)}
        <span className="muted">Blank columns are weekends</span>
      </div>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} aria-label="Calendar heatmap of cyclable commute days per historical winter">
        {monthStarts.map(({ d, i }) => (
          <text key={d} x={L + i * CELL} y={11}>{monthOf(d)}</text>
        ))}
        {years.map((y, r) => (r === 0 || r === years.length - 1 || (y % 5 === 0 && years.length - 1 - r >= 3)) && (
          <text key={y} x={L - 6} y={T + r * CELL + CELL - 2} textAnchor="end">{y}</text>
        ))}
        {values.map((row, r) => row.map((v, c) => v !== null && (
          <rect key={`${r}-${c}`} x={L + c * CELL} y={T + r * CELL} width={CELL - GAP} height={CELL - GAP} rx={2}
                fill={LEVELS[v].color} />
        )))}
        {hover && (
          <rect x={L + hover.c * CELL - 1} y={T + hover.r * CELL - 1} width={CELL} height={CELL} rx={3}
                fill="none" stroke="var(--text-primary)" strokeWidth={1.5} pointerEvents="none" />
        )}
        <rect x={L} y={T} width={dates.length * CELL} height={years.length * CELL} fill="transparent"
              onPointerMove={onMove} onPointerLeave={() => setHover(null)} />
      </svg>
      {hover && hv !== null && wrap.current && (
        <Tooltip x={hover.px} y={hover.py + 40} containerWidth={wrap.current.clientWidth}>
          <div className="t-title">{fmtWeekday(dates[hover.c])} 2027, with {years[hover.r]}'s weather</div>
          <TRow kind="rect" color={LEVELS[hv].color} value={`${hv} of 2`} label="legs cyclable" />
        </Tooltip>
      )}
      <details>
        <summary>Table view: cyclable days per winter (scaled to your stay)</summary>
        <table>
          <thead><tr><th>Winter</th><th>Days cyclable both ways</th><th>Cyclable legs</th></tr></thead>
          <tbody>
            {perYear.map((p) => <tr key={p.year}><td>{p.year}</td><td>{p.both_days}</td><td>{p.ok_legs}</td></tr>)}
          </tbody>
        </table>
      </details>
    </div>
  );
}
