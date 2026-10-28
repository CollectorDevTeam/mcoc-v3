#!/usr/bin/env python3
"""Inspect live MCOCHub payload shapes using the repo-local settings.

This intentionally avoids importing redbot so it can run in a lightweight local
check environment while still validating the real Collector API schema.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
LOCAL_SETTINGS = ROOT / "mcoc" / "local_settings.py"

if not LOCAL_SETTINGS.exists():
    raise FileNotFoundError(f"Expected local settings at {LOCAL_SETTINGS}")

spec = importlib.util.spec_from_file_location("mcoc_local_settings", LOCAL_SETTINGS)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load {LOCAL_SETTINGS}")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

API_KEY = getattr(mod, "MCOCHUBAPI", None)
ENDPOINTS = getattr(mod, "ENDPOINTS", ["champions", "tags", "immunities", "abilities", "aw"])
BASE_URL = "https://mcochub.insaneskull.com/api/v1"


def fetch_json(endpoint: str) -> Any:
    url = f"{BASE_URL}/{endpoint}?api_key={API_KEY}"
    req = request.Request(url, headers={"Accept": "application/json"})
    with request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def summarize(value: Any, depth: int = 0, max_items: int = 5) -> str:
    indent = "  " * depth
    if isinstance(value, dict):
        keys = list(value.keys())[:max_items]
        rest = max(0, len(value) - max_items)
        if rest:
            suffix = f" ... (+{rest} more)"
        else:
            suffix = ""
        return f"dict[{len(value)}] keys={keys}{suffix}"
    if isinstance(value, list):
        if not value:
            return "list[]"
        first = value[0]
        return f"list[{len(value)}] first_type={type(first).__name__} sample={summarize(first, depth + 1, max_items)}"
    if isinstance(value, str):
        return f"str[{len(value)}] {value[:80]}"
    if isinstance(value, (int, float, bool)):
        return str(value)
    return type(value).__name__


if __name__ == "__main__":
    if not API_KEY:
        raise SystemExit("MCOCHUBAPI is not defined in mcoc/local_settings.py")

    print(f"Using API key prefix: {API_KEY[:6]}...")
    for endpoint in ENDPOINTS:
        print(f"\n=== {endpoint} ===")
        try:
            payload = fetch_json(endpoint)
            print(summarize(payload))
            if isinstance(payload, dict):
                items = list(payload.items())[:3]
                for key, value in items:
                    print(f"  key={key!r} -> {summarize(value)}")
                if payload:
                    first_key, first_value = next(iter(payload.items()))
                    if isinstance(first_value, dict):
                        print("  first_value_keys=", list(first_value.keys())[:15])
                    elif isinstance(first_value, list) and first_value:
                        print("  first_item_type=", type(first_value[0]).__name__)
                        if isinstance(first_value[0], dict):
                            print("  first_item_keys=", list(first_value[0].keys())[:15])
            elif isinstance(payload, list) and payload:
                print("  first_item_type=", type(payload[0]).__name__)
                if isinstance(payload[0], dict):
                    print("  first_item_keys=", list(payload[0].keys())[:15])
        except error.HTTPError as exc:
            print(f"HTTP {exc.code}: {exc.reason}")
            print(exc.read(400).decode("utf-8", errors="replace"))
        except Exception as exc:  # pragma: no cover
            print(f"ERROR: {type(exc).__name__}: {exc}")
