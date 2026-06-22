# Retention and Deletion Policy

This document describes retention and deletion controls for `reddit-aggregate-monitor`.

## Retention summary

| Data category | Stored by default | Default retention | Notes |
|---|---:|---:|---|
| OAuth secrets | No | N/A | Read from environment variables only |
| Raw Reddit API response bodies | No | N/A | Not written to disk |
| Post titles | No | N/A | Not written to long-term outputs |
| Post selftext/body content | No | N/A | Not written to long-term outputs |
| Author usernames / user IDs | No | N/A | Not written to disk |
| Comments | No | N/A | Not collected |
| URLs / permalinks | No | N/A | Not written to long-term outputs |
| Temporary debug metadata | Disabled by default | 24 hours if enabled | No raw content or user identifiers |
| Run-level aggregate metrics | Yes | Operator-controlled | Aggregate operational metrics only |
| Daily aggregate metrics | Yes | Operator-controlled | Aggregate operational metrics only |

## Default retention window

The default temporary debug cache retention window is 24 hours.

Configuration:

```yaml
retention:
  debug_cache_hours: 24
```

The debug cache is disabled by default:

```yaml
debug_cache:
  enabled: false
```

## Raw content retention

The app is designed not to write raw Reddit response bodies to disk.

If temporary debugging is enabled, only request metadata is stored. The debug cache does not store titles, selftext, authors, comments, URLs, permalinks, or user identifiers.

## Automatic purge

Run:

```bash
python -m src.purge_raw_cache --config config.yml
```

Dry run:

```bash
python -m src.purge_raw_cache --config config.yml --dry-run
```

The purge utility removes files under the configured debug cache directory that are older than the configured retention window.

## Deletion on Reddit request or access termination

If Reddit requests deletion, or if API access is terminated and deletion is required, delete the following:

1. all files under `data/raw_cache/`;
2. all files under `data/runs/`, if requested;
3. all files under `data/aggregate/`, if requested;
4. any local backups or exported copies containing those files.

Example full local deletion:

```bash
rm -rf data/raw_cache data/runs data/aggregate
```

## Deleted Reddit content

The app does not store raw Reddit content or user identifiers long term. This reduces the risk of retaining content after it has been deleted on Reddit.

If a temporary debug metadata file is present, it is short-lived and is removed by the purge utility according to the configured retention window.

## Backups

Do not include `data/raw_cache/` in backups.

If backups are used for run-level or daily aggregate outputs, ensure they can be deleted if Reddit requests deletion of retained outputs.

## Operator checklist

Before submitting an API access request:

- confirm `debug_cache.enabled` is `false` unless needed for troubleshooting;
- confirm OAuth credentials are stored only in environment variables;
- confirm the User-Agent is descriptive and includes the app name and operator username;
- confirm the subreddit allowlist is narrow and fixed;
- run the purge utility after any debug session;
- verify no raw Reddit content, usernames, comments, URLs, or permalinks are written to long-term outputs.
