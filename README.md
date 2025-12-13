# YouTube Live Webcam Aggregator

Turn YouTube into your personal webcam IPTV service.

Automatically discovers live webcam streams on YouTube and generates an M3U8 playlist for IPTV applications. Creates a curated, categorized collection of webcam streams without manual searching through YouTube.

**Features:**

- Auto-updating M3U8 playlists
- Organized by category (Animals, Transportation, Education, etc.)
- Customizable search and filtering
- Docker containerized for easy deployment
- Compatible with any M3U-capable player (VLC, IPTV apps, smart TVs, etc.)

## Quick Start

### Prerequisites

- [YouTube Data API v3 key](https://console.cloud.google.com/apis/credentials) (free with Google account)
- Docker

### Run with Docker

```bash
docker run -d \
  --name youtube-webcams \
  -p 8000:8000 \
  -e YOUTUBE_API_KEY=your_api_key_here \
  ghcr.io/mrgeetv/youtube-webcam-aggregator:latest
```

**With optional configuration:**

```bash
docker run -d \
  --name youtube-webcams \
  -p 8000:8000 \
  -e YOUTUBE_API_KEY=your_api_key_here \
  -e SEARCH_QUERY="webcam|live|nature -gaming" \
  -e EXCLUDED_CATEGORIES="Gaming,Music" \
  ghcr.io/mrgeetv/youtube-webcam-aggregator:latest
```

### Access Your Playlist

**Playlist URL:** `http://<your-host>:8000/playlist.m3u8`

- Use `localhost` for local installations
- Use your server's IP or hostname for remote access

Open this URL in any M3U-compatible player (VLC, IPTV apps, media players, etc.)

## Configuration

### Environment Variables

**Required:**

- `YOUTUBE_API_KEY` - Your YouTube Data API v3 key

**Optional:**

- `SEARCH_QUERY` - Search terms for finding streams (default includes webcam, live, nature terms)
- `EXCLUDED_CATEGORIES` - YouTube categories to exclude (comma-separated)
- `UPDATE_INTERVAL_HOURS` - Playlist refresh frequency (default: 5, max recommended: 5)

### Example Configurations

**Nature & Wildlife Focus:**

```bash
-e SEARCH_QUERY="animal|wildlife|bird|nature|zoo|aquarium|safari|live|cam -gameplay -gaming"
-e EXCLUDED_CATEGORIES="Gaming,Sports,Music,Entertainment"
```

**Transportation Focus:**

```bash
-e SEARCH_QUERY="train|railway|airport|harbor|traffic|road|ferry|live|cam -gameplay -gaming"
-e EXCLUDED_CATEGORIES="Gaming,Sports,Music,Entertainment,Comedy"
```

### Available Categories for Exclusion

- Film & Animation
- Autos & Vehicles
- Music
- Pets & Animals
- Sports
- Travel & Events
- Gaming
- People & Blogs
- Comedy
- Entertainment
- News & Politics
- Howto & Style
- Education
- Science & Technology
- Nonprofits & Activism

## Important Notes

### YouTube API Limitations

- **Inconsistent results**: YouTube's API can return different streams on each run - this is normal behavior
- **Rate limits**: Free tier includes 10,000 quota units per day (typically sufficient for normal use)
- **Search variability**: Results depend on what's currently live on YouTube

### Stream Expiration

- **Refresh interval limit**: Don't set `UPDATE_INTERVAL_HOURS` above 5 - streams expire after ~6 hours
- **Dead streams**: If you see connection errors, the playlist needs refreshing

### Search Query Optimization

- **Less is more**: Adding too many search terms can actually worsen results
- **Use exclusions**: The `-gameplay -gaming` style exclusions help filter unwanted content
- **Test iteratively**: Start simple and add terms gradually

## Troubleshooting

### No Streams Found

- Verify your YouTube API key is correct and active
- Check API quota usage in Google Console
- Try a simpler search query with fewer terms
- Ensure excluded categories aren't filtering everything out

### Streams Won't Play

- Check if playlist was recently updated (streams may have expired)
- Verify the M3U8 URL is accessible: `curl http://<your-host>:8000/playlist.m3u8`
- Restart the container: `docker restart youtube-webcams`

### API Quota Exceeded

- Monitor usage in [Google Console](https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas)
- Increase update interval to reduce API calls
- Consider requesting quota increase for heavy usage

### Viewing Logs

```bash
docker logs -f youtube-webcams
```

Look for successful playlist generation messages and any API errors.

## Development

For local development setup, Docker Compose usage, and contributing guidelines, see [DEVELOPMENT.md](DEVELOPMENT.md).
