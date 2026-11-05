// Typed client for the FastAPI backend (see backend/app/api).

export interface Thresholds {
  min_temp_c: number;
  max_precip_mm_h: number;
  max_gust_kmh: number;
  max_snow_depth_cm: number;
}

export interface LegStats {
  wet: number; snowing: number; snow_on_ground: number; below_zero: number;
  too_cold: number; too_windy: number; dark: number; cyclable: number;
  median_feels_c: number; median_temp_c: number;
}

export interface WeekRow {
  week: number; week_start: string;
  out_cyclable_pct: number; back_cyclable_pct: number;
  out_dark_pct: number; back_dark_pct: number;
  out_median_feels_c: number; back_median_feels_c: number;
  wet_pct: number;
}

export interface Climatology {
  route: {
    id: string; name: string; line: string | null;
    home: { lat: number; lon: number; label: string }; work: { lat: number; lon: number; label: string };
    out_time: string; back_time: string; commute_minutes: number;
  };
  period: { start: string; end: string; commute_days: number };
  thresholds: Thresholds;
  using_example_config: boolean;
  has_data: boolean;
  years?: { first: number; last: number; n: number };
  legs?: { out: LegStats; back: LegStats };
  days?: {
    both_cyclable_pct: number; one_cyclable_pct: number; none_cyclable_pct: number;
    expected_both_days: { p10: number; median: number; p90: number };
    expected_ok_legs_median: number; total_legs: number;
  };
  per_year?: { year: number; both_days: number; ok_legs: number }[];
  weekly?: WeekRow[];
  fail_reasons_pct?: Record<string, number>;
  calendar: { years: number[]; dates: string[]; values: (number | null)[][] };
}

export interface DaylightDay { date: string; dawn: string; sunrise: string; sunset: string; dusk: string }
export interface Daylight { out_time: string; back_time: string; commute_minutes: number; days: DaylightDay[] }

export interface CollectorStatus {
  stations: { station_id: string; polls: number; failures: number; last_poll_utc: string; first_poll_utc: string }[];
  departures: number;
  first_planned_utc: string | null;
  last_planned_utc: string | null;
}

export interface DelayLine {
  station_id: string; station_name: string | null; label: string; transport_type: string; departures: number;
  cancelled_pct: number; replacement_bus_pct: number;
  delay_p50: number | null; delay_p90: number | null; late_5min_pct: number;
}

async function get<T>(path: string, params: Record<string, string | number | undefined> = {}): Promise<T> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") qs.set(k, String(v));
  const res = await fetch(`/api${path}${qs.size ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(`${path}: ${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  climatology: (p: Partial<Thresholds> & { since_year?: number }) => get<Climatology>("/weather/climatology", p),
  daylight: () => get<Daylight>("/weather/daylight"),
  collectorStatus: () => get<CollectorStatus>("/transit/collector-status"),
  delays: () => get<{ lines: DelayLine[]; note?: string }>("/transit/delays"),
};
