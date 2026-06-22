# Reddit Aggregate Monitor

`reddit-aggregate-monitor` is a small, non-commercial, read-only Reddit API prototype.

Its purpose is to demonstrate a narrow, privacy-preserving API client that uses OAuth-authenticated Reddit API requests to collect minimal public listing-level counts from a fixed subreddit allowlist and reduce them to aggregate operational metrics.

This repository is intentionally limited to the Reddit API access prototype and its compliance controls. It does not contain unrelated financial-analysis, screener, trading, prediction, sentiment, or AI/ML code.

## Scope

The app performs low-volume, read-only `GET` requests to public listing endpoints for a fixed subreddit allowlist.

Default allowlist:

- `r/ETFs`
- `r/investing`
- `r/finance`

The app stores only aggregate run and daily collection metrics, such as:

- listing items returned by subreddit
- request success/failure status
- request timestamp
- Reddit rate-limit headers, when present
- collection coverage statistics

The app does **not** store Reddit usernames, Reddit user IDs, comments, private data, private messages, votes, saved posts, subscriptions, profile data, or long-term raw Reddit content.

## Explicit non-goals

This app does **not**:

- post, comment, vote, send messages, or moderate communities
- access private messages, chat, modmail, private subreddits, or non-public data
- collect comments
- store author usernames or Reddit user IDs
- build user profiles
- infer sensitive attributes about Redditors
- perform sentiment analysis
- perform topic modeling
- generate investment signals or trading signals
- perform market prediction or backtesting
- train AI/ML models
- redistribute Reddit content
- expose raw Reddit data publicly
- scrape Reddit web pages
- scrape external links found in Reddit posts
- use a fallback to unauthenticated `.json` endpoints

## OAuth-only design

The client fails closed if OAuth credentials are missing. It does not fall back to unauthenticated requests, unidentified scraping, or `www.reddit.com/*.json` access.

Required environment variables:

```bash
export REDDIT_CLIENT_ID="your_client_id"
export REDDIT_CLIENT_SECRET="your_client_secret"
```

Optional environment variable:

```bash
export REDDIT_USER_AGENT="script:com.example.reddit-aggregate-monitor:v0.1.0 (by /u/example_user)"
```

The `config.example.yml` file contains the default User-Agent template and can be copied to `config.yml`.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yml config.yml
```

Edit `config.yml` before running. Use a descriptive User-Agent that identifies the app and the Reddit username operating it.

## Usage

Collect one low-volume run of public listing counts:

```bash
python -m src.collect_public_listing_counts --config config.yml
```

Aggregate run-level outputs into a daily aggregate file:

```bash
python -m src.aggregate_daily_counts --config config.yml
```

Purge temporary debug cache files older than the configured retention window:

```bash
python -m src.purge_raw_cache --config config.yml
```

Dry-run purge:

```bash
python -m src.purge_raw_cache --config config.yml --dry-run
```

## Output layout

```text
data/
├── runs/
│   └── run-YYYYMMDDTHHMMSSZ.json
├── aggregate/
│   └── daily_counts/
│       └── YYYY-MM-DD.json
└── raw_cache/
    └── debug_metadata/
```

`runs/` and `aggregate/` contain aggregate operational metrics only.

`raw_cache/` is disabled by default. If enabled for debugging, it stores only short-lived request metadata and is purged automatically according to the retention window in `config.yml`.

## Data minimization

Although Reddit API responses may contain post fields, this prototype only reads what is necessary to count listing items and record collection health. It does not write post titles, selftext, authors, comments, URLs, permalinks, or user identifiers to long-term outputs.

See [`DATA_HANDLING.md`](DATA_HANDLING.md) and [`RETENTION.md`](RETENTION.md) for the full data-handling and retention design.

## Intended review posture

This repository is designed to support a narrow Reddit Data API access request:

- read-only
- non-commercial
- low-volume
- OAuth-authenticated
- fixed subreddit allowlist
- no raw content redistribution
- no long-term raw Reddit content retention
- no user-level profiling
- no AI/ML training
- no investment or trading signals

## License

This prototype is provided for review and personal non-commercial use. Add a license before distributing or reusing it more broadly.
