import { useEffect, useState } from "react";
import { api, type CollectorStatus, type DelayLine } from "../api";
import { fmtLongDay } from "../format";

const fmtMin = (v: number | null) => (v === null ? "–" : `${Math.round(v)} min`);

/** What the background MVG delay collector has recorded at your stops so far. */
export function TransitCard() {
  const [status, setStatus] = useState<CollectorStatus | null>(null);
  const [lines, setLines] = useState<DelayLine[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.collectorStatus(), api.delays()])
      .then(([s, d]) => { setStatus(s); setLines(d.lines); })
      .catch((e) => setErr(String(e)));
  }, []);

  if (err) return <p className="sub">The delay figures couldn't be loaded: {err}</p>;
  if (!status) return <p className="sub">Loading delays…</p>;

  if (status.departures === 0) {
    return (
      <p className="sub">
        Nothing recorded yet. Start the collector from the <code>backend</code> folder with{" "}
        <code>uv run python -m app.collectors departures</code>. During commute hours the first delays
        appear here within two minutes.
      </p>
    );
  }

  const since = status.first_planned_utc ? fmtLongDay(status.first_planned_utc.slice(0, 10)) : null;
  return (
    <>
      <p className="sub">
        {status.departures.toLocaleString()} departures recorded at your stops{since && <> since {since}</>}.
        MVG keeps no delay history, so the collector on your computer builds it. Leave it running until you arrive.
      </p>
      {lines.length > 0 && (
        <div className="table-scroll">
          <table>
            <thead>
              <tr><th>Line</th><th className="name">From</th><th>Departures</th><th>Typical delay</th><th>Bad day (90th pct)</th><th>5+ min late</th><th>Cancelled</th></tr>
            </thead>
            <tbody>
              {lines.map((l) => (
                <tr key={`${l.station_id}-${l.label}`}>
                  <td><span className={`chip ${l.transport_type.toLowerCase()}`}>{l.label}</span></td>
                  <td className="name">{l.station_name ?? l.station_id}</td>
                  <td>{l.departures}</td>
                  <td>{fmtMin(l.delay_p50)}</td>
                  <td>{fmtMin(l.delay_p90)}</td>
                  <td>{Math.round(l.late_5min_pct)}%</td>
                  <td>{Math.round(l.cancelled_pct)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
