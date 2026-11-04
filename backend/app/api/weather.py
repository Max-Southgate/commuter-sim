from __future__ import annotations

from dataclasses import replace

from fastapi import APIRouter, HTTPException, Query

from app.analysis import climatology
from app.config import CyclingThresholds, get_settings

router = APIRouter(prefix="/weather", tags=["weather"])


def _resolve(route_id: str | None):
    s = get_settings()
    try:
        return s, s.route(route_id)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e


def _thresholds(base: CyclingThresholds, **overrides):
    return replace(base, **{k: v for k, v in overrides.items() if v is not None})


@router.get("/climatology")
def get_climatology(
    route: str | None = None,
    min_temp_c: float | None = Query(None, description="feels-like minimum for cycling"),
    max_precip_mm_h: float | None = Query(None, ge=0),
    max_gust_kmh: float | None = Query(None, ge=0),
    max_snow_depth_cm: float | None = Query(None, ge=0),
    since_year: int | None = Query(None, description="only use winters from this year on"),
):
    """Historical 'what would my commutes have been like' summary + calendar grid."""
    settings, r = _resolve(route)
    th = _thresholds(settings.thresholds, min_temp_c=min_temp_c, max_precip_mm_h=max_precip_mm_h,
                     max_gust_kmh=max_gust_kmh, max_snow_depth_cm=max_snow_depth_cm)
    legs = climatology.build_legs(climatology.load_weather_cached(r.id), r, settings, th, since_year)
    return {
        **climatology.summarize(legs, r, settings, th),
        "calendar": climatology.calendar(legs, r),
    }


@router.get("/daylight")
def get_daylight(route: str | None = None):
    settings, r = _resolve(route)
    return {"out_time": r.out_time.strftime("%H:%M"), "back_time": r.back_time.strftime("%H:%M"),
            "commute_minutes": r.commute_minutes, "days": climatology.daylight_table(r, settings)}
