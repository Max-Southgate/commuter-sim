"""CLI entry point for data jobs.

    python -m app.collectors weather-history          # one-off backfill (cached; safe to re-run)
    python -m app.collectors departures               # long-running MVG delay collector
    python -m app.collectors departures --once        # single poll (handy for testing)
    python -m app.collectors departures --ignore-windows
"""
from __future__ import annotations

import argparse
import logging
from logging.handlers import RotatingFileHandler

from app.collectors import departures, weather_history
from app.config import get_settings


def setup_logging(log_file: str | None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        # Rotating UTF-8 file: at most ~3 x 2 MB, so months of collecting can't fill the disk.
        handlers = [RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=2, encoding="utf-8")]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=handlers)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # don't log every single request


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m app.collectors")
    ap.add_argument("--log-file", default=None, help="write logs to this file instead of the console")
    sub = ap.add_subparsers(dest="cmd", required=True)

    wh = sub.add_parser("weather-history", help="backfill historical hourly weather for each route")
    wh.add_argument("--route", default=None)

    dep = sub.add_parser("departures", help="collect live MVG departures/delays")
    dep.add_argument("--once", action="store_true", help="poll once and exit")
    dep.add_argument("--ignore-windows", action="store_true", help="poll regardless of configured time windows")

    args = ap.parse_args()
    setup_logging(args.log_file)
    settings = get_settings()
    logging.info("config: %s", settings.source_file)

    if args.cmd == "weather-history":
        routes = [settings.route(args.route)] if args.route else list(settings.routes.values())
        for r in routes:
            n = weather_history.backfill(settings, r)
            logging.info("route %s: stored %d observations", r.id, n)
    elif args.cmd == "departures":
        if args.once:
            n = departures.poll_once(settings)
            logging.info("stored/updated %d departures", n)
        else:
            departures.run_forever(settings, ignore_windows=args.ignore_windows)


if __name__ == "__main__":
    main()
