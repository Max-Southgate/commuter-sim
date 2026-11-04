import { useEffect, useState } from "react";
import { api, type CollectorStatus, type DelayLine } from "../api";

/** Status of the background MVG delay collector + what it has seen so far. */
export function TransitCard() {
  const [status, setStatus] = useState<CollectorStatus | null>(null);
  const [lines, setLines] = useState<DelayLine[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.collectorStatus(), api.delays()])
      .then(([s, d]) => { setStatus(s); setLines(d.lines); })
      .catch((e) => setErr(String(e)));
  }, []);

  if (err) return <p className="muted">{err}</p>;
  if (!status) return <p className="muted">Loading…</p>;
  const last = status.stations.map((s) => s.last_poll_utc).sort().at(-1);
  return (
    <>
      <p className="sub">
        {status.departures.toLocaleString()} departures recorded
        {last ? <> · last poll {last.slice(0, 16).replace("T", " ")} UTC</> : <> · collector hasn't run yet</>}.
        {" "}There's no free archive of MVG delays, so this builds your own history. Keep it running until you arrive.
      </p>
      {lines.length > 0 && (
        <table>
          <thead>
            <tr><th>Line</th><th>Departures</th><th>Median delay</th><th>90th pct delay</th><th>≥5 min late</th><th>Cancelled</th></tr>
          </thead>
          <tbody>
            {lines.map((l) => (
              <tr key={`${l.station_id}-${l.label}`}>
                <td>{l.label} <span className="muted">{l.transport_type}</span></td>
                <td>{l.departures}</td>
                <td>{l.delay_p50 ?? "–"} min</td>
                <td>{l.delay_p90 ?? "–"} min</td>
                <td>{l.late_5min_pct}%</td>
                <td>{l.cancelled_pct}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
