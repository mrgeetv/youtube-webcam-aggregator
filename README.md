# Live Webcam Aggregator

Turn live webcams from across the web into your own IPTV channel list.

It discovers live webcam streams from multiple sources, merges and de-duplicates
them into a single categorised **M3U8 playlist**, and serves it over HTTP for any
IPTV player (TiViMate, VLC, smart TVs, and similar). Streams are resolved **on
demand** when a channel is opened, so the playlist stays current and the server
only does work when a stream is played.

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
  stream on request and proxies the HLS manifest, refreshing expiring tokens
  transparently so long sessions keep playing. For most cams the video segments
  stream **directly** from the source CDN (only the small manifest passes through the
  box); a few sources whose streams are tied to the fetcher are handled specially
  (passthrough or relayed) so they still play.

## Quick start

### Prerequisites

- A YouTube Data API v3 key (free with a Google account). In the
  [Google Cloud Console](https://console.cloud.google.com/apis/credentials): create
  a project, enable *YouTube Data API v3*, then create an API key.
- Docker and Docker Compose installed.

### Run

```bash
git clone https://github.com/mrgeetv/youtube-webcam-aggregator.git
cd youtube-webcam-aggregator
cp .env.example .env          # then edit .env and set YOUTUBE_API_KEY
docker compose up -d
```

The playlist is then available at `http://localhost:23457/playlist.m3u8`. The first
catalogue build takes a few minutes (discovery + liveness checks); until it's ready,
`/playlist.m3u8` returns `503`.

## Adding it to TiViMate (or any IPTV player)

It's a standard M3U8 playlist, so:

1. Make sure the container is reachable at the address your player will use, and set
   **`PUBLIC_BASE_URL`** to that address (see *Exposing it* below) — the playlist hands
   out `/stream/<id>` URLs that must be reachable by the player.
2. In **TiViMate**: *Settings → Playlists → Add playlist → Enter URL* → paste
   `https://<your-address>/playlist.m3u8` → *Next*. Channels load, grouped by category.
3. Open a channel — the stream is resolved on demand and begins playing.

Notes:

- First play of a YouTube camera takes a few seconds (it resolves cold, then it's
  instant); other sources are near-instant.
- There's no EPG — webcams have no schedule, so they appear as channels without a guide.
- Designed and tested against HLS/ExoPlayer-based players (TiViMate, VLC). Try one
  channel first to confirm your player + network path.

## Exposing it

The application is **exposure-agnostic**: it serves HTTP and builds links from
`PUBLIC_BASE_URL`. Any reverse proxy, tunnel (such as Tailscale), or direct port
mapping can sit in front. The only requirement is that the front door forwards
**both** `/playlist.m3u8` **and** `/stream/*` to the container, and that
`PUBLIC_BASE_URL` is set to the address clients actually reach
(for example `https://cams.example.com`).

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
| `SCRAPE_WORKERS` | `min(16, cpu×4)` | Concurrency for scraping + liveness during the catalogue build. Lower it to reduce peak build-time memory (at the cost of a slower build) |

> **Resource usage:** memory peaks during the periodic catalogue build — it fetches
> and liveness-checks every source concurrently, then settles back down once the
> playlist is built (e.g. a transient ~1 GB during the build vs ~270 MB at rest for a
> ~2000-cam catalogue). The build is the high-water mark; lower `SCRAPE_WORKERS` to
> cap that peak. Live memory is on `/health` (`rss_mb`).

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for local setup, the test suite, and the
project structure. Built test-first; run the checks with `pre-commit run --all-files`
and `pytest`.

## Security note

The on-demand stream proxy validates and signs the URLs it will fetch and refuses to
reach private/loopback addresses, but this is a self-hosted tool — put it behind your
own reverse proxy / network controls rather than exposing the raw port to the internet.
