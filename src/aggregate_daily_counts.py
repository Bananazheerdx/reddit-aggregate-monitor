from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from .reddit_oauth_client import load_config


def parse_iso_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except Exception:
        return None


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def iter_run_files(run_dir: Path) -> list[Path]:
    if not run_dir.exists():
        return []
    return sorted(p for p in run_dir.glob("run-*.json") if p.is_file())


def aggregate_for_day(config_path: str | Path, target_day: date | None = None) -> Path:
    config = load_config(config_path)
    storage = config.get("storage") if isinstance(config.get("storage"), dict) else {}
    run_dir = Path(storage.get("run_dir") or "data/runs")
    aggregate_dir = Path(storage.get("daily_aggregate_dir") or "data/aggregate/daily_counts")

    if target_day is None:
        target_day = datetime.now(timezone.utc).date()

    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "runs_observed": 0,
            "requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "listing_counts": [],
            "latencies_ms": [],
            "http_statuses": defaultdict(int),
        }
    )

    run_files_seen = 0
    for path in iter_run_files(run_dir):
        payload = read_json(path)
        if not payload:
            continue

        if payload.get("schema_name") != "reddit_aggregate_monitor_run":
            continue

        payload_date = parse_iso_date(str(payload.get("date_utc") or ""))
        if payload_date != target_day:
            continue

        run_files_seen += 1
        subreddits = payload.get("subreddits")
        if not isinstance(subreddits, dict):
            continue

        for subreddit, info in subreddits.items():
            if not isinstance(info, dict):
                continue
            bucket = buckets[str(subreddit)]
            bucket["runs_observed"] += 1
            bucket["requests"] += 1

            status = str(info.get("status") or "error")
            if status == "ok":
                bucket["successful_requests"] += 1
            else:
                bucket["failed_requests"] += 1

            try:
                bucket["listing_counts"].append(int(info.get("listing_items_returned") or 0))
            except Exception:
                pass

            latency = info.get("latency_ms")
            if isinstance(latency, int | float):
                bucket["latencies_ms"].append(float(latency))

            http_status = info.get("http_status")
            if http_status is not None:
                bucket["http_statuses"][str(http_status)] += 1

    subreddit_summary: dict[str, Any] = {}
    total_requests = 0
    total_successes = 0
    total_failures = 0

    for subreddit, bucket in sorted(buckets.items()):
        counts = bucket["listing_counts"]
        latencies = bucket["latencies_ms"]
        total_requests += int(bucket["requests"])
        total_successes += int(bucket["successful_requests"])
        total_failures += int(bucket["failed_requests"])

        subreddit_summary[subreddit] = {
            "runs_observed": int(bucket["runs_observed"]),
            "requests": int(bucket["requests"]),
            "successful_requests": int(bucket["successful_requests"]),
            "failed_requests": int(bucket["failed_requests"]),
            "listing_items_returned": {
                "min": min(counts) if counts else None,
                "max": max(counts) if counts else None,
                "mean": round(mean(counts), 3) if counts else None,
                "total_across_runs": sum(counts) if counts else 0,
            },
            "latency_ms": {
                "mean": round(mean(latencies), 3) if latencies else None,
                "max": max(latencies) if latencies else None,
            },
            "http_statuses": dict(sorted(bucket["http_statuses"].items())),
        }

    payload_out = {
        "schema_name": "reddit_aggregate_monitor_daily_counts",
        "schema_version": 1,
        "date_utc": target_day.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": {
            "run_dir": str(run_dir),
            "run_files_seen_for_day": run_files_seen,
        },
        "summary": {
            "subreddits_observed": len(subreddit_summary),
            "requests": total_requests,
            "successful_requests": total_successes,
            "failed_requests": total_failures,
        },
        "subreddits": subreddit_summary,
        "privacy_notes": {
            "aggregate_only": True,
            "contains_post_titles": False,
            "contains_post_selftext": False,
            "contains_authors": False,
            "contains_user_ids": False,
            "contains_comments": False,
            "contains_urls_or_permalinks": False,
            "contains_raw_reddit_response_bodies": False,
        },
    }

    out_path = aggregate_dir / f"{target_day.isoformat()}.json"
    write_json(out_path, payload_out)
    return out_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate run-level Reddit listing metrics into daily counts.")
    parser.add_argument("--config", default="config.yml", help="Path to YAML configuration file.")
    parser.add_argument("--date", default=None, help="UTC date to aggregate, YYYY-MM-DD. Defaults to today UTC.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    target_day = parse_iso_date(args.date) if args.date else None
    if args.date and target_day is None:
        raise SystemExit("--date must be in YYYY-MM-DD format.")
    out_path = aggregate_for_day(args.config, target_day)
    print(f"Wrote daily aggregate metrics: {out_path}")


if __name__ == "__main__":
    main()
