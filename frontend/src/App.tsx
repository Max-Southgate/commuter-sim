import { useEffect, useRef, useState } from "react";
import { api, type Climatology, type Daylight, type Thresholds } from "./api";
import { CalendarHeatmap } from "./components/CalendarHeatmap";
import { DaylightChart } from "./components/DaylightChart";
import { FailReasons } from "./components/FailReasons";
import { TransitCard } from "./components/TransitCard";
import { WeeklyChart } from "./components/WeeklyChart";
import { fmtLongDay } from "./format";
import { useTheme } from "./hooks";

type Filters = Thresholds & { since_year: number | "" };

const SLIDERS: { key: keyof Thresholds; label: string; min: number; max: number; step: number; unit: string }[] = [
  { key: "min_temp_c", label: "Coldest I'll ride in (feels-like)", min: -12, max: 6, step: 1, unit: " °C" },
  { key: "max_precip_mm_h", label: "Most rain I'll ride in", min: 0, max: 3, step: 0.1, unit: " mm/h" },
  { key: "max_gust_kmh", label: "Strongest gusts", min: 20, max: 90, step: 5, unit: " km/h" },
  { key: "max_snow_depth_cm", label: "Deepest snow on the ground", min: 0, max: 20, step: 1, unit: " cm" },
];

// How each blocker reads inside a sentence.
const REASON_PHRASE: Record<string, string> = {
  too_cold: "the cold", snow_on_ground: "snow on the ground", wet: "rain",
  snowing: "falling snow", too_windy: "wind",
};

function ThemeToggle() {
  const [theme, setTheme] = useTheme();
  return (
    <div className="theme" role="group" aria-label="Colour theme">
      <button aria-pressed={theme === "light"} onClick={() => setTheme("light")}>Light</button>
      <button aria-pressed={theme === "dark"} onClick={() => setTheme("dark")}>Dark</button>
    </div>
  );
}

function RouteSign({ from, to, line }: { from: string; to: string; line?: string | null }) {
  return (
    <header className="sign">
      <div className="route" aria-label={`${from} to ${to}${line ? ` on the ${line}` : ""}`}>
        <span className="station">{from}</span>
        <span className="track" aria-hidden="true">{line && <span className="badge">{line}</span>}</span>
        <span className="station">{to}</span>
      </div>
      <ThemeToggle />
    </header>
  );
}

