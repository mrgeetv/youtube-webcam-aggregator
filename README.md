# 📹 YouTube Live Webcam Aggregator

🎯 **Turn YouTube into your personal webcam IPTV service**

Automatically discovers live webcam streams on YouTube and generates an M3U8 playlist for IPTV applications. Creates a curated, categorized collection of webcam streams without manual searching through YouTube.

✨ **Features:**

- 🔄 Auto-updating M3U8 playlists
- 📂 Organized by category (Animals, Transportation, Education, etc.)
- 🎛️ Customizable search and filtering
- 🐳 Docker containerized for easy deployment
- 📱 Compatible with most IPTV players

## 🚀 Quick Start

### 📋 Prerequisites

- 🔑 [YouTube Data API v3 key](https://console.cloud.google.com/apis/credentials) (free with Google account)
- 🐳 Docker and Docker Compose

### ⚡ 5-Minute Setup

```bash
# 1. Clone the repository
git clone <repository-url>
cd youtube-webcam-aggregator

# 2. Configure your API key
cp .env.example .env
# Edit .env and add your YouTube API key

# 3. Launch the service
docker-compose up -d
```

### 🎯 Access Your Playlist

📺 **Playlist URL:** `http://localhost:23457/playlist.m3u8`

Copy this URL into any IPTV player that supports M3U8 streams!

## ⚙️ Configuration

### 🔧 Environment Variables

**🔑 Required:**

- `YOUTUBE_API_KEY` - Your YouTube Data API v3 key

**🎛️ Optional:**

- `SEARCH_QUERY` - Search terms for finding streams (default includes webcam, live, nature terms)
- `EXCLUDED_CATEGORIES` - YouTube categories to exclude (comma-separated)
- `UPDATE_INTERVAL_HOURS` - Playlist refresh frequency (default: 5, max recommended: 5)

### 📝 Example Configurations

**🦅 Nature & Wildlife Focus:**

```env
SEARCH_QUERY=animal|wildlife|bird|nature|zoo|aquarium|safari|live|cam -gameplay -gaming
EXCLUDED_CATEGORIES=Gaming,Sports,Music,Entertainment
UPDATE_INTERVAL_HOURS=5
```

**🚂 Transportation Focus:**

```env
SEARCH_QUERY=train|railway|airport|harbor|traffic|road|ferry|live|cam -gameplay -gaming
EXCLUDED_CATEGORIES=Gaming,Sports,Music,Entertainment,Comedy
UPDATE_INTERVAL_HOURS=5
```

### 📂 Available Categories for Exclusion

- Film & Animation
- Autos & Vehicles
- Music
- Pets & Animals
- Sports
- Travel & Events
- Gaming- People & Blogs
- Comedy
- Entertainment
- News & Politics
- Howto & Style
- Education
- Science & Technology
- Nonprofits & Activism

## 📺 Usage

The service generates an M3U8 playlist file that's compatible with most IPTV players that support HLS streams. The playlist organizes streams by YouTube category and updates automatically based on your configured interval.

**🔗 Accessing the playlist:**

- 🐳 Docker Compose: `http://localhost:23457/playlist.m3u8`
- 🖥️ Manual/local: `http://localhost:8000/playlist.m3u8`

💡 The port can be customized in the docker-compose.yml file if needed.

## ⚠️ Important Notes

### 🔄 YouTube API Limitations

- **🎲 Inconsistent results**: YouTube's API can return different streams on each run - this is normal behavior
- **📊 Rate limits**: Free tier includes 10,000 quota units per day (typically sufficient for normal use)
- **🔍 Search variability**: Results depend on what's currently live on YouTube

### ⏰ Stream Expiration

- **🕐 Refresh interval limit**: Don't set `UPDATE_INTERVAL_HOURS` above 5 - streams expire after ~6 hours
- **💀 Dead streams**: If you see connection errors, the playlist needs refreshing

### 🎯 Search Query Optimization

- **➖ Less is more**: Adding too many search terms can actually worsen results
- **🚫 Use exclusions**: The `-gameplay -gaming` style exclusions help filter unwanted content
- **🧪 Test iteratively**: Start simple and add terms gradually

## 🔧 Troubleshooting

### 🚫 No Streams Found

- ✅ Verify your YouTube API key is correct and active
- 📊 Check API quota usage in Google Console
- 🎯 Try a simpler search query with fewer terms
- 📂 Ensure excluded categories aren't filtering everything out

### ▶️ Streams Won't Play

- 🔄 Check if playlist was recently updated (streams may have expired)
- 🌐 Verify the M3U8 URL is accessible: `curl http://localhost:23457/playlist.m3u8`
- 🔄 Restart the service: `docker-compose restart`

### 📈 API Quota Exceeded

- 📊 Monitor usage in [Google Console](https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas)
- ⏰ Increase update interval to reduce API calls
- 📨 Consider requesting quota increase for heavy usage

### 🔧 Configuration Changes

After modifying `.env` file:

```bash
docker-compose down
docker-compose up -d
```

### 📋 Viewing Logs

```bash
docker-compose logs -f
```

👀 Look for successful playlist generation messages and any API errors.
