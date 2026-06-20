# Live Webcam Aggregator

Turn live webcams from across the web into your own IPTV channel list.

It discovers live webcam streams from multiple sources, merges and de-duplicates
them into a single categorised **M3U8 playlist**, and serves it over HTTP for any
IPTV player (TiViMate, VLC, smart TVs, …). Streams are resolved **on demand** when
you press play, so the playlist never goes stale and the box does almost no work
until you actually watch something.

## Sources

| Source | What it adds |
| ------ | ------------ |
| YouTube Data API | Live webcam broadcasts found by search |
| worldcams.tv | Scraped camera directory |
| cxtvlive.com | Scraped camera directory |

The same camera found on more than one source is merged into a single channel.

## How it works

- **Catalogue build** (periodic, slow): each source is crawled, dead streams are
  dropped, survivors are de-duplicated, mapped to a unified category, and written
  into a playlist of stable internal URLs.
- **On-demand serving**: when a player opens a channel, the container resolves the
  real stream there and then and proxies the HLS manifest — refreshing expiring
  tokens transparently so long sessions don't die. Video segments stream **directly**
  from the source CDN; only the tiny manifest passes through the container.

## Quick start

### Prerequisites

- A [YouTube Data API v3 key](https://console.cloud.google.com/apis/credentials)
  (free with a Google account)
- Docker + Docker Compose

### Run

```bash
git clone https://github.com/mrgeetv/youtube-webcam-aggregator.git
cd youtube-webcam-aggregator
cp .env.example .env          # then edit .env and set YOUTUBE_API_KEY
docker compose up -d
```

The playlist is then available at `http://localhost:23457/playlist.m3u8`.

## Adding it to TiViMate (or any IPTV player)

It's a standard M3U8 playlist, so:

1. Make sure the container is reachable at the address your player will use, and set
   **`PUBLIC_BASE_URL`** to that address (see *Exposing it* below) — the playlist hands
   out `/stream/<id>` URLs that must be reachable by the player.
2. In **TiViMate**: *Settings → Playlists → Add playlist → Enter URL* → paste
   `https://<your-address>/playlist.m3u8` → *Next*. Channels load, grouped by category.
3. Press play on a channel — the stream is resolved on demand and starts.

Notes:

- First play of a YouTube camera takes a few seconds (it resolves cold, then it's
  instant); other sources are near-instant.
- There's no EPG — webcams have no schedule, so they appear as channels without a guide.
- Designed and tested against HLS/ExoPlayer-based players (TiViMate, VLC). Try one
  channel first to confirm your player + network path.

## Exposing it

The app is **exposure-agnostic** — it just serves HTTP and builds links from
`PUBLIC_BASE_URL`. Put whatever you like in front (reverse proxy, Tailscale, plain
LAN port). The only requirement: the front door must forward **both**
`/playlist.m3u8` **and** `/stream/*` to the container, and `PUBLIC_BASE_URL` must be
the address clients actually reach (e.g. `https://cams.example.com`).

## Endpoints

| Path | Purpose |
| ---- | ------- |
| `/playlist.m3u8` | The channel list |
| `/stream/<id>` | On-demand resolve + HLS manifest proxy (302 for MP4 sources) |
| `/health` | JSON status: readiness, stream count, per-source counts, memory |

## Configuration

All via environment variables (see `.env.example`):

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `YOUTUBE_API_KEY` | (required) | YouTube Data API v3 key |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | Externally-reachable base for the emitted URLs |
| `CATALOGUE_INTERVAL_HOURS` | `6` | Hours between catalogue refreshes (min 1) |
| `SEARCH_QUERY` | built-in webcam query | YouTube search terms (`\|`=OR, space=AND, `-`=exclude) |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `PORT` | `8000` | HTTP port inside the container |

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for local setup, the test suite, and the
project structure. Built test-first; run the checks with `pre-commit run --all-files`
and `pytest`.

## Security note

The on-demand stream proxy validates and signs the URLs it will fetch and refuses to
reach private/loopback addresses, but this is a self-hosted tool — put it behind your
own reverse proxy / network controls rather than exposing the raw port to the internet.
