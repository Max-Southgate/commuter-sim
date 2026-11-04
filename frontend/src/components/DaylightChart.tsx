import { useRef, useState } from "react";
import type { Daylight } from "../api";
import { fmtDay, fmtMinutes, svgPoint, toMinutes } from "../format";
import { TRow, Tooltip } from "./Tooltip";

const W = 980, H = 230, L = 44, R = 12, T = 10, B = 24;
const Y0 = 6 * 60, Y1 = 20 * 60; // 06:00 (top) .. 20:00 (bottom) - read like a timetable

/** When is it dark during my commute? Night shaded, commute slots as bands. */
export function DaylightChart({ data }: { data: Daylight }) {
  const wrap = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<{ i: number; px: number } | null>(null);
  const days = data.days;
  const n = days.length;
  const step = (W - L - R) / Math.max(1, n - 1);
  const x = (i: number) => L + i * step;
  const y = (min: number) => T + ((min - Y0) / (Y1 - Y0)) * (H - T - B);

  const dawn = days.map((d) => toMinutes(d.dawn));
  const dusk = days.map((d) => toMinutes(d.dusk));
  const morningDark = `M${x(0)},${y(Y0)} ` + dawn.map((m, i) => `L${x(i)},${y(m)}`).join(" ") + ` L${x(n - 1)},${y(Y0)} Z`;
  const eveningDark = `M${x(0)},${y(Y1)} ` + dusk.map((m, i) => `L${x(i)},${y(m)}`).join(" ") + ` L${x(n - 1)},${y(Y1)} Z`;

  const legs = [
    { name: "Outbound", start: toMinutes(data.out_time), color: "var(--series-out)" },
    { name: "Return", start: toMinutes(data.back_time), color: "var(--series-back)" },
  ];
  const backEnd = legs[1].start + data.commute_minutes;
  const firstLightHome = dusk.findIndex((m) => m >= backEnd);

  function onMove(e: React.PointerEvent<SVGRectElement>) {
    const p = svgPoint(e, W, H);
    const i = Math.max(0, Math.min(n - 1, Math.round((p.x - L) / step)));
    setHover({ i, px: x(i) * p.scale });
  }

  return (
    <div ref={wrap} style={{ position: "relative" }}>
      <p className="sub">
        {firstLightHome > 0
          ? <>You'd ride home in daylight from <strong>{fmtDay(days[firstLightHome].date)}</strong>. Before that, the return leg finishes after civil dusk.</>
          : firstLightHome === 0 ? <>Your return leg is in daylight for the whole stay.</>
          : <>Your return leg is after dusk for the whole stay.</>}
      </p>
      <div className="legend">
        <span><i className="key-rect" style={{ background: "var(--wash-neutral)" }} />Dark (before civil dawn / after civil dusk)</span>
        {legs.map((l) => <span key={l.name}><i className="key-line" style={{ background: l.color }} />{l.name} commute</span>)}
      </div>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} aria-label="Darkness versus commute times across the stay">
        {[6, 8, 10, 12, 14, 16, 18, 20].map((h) => (
          <g key={h}>
            <line x1={L} x2={W - R} y1={y(h * 60)} y2={y(h * 60)} stroke="var(--grid)" />
            <text x={L - 6} y={y(h * 60) + 4} textAnchor="end">{`${String(h).padStart(2, "0")}:00`}</text>
          </g>
        ))}
        <path d={morningDark} fill="var(--wash-neutral)" />
        <path d={eveningDark} fill="var(--wash-neutral)" />
        {legs.map((l) => (
          <g key={l.name}>
            <rect x={L} width={W - L - R} y={y(l.start)} height={y(l.start + data.commute_minutes) - y(l.start)}
                  fill={l.color} opacity={0.12} />
            <line x1={L} x2={W - R} y1={y(l.start)} y2={y(l.start)} stroke={l.color} strokeWidth={2} />
          </g>
        ))}
        {firstLightHome > 0 && (
          <line x1={x(firstLightHome)} x2={x(firstLightHome)} y1={T} y2={H - B} stroke="var(--text-muted)" />
        )}
        {days.map((d, i) => i % 7 === 0 && (
          <text key={d.date} x={x(i)} y={H - 6} textAnchor="middle">{fmtDay(d.date)}</text>
        ))}
        {hover && <line x1={x(hover.i)} x2={x(hover.i)} y1={T} y2={H - B} stroke="var(--axis)" pointerEvents="none" />}
        <rect x={L} y={T} width={W - L - R} height={H - T - B} fill="transparent"
              onPointerMove={onMove} onPointerLeave={() => setHover(null)} />
      </svg>
      {hover && wrap.current && (
        <Tooltip x={hover.px} y={30} containerWidth={wrap.current.clientWidth}>
          <div className="t-title">{fmtDay(days[hover.i].date)}</div>
          <TRow value={days[hover.i].dawn} label="civil dawn" />
          <TRow value={days[hover.i].sunrise} label="sunrise" />
          <TRow value={days[hover.i].sunset} label="sunset" />
          <TRow value={days[hover.i].dusk} label="civil dusk" />
          <TRow color={legs[1].color} value={fmtMinutes(backEnd)} label="you get home" />
        </Tooltip>
      )}
    </div>
  );
}
