"""Find MVG station ids to put in config/routes.yaml.

    python -m app.tools.stops nearby --lat 48.1351 --lon 11.5820
    python -m app.tools.stops search "Münchner Freiheit"
"""
from __future__ import annotations

import argparse

from app.connectors.mvg import MVG


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m app.tools.stops")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("nearby")
    n.add_argument("--lat", type=float, required=True)
    n.add_argument("--lon", type=float, required=True)
    s = sub.add_parser("search")
    s.add_argument("query")
    args = ap.parse_args()

    mvg = MVG()
    rows = mvg.nearby_stations(args.lat, args.lon) if args.cmd == "nearby" else mvg.search_stations(args.query)
    for r in rows[:15]:
        dist = f"{r['distanceInMeters']:>5} m  " if "distanceInMeters" in r else ""
        print(f"{dist}{r['globalId']:<16} {r['name']}, {r.get('place', '')}  [{', '.join(r.get('transportTypes', []))}]")


if __name__ == "__main__":
    main()
