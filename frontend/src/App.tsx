import { useEffect, useRef, useState } from "react";
import { api, type Climatology, type Daylight, type Thresholds } from "./api";
import { CalendarHeatmap } from "./components/CalendarHeatmap";
import { DaylightChart } from "./components/DaylightChart";
import { FailReasons } from "./components/FailReasons";
import { TransitCard } from "./components/TransitCard";
import { WeeklyChart } from "./components/WeeklyChart";
import { fmtDay } from "./format";

type Filters = Thresholds & { since_year: number | "" };

const SLIDERS: { key: keyof Thresholds; label: string; min: number; max: number; step: number; unit: string }[] = [
  { key: "min_temp_c", label: "Coldest feels-like I'll ride in", min: -12, max: 6, step: 1, unit: " °C" },
  { key: "max_precip_mm_h", label: "Max rain I'll ride in", min: 0, max: 3, step: 0.1, unit: " mm/h" },
  { key: "max_gust_kmh", label: "Max wind gusts", min: 20, max: 90, step: 5, unit: " km/h" },
  { key: "max_snow_depth_cm", label: "Max lying snow", min: 0, max: 20, step: 1, unit: " cm" },
];

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

  // Slider changes: debounce, refetch, keep the previous frame visible meanwhile.
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

  if (error) return <main><h1>commuter-sim</h1><div className="banner">Couldn't reach the backend: {error}. Is <code>uvicorn app.main:app</code> running on :8000?</div></main>;
  if (!data || !filters) return <main><h1>commuter-sim</h1><p className="muted">Loading…</p></main>;

  const d = data.days, legs = data.legs;
  return (
    <main>
      <h1>Should I get a bike? {data.route.name}</h1>
      <p className="sub">
        {fmtDay(data.period.start)} – {fmtDay(data.period.end)} 2027 · {data.period.commute_days} working days ·
        out {data.route.out_time}, back {data.route.back_time} ({data.route.commute_minutes} min)
        {data.years && <> · replaying {data.years.n} past winters ({data.years.first}–{data.years.last})</>}
      </p>

      {data.using_example_config && (
        <div className="banner">
          Showing <strong>example coordinates</strong>. Copy <code>config/routes.example.yaml</code> to{" "}
          <code>config/routes.yaml</code>, add your home, work and MVG stops, then re-run{" "}
          <code>python -m app.collectors weather-history</code>.
        </div>
      )}

      <div className="filters">
        {SLIDERS.map((s) => (
          <label key={s.key}>
            <span>{s.label}: <output>{filters[s.key]}{s.unit}</output></span>
            <input type="range" min={s.min} max={s.max} step={s.step} value={filters[s.key]}
                   onChange={(e) => setFilters({ ...filters, [s.key]: Number(e.target.value) })} />
          </label>
        ))}
        <label>
          <span>Winters to use</span>
          <select value={filters.since_year}
                  onChange={(e) => setFilters({ ...filters, since_year: e.target.value ? Number(e.target.value) : "" })}>
            <option value="">All ({data.years?.n ?? "–"})</option>
            <option value={2011}>Since 2011</option>
            <option value={2017}>Last 10</option>
            <option value={2022}>Last 5</option>
          </select>
        </label>
      </div>

      {!data.has_data ? (
        <div className="banner">No weather history yet. Run <code>python -m app.collectors weather-history</code> in <code>backend/</code>.</div>
      ) : (
        <div className={loading ? "loading" : ""}>
          <section className="card">
            <div className="hero">
              <div className="hero-value">{d!.expected_both_days.median} <span style={{ fontSize: 24 }}>of {data.period.commute_days}</span></div>
              <div className="hero-label">
                working days you could cycle <strong>both ways</strong> in a typical winter
                (1 in 10 winters: ≤{d!.expected_both_days.p10}; best 1 in 10: ≥{d!.expected_both_days.p90}).
                Counting single legs: about <strong>{d!.expected_ok_legs_median} of {d!.total_legs}</strong> rides.
              </div>
            </div>
            <div className="tiles">
              <div className="tile"><div className="label">Outbound legs cyclable</div><div className="value">{legs!.out.cyclable}%</div><div className="note">median feels-like {legs!.out.median_feels_c} °C</div></div>
              <div className="tile"><div className="label">Return legs cyclable</div><div className="value">{legs!.back.cyclable}%</div><div className="note">median feels-like {legs!.back.median_feels_c} °C</div></div>
              <div className="tile"><div className="label">Return leg in the dark</div><div className="value">{legs!.back.dark}%</div><div className="note">outbound: {legs!.out.dark}%</div></div>
              <div className="tile"><div className="label">Below 0 °C at departure</div><div className="value">{legs!.out.below_zero}%</div><div className="note">of outbound legs (actual air temp)</div></div>
            </div>
          </section>

          <div className="grid-2">
            <section className="card">
              <h2>It gets better towards March</h2>
              <p className="sub">Share of legs cyclable, by week of your stay</p>
              <WeeklyChart weekly={data.weekly!} />
            </section>
            <section className="card">
              <h2>What stops you riding</h2>
              <p className="sub">Share of non-cyclable legs blocked by each reason (a leg can have several)</p>
              <FailReasons reasons={data.fail_reasons_pct!} />
              <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
                Snow depth comes from a ~25 km weather grid (ERA5), so it includes countryside. Munich's main bike routes
                are usually cleared, so consider raising the lying-snow slider.
              </p>
            </section>
          </div>

          <section className="card">
            <h2>Every past winter, replayed on your stay</h2>
            <p className="sub">Each row is one historical winter's weather mapped onto your 2027 working days</p>
            <CalendarHeatmap calendar={data.calendar} perYear={data.per_year!} />
          </section>
        </div>
      )}

      {daylight && (
        <section className="card">
          <h2>Daylight on your commute</h2>
          <DaylightChart data={daylight} />
        </section>
      )}

      <section className="card">
        <h2>Public transport: delay collector</h2>
        <TransitCard />
      </section>
    </main>
  );
}
