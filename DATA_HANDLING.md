# Data Handling

This document describes how `reddit-aggregate-monitor` handles Reddit API data.

## Purpose

The project is a small, non-commercial, read-only API prototype. It uses OAuth-authenticated Reddit API requests to collect minimal public listing-level counts from a fixed subreddit allowlist and reduce them to aggregate operational metrics.

The app is not a user-facing Reddit bot and does not automate posts, comments, votes, messages, moderation actions, or community interactions.

## Fixed subreddit allowlist

Default allowlist:

- `r/ETFs`
- `r/investing`
- `r/finance`

The allowlist is configured explicitly in `config.yml`. The client does not discover or crawl subreddits automatically.

## API actions

The app only performs read-only `GET` requests to public listing endpoints on `https://oauth.reddit.com`.

Default endpoint pattern:

```text
/r/{subreddit}/new?limit={request_limit}
```

The app does not use endpoints for posting, commenting, voting, messaging, moderation, private messages, modmail, user profiles, saved posts, subscriptions, or private subreddit access.

## OAuth-only access

The app requires OAuth credentials. If credentials are missing, the client raises an error and stops.

The app does not fall back to:

- unauthenticated `.json` endpoints
- web scraping
- browser automation
- multiple accounts
- rotating identities
- proxy-based access

## Data received from Reddit

The Reddit API may return listing items with many fields. The prototype intentionally ignores fields that are not needed for collection-health metrics.

The app may read the listing response to calculate:

- number of listing items returned
- subreddit requested
- request timestamp
- HTTP status
- rate-limit headers, when present
- request error category, if any

## Data stored long term

Long-term outputs are limited to aggregate operational metrics:

- run timestamp
- subreddit name from the allowlist
- listing item count returned by the API
- request success/failure status
- request latency
- request count
- rate-limit metadata, when present
- daily aggregate coverage metrics

Long-term outputs do **not** contain:

- Reddit usernames
- Reddit user IDs
- author fields
- post titles
- post selftext/body content
- comment bodies
- comment IDs
- private messages
- modmail
- user profile data
- post URLs
- permalinks
- vote data
- subscriber data
- off-platform identifiers

## Temporary debug cache

Temporary debug metadata caching is disabled by default.

If enabled, the cache stores only short-lived request metadata useful for troubleshooting collection quality, such as:

- fetch timestamp
- subreddit requested
- endpoint path
- listing item count
- HTTP status
- rate-limit headers

The debug cache does not store raw Reddit response bodies, post titles, selftext, authors, comments, URLs, permalinks, or user identifiers.

Temporary debug metadata is purged according to the retention window in `config.yml`. The default retention window is 24 hours.

## Data not collected

The app does not collect:

- comments
- comment threads
- private messages
- chat messages
- modmail
- user profile pages
- user histories
- followers
- saved posts
- subscriptions
- voting behavior
- moderation logs
- private subreddit content
- external web pages linked from Reddit posts

## No user profiling or sensitive inference

The app does not build user-level datasets and does not infer characteristics about Redditors.

Specifically, it does not infer or derive:

- political affiliation
- health status
- sexual orientation
- religion
- ethnicity
- financial condition of individual Redditors
- location of individual Redditors
- identity or off-platform accounts

## No commercial or restricted downstream use

The app does not use Reddit data for:

- advertising
- user targeting
- lead generation
- resale or licensing
- commercial datasets
- AI/ML training
- model fine-tuning
- sentiment analysis
- investment signals
- trading signals
- market prediction
- backtesting
- automated engagement

## Data deletion posture

Because the app does not store raw Reddit content or user identifiers long term, deletion exposure is minimized.

If Reddit requests deletion of any retained output, or if access is terminated and Reddit requires deletion, the operator should delete:

1. all temporary debug cache files;
2. all run-level aggregate files, if requested;
3. all daily aggregate files, if requested;
4. any local backups containing those files.

The purge utility can delete temporary debug cache files automatically:

```bash
python -m src.purge_raw_cache --config config.yml
```

Manual deletion of all local data can be performed by removing the configured `data_dir` directory.