/** The answer, written as sentences built from the data. */
function Answer({ data }: { data: Climatology }) {
  const d = data.days!, n = data.period.commute_days, med = d.expected_both_days.median;
  const reasons = Object.entries(data.fail_reasons_pct ?? {}).sort((a, b) => b[1] - a[1]);
  const weekly = data.weekly ?? [];
  const avg = (w: (typeof weekly)[number]) => Math.round((w.out_cyclable_pct + w.back_cyclable_pct) / 2);
  const first = weekly[0], last = weekly[weekly.length - 1];

  return (
    <>
      <p className="answer">
        {med === 0
          ? <>In a typical winter there isn't one working day you could ride both ways.</>
          : <>In a typical winter you could ride both ways on {med} of your {n} working days.</>}
      </p>
      <p className="prose answer-detail">
        A bad winter leaves {d.expected_both_days.p10}, a good one {d.expected_both_days.p90}.
        {reasons.length > 0 && <> What stops you most is {REASON_PHRASE[reasons[0][0]] ?? reasons[0][0]}, behind {Math.round(reasons[0][1])}% of the rides you'd skip.</>}
        {first && last && <> Single rides get easier through the stay: {avg(first)}% are rideable in the first week, {avg(last)}% in the last.</>}
      </p>
    </>
  );
}

export default function App() {
  const [data, setData] = useState<Climatology | null>(null);
  const [daylight, setDaylight] = useState<Daylight | null>(null);
  const [filters, setFilters] = useState<Filters | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const reqId = useRef(0);

  // First load: defaults come from the backend config.
  useEffect(() => {
    api.climatology({}).then((d) => {
      setData(d);
      setFilters({ ...d.thresholds, since_year: "" });
      setLoading(false);
    }).catch((e) => setError(String(e)));
    api.daylight().then(setDaylight).catch((e) => setError(String(e)));
  }, []);

  // Limit changes: debounce, refetch, keep the previous picture visible meanwhile.
  useEffect(() => {
    if (!filters) return;
    const id = ++reqId.current;
    setLoading(true);
    const t = setTimeout(() => {
      api.climatology({ ...filters, since_year: filters.since_year || undefined })
        .then((d) => { if (id === reqId.current) { setData(d); setLoading(false); } })
        .catch((e) => setError(String(e)));
    }, 250);
    return () => clearTimeout(t);
  }, [filters]);

  if (error) {
    return (
      <main>
        <RouteSign from="commuter-sim" to="" />
        <p className="notice">
          The dashboard can't reach its data service. Start it from the <code>backend</code> folder
          with <code>uv run uvicorn app.main:app</code>, then reload this page.
        </p>
      </main>
    );
  }
  if (!data || !filters) {
    return <main><RouteSign from="commuter-sim" to="" /><p className="prose" style={{ marginTop: 24 }}>Loading your route…</p></main>;
  }

  const r = data.route;
  return (
    <main>
      <RouteSign from={r.home.label || "Home"} to={r.work.label || "Work"} line={r.line} />

      {data.using_example_config && (
        <p className="notice">
          These are example locations. Copy <code>config/routes.example.yaml</code> to <code>config/routes.yaml</code>,
          enter your home, work and stops, then reload the weather with{" "}
          <code>uv run python -m app.collectors weather-history</code>.
        </p>
      )}

      {!data.has_data ? (
        <p className="notice">
          There's no weather history for this route yet. Load it from the <code>backend</code> folder with{" "}
          <code>uv run python -m app.collectors weather-history</code> (about ten seconds), then reload.
        </p>
      ) : (
        <div className={loading ? "loading" : ""}>
          <Answer data={data} />
          <p className="meta">
            Leaving at {r.out_time} and heading home at {r.back_time}, {r.commute_minutes} minutes each way,
            from {fmtLongDay(data.period.start)} to {fmtLongDay(data.period.end)} 2027.
            {data.years && <> Based on the weather of {data.years.n} winters, {data.years.first} to {data.years.last}.</>}
          </p>

          <section className="limits" aria-labelledby="limits-h">
            <h2 id="limits-h">Your limits</h2>
            <div className="filters">
              {SLIDERS.map((s) => (
                <label key={s.key}>
                  <span>{s.label}: <output>{filters[s.key]}{s.unit}</output></span>
                  <input type="range" min={s.min} max={s.max} step={s.step} value={filters[s.key]}
                         onChange={(e) => setFilters({ ...filters, [s.key]: Number(e.target.value) })} />
                </label>
              ))}
              <label>
                <span>Which winters</span>
                <select value={filters.since_year}
                        onChange={(e) => setFilters({ ...filters, since_year: e.target.value ? Number(e.target.value) : "" })}>
                  <option value="">All of them</option>
                  <option value={2011}>Since 2011</option>
                  <option value={2017}>The last 10</option>
                  <option value={2022}>The last 5</option>
                </select>
              </label>
            </div>
          </section>

          <section aria-labelledby="winters-h">
            <h2 id="winters-h">Every winter, replayed on your working days</h2>
            <p className="sub">
              Each row is one winter. Each square is one of your working days, coloured by how many of its
              two rides you could have cycled.
            </p>
            <CalendarHeatmap calendar={data.calendar} perYear={data.per_year!} />
          </section>

          <div className="pair">
            <section aria-labelledby="weekly-h">
              <h2 id="weekly-h">Week by week</h2>
              <p className="sub">Share of rides you could have cycled, through your stay.</p>
              <WeeklyChart weekly={data.weekly!} />
            </section>
            <section aria-labelledby="reasons-h">
              <h2 id="reasons-h">What stops you</h2>
              <p className="sub">
                Of the rides you'd skip, how many each condition rules out. One ride can fail on several counts.
              </p>
              <FailReasons reasons={data.fail_reasons_pct!} />
              <p className="sub" style={{ fontSize: 14, marginTop: 12 }}>
                Snow depth comes from a 25 km weather grid that includes the countryside. Munich clears its main
                bike routes, so you may want to allow more snow than this suggests.
              </p>
            </section>
          </div>
        </div>
      )}

      {daylight && (
        <section className="section" aria-labelledby="light-h">
          <h2 id="light-h">Daylight on your rides</h2>
          <DaylightChart data={daylight} />
        </section>
      )}

      <section className="section" aria-labelledby="transit-h">
        <h2 id="transit-h">{r.line ? `The ${r.line} so far` : "Public transport so far"}</h2>
        <TransitCard />
      </section>
    </main>
  );
}
