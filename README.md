# commuter-sim

An interactive site for working out how you'll commute: bike, public transport or car. It combines
historical weather, daylight, live public-transport delays and (later) forecasts, traffic and events.

The first use case is a stay in Munich from 10 Jan to 21 Mar 2027: *is it worth getting a bike, or should I just use MVV?*
Everything is driven by `config/routes.yaml`, so other routes and cities only need a new config entry.

## What works today (Phase 0 + 1)

- **Winter replay:** 31 past winters (Open-Meteo / ERA5 hourly data) are mapped onto your 2027 working days.
  Each outbound and return leg is judged against your own thresholds (feels-like temperature, rain, wind gusts,
  lying snow), and you can adjust them with sliders.
- **Daylight:** shows when your commute legs fall before civil dawn or after civil dusk.
- **MVG delay collector:** polls live departures at your stops during commute hours and stores
  delays, cancellations, replacement buses and incident messages. MVG has no free history,
  so **start this now** to have about two months of data by January.

See the [project plan](#roadmap) for what's next.

## Setup (Windows, [uv](https://docs.astral.sh/uv/), Node 20+)

Python is managed by uv: `backend/.python-version` pins 3.14 and `uv.lock` pins every package.
Run all backend commands from `backend/` with `uv run`; there's no venv to activate.

```powershell
# backend: creates .venv and installs everything, including pytest
cd backend
uv sync

# your route (gitignored)
copy ..\config\routes.example.yaml ..\config\routes.yaml
# edit home/work coordinates, commute times; then find your MVG stops:
uv run python -m app.tools.stops nearby --lat 48.1351 --lon 11.5820
uv run python -m app.tools.stops search "Münchner Freiheit"

# load 31 winters of weather (about 10 s, cached in data/cache)
uv run python -m app.collectors weather-history

# frontend
cd ..\frontend
npm install
```

## Running

```powershell
# API (http://localhost:8000/docs)
cd backend; uv run uvicorn app.main:app --reload

# UI in dev mode (http://localhost:5173, proxies /api to :8000)
cd frontend; npm run dev
# ...or build once and let the API serve it at http://localhost:8000
cd frontend; npm run build

# delay collector (leave running; it only polls during collector.windows on weekdays)
cd backend; uv run python -m app.collectors departures
# or run it in the background at Windows logon: see scripts\run_collector.ps1
```

Tests: `cd backend; uv run pytest`

Packages: `uv add <pkg>` / `uv remove <pkg>` (never `pip install`, which would bypass the lockfile).

## Layout

```
config/            routes.example.yaml (template), routes.yaml (yours, gitignored)
backend/app/
  connectors/      one module per external source (open_meteo, mvg, daylight, ...) returning DataFrames
  collectors/      jobs that call connectors and write to the store (weather backfill, delay poller)
  analysis/        climatology: weather -> commute legs -> summaries
  api/             FastAPI routers, mounted under /api
  store.py         DuckDB (data/commuter.duckdb), short-lived connections so the API and collector can share it
frontend/src/      Vite + React + TS; charts are small hand-written SVG components
data/              gitignored: DuckDB file, raw API response cache, collector log
```

To add a data source, write a connector (fetch → tidy DataFrame), a collector that stores it in
`observations` (long format: source, location, metric, ts, value), and an API route.

## Caveats

- ERA5 weather is on a ~25 km grid. It's representative of the Munich area, not your street, and its snow depth
  includes the countryside. That's why lying snow is a slider and not a hard rule.
- The MVG API is unofficial and undocumented. Poll gently (the default is every 2 minutes, only during commute windows).
- Public holidays aren't excluded from working days yet (planned for the events layer).

## Roadmap

1. ~~Skeleton, weather climatology, daylight, delay collector~~
2. Route baselines: bike, transit and car travel times (BRouter / OpenRouteService / Transitous), a Leaflet map,
   and a cost model (Deutschlandticket vs. buying a used bike, Swapfiets or MVG Rad)
3. Simulator: Monte Carlo over past winters combined with collected delay distributions, giving an overall
   "bike / transit / hybrid" recommendation and the break-even point
4. Live mode: 16-day forecast, a daily "bike or train today?" card, strikes and events
5. Generalise to multiple routes and cities, then deploy
