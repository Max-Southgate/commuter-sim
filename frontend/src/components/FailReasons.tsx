import { useElementWidth } from "../hooks";

const NAMES: Record<string, string> = {
  snow_on_ground: "Snow on the ground",
  too_cold: "Too cold",
  wet: "Rain",
  snowing: "Falling snow",
  too_windy: "Wind",
};

/** Why non-cyclable legs failed. A leg can fail for several reasons, so bars don't sum to 100%. */
export function FailReasons({ reasons }: { reasons: Record<string, number> }) {
  const [wrap, W] = useElementWidth<HTMLDivElement>(420);
  const narrow = W < 380;
  const ROW = narrow ? 26 : 30, BAR = narrow ? 14 : 16, L = narrow ? 128 : 156, R = 44;
  const rows = Object.entries(reasons).sort((a, b) => b[1] - a[1]);
  const H = rows.length * ROW;
  const w = (v: number) => (v / 100) * Math.max(40, W - L - R);
  return (
    <div ref={wrap}>
      <svg className="chart" width={W} height={H} role="list" aria-label="Reasons commute legs were not cyclable">
        <line x1={L} x2={L} y1={0} y2={H} stroke="var(--axis)" />
        {rows.map(([k, v], i) => {
          const y = i * ROW + (ROW - BAR) / 2;
          const bw = Math.max(0, w(v));
          const r = Math.min(4, bw);
          // square at the baseline, 4px rounded data-end
          const d = `M${L},${y} h${bw - r} a${r},${r} 0 0 1 ${r},${r} v${BAR - 2 * r} a${r},${r} 0 0 1 ${-r},${r} h${-(bw - r)} z`;
          return (
            <g key={k} role="listitem">
              <title>{`${NAMES[k] ?? k}: ${v}% of non-cyclable legs`}</title>
              <text className="label-primary" x={L - 8} y={y + BAR - 3} textAnchor="end">{NAMES[k] ?? k}</text>
              {bw > 0 && <path d={d} fill="var(--series-out)" />}
              <text className="label-primary" x={L + bw + 6} y={y + BAR - 3}>{v.toFixed(0)}%</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
