"""Shared plumbing for connectors.

A connector knows how to talk to ONE external source and return tidy pandas data.
It never writes to the store itself - collectors/loaders do that - which keeps
connectors trivially testable with a fake HTTP transport.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import httpx

from app import config

log = logging.getLogger(__name__)

USER_AGENT = "commuter-sim/0.1 (personal commute research project)"


def make_client(transport: httpx.BaseTransport | None = None, timeout: float = 30.0) -> httpx.Client:
    return httpx.Client(
        transport=transport,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )


class JsonCache:
    """Caches raw API responses on disk so historical fetches only ever happen once."""

    def __init__(self, namespace: str, root: Path | None = None):
        self.dir = (root or config.DATA_DIR / "cache") / namespace
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, url: str, params: dict) -> Path:
        key = json.dumps([url, sorted(params.items())], default=str)
        return self.dir / (hashlib.sha1(key.encode()).hexdigest()[:20] + ".json")

    def get(self, url: str, params: dict) -> Any | None:
        p = self._path(url, params)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return None

    def put(self, url: str, params: dict, data: Any) -> None:
        self._path(url, params).write_text(json.dumps(data), encoding="utf-8")


def get_json(client: httpx.Client, url: str, params: dict, cache: JsonCache | None = None) -> Any:
    if cache is not None and (hit := cache.get(url, params)) is not None:
        return hit
    r = client.get(url, params=params)
    r.raise_for_status()
    data = r.json()
    if cache is not None:
        cache.put(url, params, data)
    return data
