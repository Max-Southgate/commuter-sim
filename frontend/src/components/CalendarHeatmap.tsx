import { useState } from "react";
import type { Climatology } from "../api";
import { fmtWeekday, monthOf } from "../format";
import { useElementWidth } from "../hooks";
import { TRow, Tooltip } from "./Tooltip";

const GAP = 2, L = 38, T = 18;
const MIN_CELL = 7, MAX_CELL = 16; // below MIN_CELL the grid scrolls sideways instead of shrinking
const LEVELS = [
  { v: 0, name: "Neither ride", color: "var(--seq-0)" },
  { v: 1, name: "One ride", color: "var(--seq-1)" },
  { v: 2, name: "Both rides", color: "var(--seq-2)" },
];

/** Every past winter (rows) replayed onto your stay's working days (columns). */
export function CalendarHeatmap({ calendar, perYear }: {
  calendar: Climatology["calendar"]; perYear: NonNullable<Climatology["per_year"]>;
}) {
  const [wrap, avail] = useElementWidth<HTMLDivElement>(900);
  const [hover, setHover] = useState<{ r: number; c: number } | null>(null);
  const { years, dates, values } = calendar;

  // Cells grow to fill wide screens and shrink on narrow ones, within readable limits.
  const CELL = Math.max(MIN_CELL, Math.min(MAX_CELL, (avail - L - 4) / Math.max(1, dates.length)));
  const W = L + dates.length * CELL + 4;
  const H = T + years.length * CELL + 2;
  const yearEvery = CELL >= 12 ? 2 : 5;

  const monthStarts = dates
    .map((d, i) => ({ d, i }))
    .filter(({ d, i }) => i === 0 || monthOf(d) !== monthOf(dates[i - 1]));

  function onMove(e: React.PointerEvent<SVGRectElement>) {
    const rect = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
    const c = Math.floor((e.clientX - rect.left - L) / CELL), r = Math.floor((e.clientY - rect.top - T) / CELL);
    if (r < 0 || c < 0 || r >= years.length || c >= dates.length || values[r][c] === null) { setHover(null); return; }
    setHover({ r, c });
  }

  const hv = hover ? values[hover.r][hover.c] : null;
  return (
    <div ref={wrap}>
      <div className="legend">
        {LEVELS.map((l) => <span key={l.v}><i className="key-rect" style={{ background: l.color }} />{l.name}</span>)}
        <span className="muted">Blank columns are weekends</span>
      </div>
      {/* Only becomes a sideways scroller when the grid can't fit (cells at their minimum size). */}
      <div className={W > avail ? "table-scroll" : undefined}>
        <div style={{ position: "relative", width: W }}>
          <svg className="chart" width={W} height={H} aria-label="Calendar heatmap of cyclable commute days per historical winter">
            {monthStarts.map(({ d, i }) => (
              <text key={d} x={L + i * CELL} y={11}>{monthOf(d)}</text>
            ))}
            {years.map((y, r) => (r === 0 || r === years.length - 1 || (y % yearEvery === 0 && years.length - 1 - r >= 3)) && (
              <text key={y} x={L - 6} y={T + r * CELL + CELL - 3} textAnchor="end">{y}</text>
            ))}
            {/* Winters arrive in order, oldest first: the page's one entrance animation. */}
            <g className="cells">
              {values.map((row, r) => (
                <g key={years[r]} style={{ animationDelay: `${r * 28}ms` }}>
                  {row.map((v, c) => v !== null && (
                    <rect key={c} x={L + c * CELL} y={T + r * CELL} width={CELL - GAP} height={CELL - GAP}
                          rx={2} fill={LEVELS[v].color} />
                  ))}
                </g>
              ))}
            </g>
            {hover && (
              <rect x={L + hover.c * CELL - 1} y={T + hover.r * CELL - 1} width={CELL} height={CELL} rx={3}
                    fill="none" stroke="var(--text-primary)" strokeWidth={1.5} pointerEvents="none" />
            )}
            <rect x={L} y={T} width={dates.length * CELL} height={years.length * CELL} fill="transparent"
                  onPointerMove={onMove} onPointerDown={onMove} onPointerLeave={() => setHover(null)} />
          </svg>
          {hover && hv !== null && (
            <Tooltip x={L + hover.c * CELL + CELL / 2} containerWidth={W}
                     y={hover.r > years.length / 2 ? T + hover.r * CELL - 62 : T + hover.r * CELL + CELL + 6}>
              <div className="t-title">{fmtWeekday(dates[hover.c])} 2027, with {years[hover.r]}'s weather</div>
              <TRow kind="rect" color={LEVELS[hv].color} value={`${hv} of 2`} label="legs cyclable" />
            </Tooltip>
          )}
        </div>
      </div>
      <details>
        <summary>Table view: cyclable days per winter (scaled to your stay)</summary>
        <div className="table-scroll">
          <table>
            <thead><tr><th>Winter</th><th>Days cyclable both ways</th><th>Cyclable legs</th></tr></thead>
            <tbody>
              {perYear.map((p) => <tr key={p.year}><td>{p.year}</td><td>{p.both_days}</td><td>{p.ok_legs}</td></tr>)}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
