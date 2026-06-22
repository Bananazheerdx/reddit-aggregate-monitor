from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .reddit_oauth_client import RedditClientConfig, RedditOAuthClient, load_config


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def run_id_from_datetime(value: datetime) -> str:
    return value.strftime("run-%Y%m%dT%H%M%SZ")


def ensure_directory(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_subreddit_allowlist(config: dict[str, Any]) -> list[str]:
    raw = config.get("subreddits")
    if not isinstance(raw, list) or not raw:
        raise ValueError("Config must include a non-empty 'subreddits' allowlist.")

    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        name = str(item or "").strip()
        if name.lower().startswith("r/"):
            name = name[2:]
        if not name:
            continue
        key = name.lower()
        if key not in seen:
            out.append(name)
            seen.add(key)

    if not out:
        raise ValueError("Subreddit allowlist is empty after normalization.")
    return out


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def maybe_write_debug_metadata(config: dict[str, Any], run_payload: dict[str, Any]) -> None:
    debug_config = config.get("debug_cache") if isinstance(config.get("debug_cache"), dict) else {}
    enabled = bool(debug_config.get("enabled", False))
    if not enabled:
        return

    storage = config.get("storage") if isinstance(config.get("storage"), dict) else {}
    debug_dir = ensure_directory(storage.get("debug_cache_dir") or "data/raw_cache/debug_metadata")

    # This is not a raw Reddit response cache. It contains request metadata only.
    debug_payload = {
        "schema_name": "debug_request_metadata",
        "schema_version": 1,
        "created_at": iso_utc_now(),
        "run_id": run_payload.get("run_id"),
        "subreddits": {
            name: {
                "status": info.get("status"),
                "listing_items_returned": info.get("listing_items_returned"),
                "http_status": info.get("http_status"),
                "latency_ms": info.get("latency_ms"),
                "rate_limit": info.get("rate_limit"),
            }
            for name, info in (run_payload.get("subreddits") or {}).items()
            if isinstance(info, dict)
        },
    }
    write_json(debug_dir / f"{run_payload['run_id']}.json", debug_payload)


def collect_once(config_path: str | Path) -> Path:
    config = load_config(config_path)
    client_config = RedditClientConfig.from_mapping(config)
    client = RedditOAuthClient(client_config)
    subreddits = load_subreddit_allowlist(config)

    started = utc_now()
    run_id = run_id_from_datetime(started)

    results: dict[str, Any] = {}
    for subreddit in subreddits:
        result = client.fetch_public_new_listing_count(subreddit)
        results[result.subreddit] = result.to_dict()

    ended = utc_now()
    successes = sum(1 for item in results.values() if item.get("status") == "ok")
    failures = len(results) - successes

    payload: dict[str, Any] = {
        "schema_name": "reddit_aggregate_monitor_run",
        "schema_version": 1,
        "run_id": run_id,
        "started_at": started.isoformat().replace("+00:00", "Z"),
        "ended_at": ended.isoformat().replace("+00:00", "Z"),
        "date_utc": started.date().isoformat(),
        "access_mode": "oauth_only",
        "request_scope": "read_only_public_listing_counts",
        "subreddit_allowlist": subreddits,
        "summary": {
            "subreddits_attempted": len(subreddits),
            "subreddits_successful": successes,
            "subreddits_failed": failures,
            "api_requests_attempted": len(subreddits),
        },
        "subreddits": results,
        "privacy_notes": {
            "stores_post_titles": False,
            "stores_post_selftext": False,
            "stores_authors": False,
            "stores_user_ids": False,
            "stores_comments": False,
            "stores_urls_or_permalinks": False,
            "stores_raw_reddit_response_bodies": False,
        },
    }

    storage = config.get("storage") if isinstance(config.get("storage"), dict) else {}
    run_dir = ensure_directory(storage.get("run_dir") or "data/runs")
    out_path = run_dir / f"{run_id}.json"
    write_json(out_path, payload)
    maybe_write_debug_metadata(config, payload)
    return out_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect one run of OAuth-only public Reddit listing counts.")
    parser.add_argument("--config", default="config.yml", help="Path to YAML configuration file.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    out_path = collect_once(args.config)
    print(f"Wrote aggregate run metrics: {out_path}")


if __name__ == "__main__":
    main()
