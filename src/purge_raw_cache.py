from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .reddit_oauth_client import load_config


def get_debug_cache_dir(config: dict[str, Any]) -> Path:
    storage = config.get("storage") if isinstance(config.get("storage"), dict) else {}
    return Path(storage.get("debug_cache_dir") or "data/raw_cache/debug_metadata")


def get_retention_hours(config: dict[str, Any], override: float | None = None) -> float:
    if override is not None:
        return float(override)
    retention = config.get("retention") if isinstance(config.get("retention"), dict) else {}
    return float(retention.get("debug_cache_hours") or 24)


def purge_debug_cache(config_path: str | Path, *, older_than_hours: float | None = None, dry_run: bool = False) -> dict[str, Any]:
    config = load_config(config_path)
    cache_dir = get_debug_cache_dir(config)
    retention_hours = get_retention_hours(config, older_than_hours)

    now_ts = datetime.now(timezone.utc).timestamp()
    cutoff_age_seconds = retention_hours * 3600.0

    result = {
        "cache_dir": str(cache_dir),
        "retention_hours": retention_hours,
        "dry_run": dry_run,
        "files_seen": 0,
        "files_deleted": 0,
        "bytes_deleted": 0,
        "deleted_files": [],
    }

    if not cache_dir.exists():
        return result

    for path in sorted(cache_dir.rglob("*")):
        if not path.is_file():
            continue
        result["files_seen"] += 1

        try:
            age_seconds = now_ts - path.stat().st_mtime
        except OSError:
            continue

        if age_seconds < cutoff_age_seconds:
            continue

        size = path.stat().st_size
        result["deleted_files"].append(str(path))
        if not dry_run:
            path.unlink(missing_ok=True)
            result["files_deleted"] += 1
            result["bytes_deleted"] += size

    # Best-effort cleanup of empty directories under the debug cache root.
    if not dry_run and cache_dir.exists():
        for child in sorted(cache_dir.rglob("*"), reverse=True):
            if child.is_dir():
                try:
                    child.rmdir()
                except OSError:
                    pass

    if dry_run:
        result["files_deleted"] = len(result["deleted_files"])
        result["bytes_deleted"] = sum(
            Path(p).stat().st_size for p in result["deleted_files"] if Path(p).exists()
        )

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Purge temporary Reddit debug metadata cache files.")
    parser.add_argument("--config", default="config.yml", help="Path to YAML configuration file.")
    parser.add_argument(
        "--older-than-hours",
        type=float,
        default=None,
        help="Override retention window in hours. Defaults to retention.debug_cache_hours from config.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting files.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = purge_debug_cache(
        args.config,
        older_than_hours=args.older_than_hours,
        dry_run=args.dry_run,
    )
    print(
        "Purged debug cache: "
        f"seen={result['files_seen']} "
        f"deleted={result['files_deleted']} "
        f"bytes={result['bytes_deleted']} "
        f"dry_run={result['dry_run']} "
        f"cache_dir={result['cache_dir']}"
    )


if __name__ == "__main__":
    main()
