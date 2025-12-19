"""
YouTube Live Webcam Aggregator

A service that automatically discovers live webcam streams on YouTube and generates
an M3U8 playlist for IPTV applications. Searches for various webcam categories
and filters out unwanted content based on configurable exclusions.
"""

import asyncio
import gc
import http.server
import json
import logging
import os
import random
import re
import socketserver
import threading
import time
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO

import psutil
import subprocess
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    force=True,
)
logger = logging.getLogger("webcam-scraper")
API_KEY = os.getenv("YOUTUBE_API_KEY")
if not API_KEY:
    logger.error("YOUTUBE_API_KEY environment variable is required")
    raise ValueError("Missing required YOUTUBE_API_KEY environment variable")

EXCLUDED_CATEGORIES = set(
    os.getenv(
        "EXCLUDED_CATEGORIES", "Gaming,Sports,Film & Animation,Howto & Style"
    ).split(",")
)

DEFAULT_SEARCH_QUERY = "cam|webcam|live|beach|wildlife|aquarium|space|harbor|park|mountain|coast|city|traffic|nature|zoo -gameplay -playing -subscriber -donation -follower -facecam -reaction -chatting -gaming -fortnite -troll -asmr -twitch"
SEARCH_QUERY = os.getenv("SEARCH_QUERY", DEFAULT_SEARCH_QUERY)

try:
    UPDATE_INTERVAL_HOURS = int(os.getenv("UPDATE_INTERVAL_HOURS", "5"))
    if UPDATE_INTERVAL_HOURS < 1:
        raise ValueError("UPDATE_INTERVAL_HOURS must be at least 1")
except ValueError as e:
    logger.error(f"Invalid UPDATE_INTERVAL_HOURS: {e}")
    UPDATE_INTERVAL_HOURS = 5

try:
    MAX_VIDEOS_PER_CYCLE = int(os.getenv("MAX_VIDEOS_PER_CYCLE", "1000"))
    if MAX_VIDEOS_PER_CYCLE < 100:
        raise ValueError("MAX_VIDEOS_PER_CYCLE must be at least 100")
except ValueError as e:
    logger.error(f"Invalid MAX_VIDEOS_PER_CYCLE: {e}")
    MAX_VIDEOS_PER_CYCLE = 1000

try:
    CONCURRENT_EXTRACTIONS = int(os.getenv("CONCURRENT_EXTRACTIONS", "5"))
    if CONCURRENT_EXTRACTIONS < 1:
        raise ValueError("CONCURRENT_EXTRACTIONS must be at least 1")
except ValueError as e:
    logger.error(f"Invalid CONCURRENT_EXTRACTIONS: {e}")
    CONCURRENT_EXTRACTIONS = 5

RETRYABLE_STATUS_CODES = (429, 500, 502, 503, 504)


def retry_api_call(func, max_retries: int = 3, base_delay: float = 1.0):
    """Retry API call with exponential backoff on transient errors."""
    for attempt in range(max_retries + 1):
        try:
            return func()
        except HttpError as e:
            status = e.resp.status if hasattr(e, "resp") else None
            if status not in RETRYABLE_STATUS_CODES or attempt == max_retries:
                raise
            delay = min(base_delay * (2**attempt), 30.0) + random.random()
            logger.warning(
                f"API error {status}, retry {attempt + 1}/{max_retries} in {delay:.1f}s"
            )
            time.sleep(delay)


def log_memory_usage() -> None:
    """Log current memory usage."""
    if not logger.isEnabledFor(logging.DEBUG):
        return

    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / 1024 / 1024
    logger.debug(f"Memory: {mem_mb:.0f} MB")


def get_youtube_stream_url(video_id: str) -> Optional[str]:
    """
    Extract the direct stream URL for a YouTube video using yt-dlp subprocess.

    Uses subprocess to avoid memory leaks from yt-dlp's internal caching.

    Args:
        video_id: YouTube video ID

    Returns:
        Direct stream URL if extraction succeeds, None otherwise
    """
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        result = subprocess.run(
            ["yt-dlp", "-q", "--no-warnings", "-g", url],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Return last URL (usually best quality)
            urls = result.stdout.strip().split("\n")
            return urls[-1]
        if result.stderr:
            logger.debug(f"yt-dlp error for {video_id}: {result.stderr.strip()}")
        return None
    except subprocess.TimeoutExpired:
        logger.debug(f"Timeout extracting stream for {video_id}")
        return None
    except Exception as e:
        logger.debug(f"Stream extraction failed for {video_id}: {str(e)}")
        return None


def write_stream_to_playlist(
    file: TextIO, title: str, category: str, stream_url: str
) -> None:
    """
    Write a single stream entry to the M3U8 playlist file.

    Args:
        file: Open file handle for writing
        title: Stream title/name
        category: Category for grouping in IPTV players
        stream_url: Direct stream URL
    """
    try:
        file.write(f'#EXTINF:-1 group-title="{category}", {title}\n')
        file.write(f"{stream_url}\n")
    except Exception as e:
        logger.error(f"Playlist write failed: {str(e)}")


def create_youtube_client() -> Any:
    """
    Create and return a YouTube Data API client.

    Uses cache_discovery=False to prevent memory accumulation from
    cached discovery documents across cycles.

    Returns:
        Configured YouTube API client

    Raises:
        Exception: If client initialization fails
    """
    try:
        return build("youtube", "v3", developerKey=API_KEY, cache_discovery=False)
    except Exception as e:
        logger.error(f"YouTube client init failed: {e}")
        raise


def get_categories(youtube: Any) -> Dict[str, str]:
    """
    Fetch YouTube video categories for the US region.

    Args:
        youtube: YouTube API client

    Returns:
        Dictionary mapping category IDs to category names
    """
    try:
        request = youtube.videoCategories().list(part="snippet", regionCode="US")
        response = retry_api_call(request.execute)
        categories = {
            item["id"]: item["snippet"]["title"] for item in response.get("items", [])
        }
        del response
        del request
        return categories
    except HttpError as e:
        logger.error(f"Category fetch failed: {e}")
        return {}


def clean_title(title: str) -> str:
    """
    Clean and normalize video title for playlist compatibility.

    Removes non-ASCII characters and normalizes whitespace.

    Args:
        title: Raw video title

    Returns:
        Cleaned title string
    """
    title = unicodedata.normalize("NFKD", title)
    title = title.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", title).strip()


def get_live_webcams(youtube: Any, max_videos: int = None) -> List[str]:
    """
    Search for live webcam streams on YouTube.

    Performs paginated search using the configured search query and returns
    video IDs of live streams. Respects MAX_VIDEOS_PER_CYCLE limit to prevent
    unbounded memory growth.

    Args:
        youtube: YouTube API client
        max_videos: Maximum videos to collect (defaults to MAX_VIDEOS_PER_CYCLE)

    Returns:
        List of YouTube video IDs for live streams
    """
    if max_videos is None:
        max_videos = MAX_VIDEOS_PER_CYCLE

    video_ids = []
    published_before = None
    batch_count = 0

    try:
        while len(video_ids) < max_videos:
            batch_count += 1
            params = {
                "part": "id,snippet",
                "type": "video",
                "eventType": "live",
                "maxResults": 50,
                "order": "date",
                "q": SEARCH_QUERY,
            }
            if published_before:
                params["publishedBefore"] = published_before

            request = youtube.search().list(**params)
            response = retry_api_call(request.execute)
            items = response.get("items", [])

            if not items:
                logger.info("No more results available")
                break

            new_ids = [item["id"]["videoId"] for item in items]
            video_ids.extend(new_ids)

            # Enforce limit
            if len(video_ids) >= max_videos:
                video_ids = video_ids[:max_videos]
                logger.info(f"Reached video limit ({max_videos})")
                # Cleanup before break
                del response
                del items
                del request
                break

            published_before = items[-1]["snippet"]["publishedAt"]
            logger.info(
                f"Batch {batch_count}: +{len(new_ids)} videos, "
                f"total: {len(video_ids)}/{max_videos}"
            )

            # Cleanup response objects to free memory
            del response
            del items
            del request

            if not new_ids:
                logger.info("No new videos found in this batch")
                break

    except HttpError as e:
        if e.resp.status == 403:
            logger.error("API quota exceeded")
            return []
        else:
            logger.error(f"YouTube API error: {e}")
            if video_ids:
                logger.info(f"Returning {len(video_ids)} videos collected before error")

    return video_ids


def get_video_details(
    youtube: Any, video_ids: List[str], categories: Dict[str, str]
) -> Dict[str, List[Dict[str, str]]]:
    """
    Fetch detailed information for videos and organize by category.

    Retrieves video metadata, extracts stream URLs in parallel, and groups
    results by YouTube category while filtering out excluded categories.

    Args:
        youtube: YouTube API client
        video_ids: List of YouTube video IDs to process
        categories: Mapping of category IDs to names

    Returns:
        Dictionary mapping category names to lists of video info dictionaries.
        Each video info dict contains 'title' and 'stream_url' keys.
    """
    categorized_results = defaultdict(list)
    total_batches = (len(video_ids) + 49) // 50

    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        batch_num = (i // 50) + 1
        logger.info(
            f"Processing batch {batch_num}/{total_batches}: "
            f"videos {i + 1}-{i + len(chunk)}/{len(video_ids)}"
        )
        log_memory_usage()

        try:
            request = youtube.videos().list(part="snippet", id=",".join(chunk))
            response = retry_api_call(request.execute)
            items = response.get("items", [])

            # Filter items and prepare for parallel extraction
            videos_to_extract = []
            for item in items:
                category = categories.get(item["snippet"]["categoryId"], "Unknown")
                if category in EXCLUDED_CATEGORIES:
                    logger.debug(f"Skipped excluded category: {category}")
                    continue
                title = clean_title(item["snippet"]["title"])
                videos_to_extract.append(
                    {"id": item["id"], "title": title, "category": category}
                )

            # Extract stream URLs in parallel
            if videos_to_extract:
                logger.info(
                    f"Extracting {len(videos_to_extract)} streams "
                    f"({CONCURRENT_EXTRACTIONS} concurrent)"
                )
                with ThreadPoolExecutor(max_workers=CONCURRENT_EXTRACTIONS) as executor:
                    future_to_video = {
                        executor.submit(get_youtube_stream_url, v["id"]): v
                        for v in videos_to_extract
                    }
                    for future in as_completed(future_to_video):
                        video = future_to_video[future]
                        stream_url = future.result()
                        if stream_url:
                            logger.info(f"Added stream: {video['title']}")
                            categorized_results[video["category"]].append(
                                {"title": video["title"], "stream_url": stream_url}
                            )

            # Cleanup response objects to free memory
            del items
            del response
            del request

        except HttpError as e:
            logger.error(f"Batch {batch_num} failed: {e}")

    for category in categorized_results:
        categorized_results[category].sort(key=lambda x: x["title"].lower())

    return dict(sorted(categorized_results.items()))


def generate_playlist() -> bool:
    """
    Generate M3U8 playlist file with current live webcam streams.

    Performs complete webcam discovery workflow: searches for live streams,
    fetches video details, extracts stream URLs, and writes M3U8 playlist.
    Uses atomic file operations to prevent corruption.

    Returns:
        True if playlist generation succeeded, False otherwise
    """
    temp_playlist = Path("playlist.m3u8.tmp")
    final_playlist = Path("playlist.m3u8")
    youtube = None

    try:
        youtube = create_youtube_client()
        logger.info("Starting playlist generation")

        categories = get_categories(youtube)
        if not categories:
            logger.warning("Using fallback category mapping")

        video_ids = get_live_webcams(youtube)
        if not video_ids:
            logger.error("No videos found")
            return False

        categorized_results = get_video_details(youtube, video_ids, categories)

        stream_count = sum(len(v) for v in categorized_results.values())
        with open(temp_playlist, "w", encoding="utf-8") as playlist_file:
            playlist_file.write("#EXTM3U\n")
            playlist_file.write("# Generated by YouTube Webcam Scraper\n")
            playlist_file.write(
                f"# Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            playlist_file.write(f"# Streams: {stream_count}\n\n")

            for category, videos in categorized_results.items():
                for video in videos:
                    write_stream_to_playlist(
                        playlist_file, video["title"], category, video["stream_url"]
                    )

        os.replace(temp_playlist, final_playlist)
        logger.info(f"Playlist updated: {stream_count} streams")
        return True

    except Exception as e:
        logger.error(f"Playlist generation failed: {str(e)}")
        if temp_playlist.exists():
            temp_playlist.unlink()
        return False

    finally:
        # Cleanup YouTube client to free HTTP connections and caches
        if youtube is not None:
            try:
                if hasattr(youtube, "_http") and youtube._http:
                    youtube._http.close()
                logger.debug("Closed YouTube client")
            except Exception as e:
                logger.debug(f"Error closing YouTube client: {e}")
            del youtube


async def main() -> None:
    """
    Main service loop that periodically generates webcam playlists.

    Starts HTTP server for playlist serving and runs continuous update cycle
    at configured intervals. Forces garbage collection between cycles to
    prevent memory accumulation.
    """
    logger.info("Scraper service starting")
    logger.info(f"Using search query: {SEARCH_QUERY}")
    logger.info(f"Excluded categories: {', '.join(sorted(EXCLUDED_CATEGORIES))}")
    logger.info(f"Update interval: {UPDATE_INTERVAL_HOURS} hours")
    logger.info(f"Max videos per cycle: {MAX_VIDEOS_PER_CYCLE}")
    logger.info(f"Concurrent extractions: {CONCURRENT_EXTRACTIONS}")
    run_http_server()

    cycle_count = 0
    while True:
        try:
            cycle_count += 1
            logger.info(f"Starting scrape cycle #{cycle_count}")
            log_memory_usage()

            success = generate_playlist()

            if success:
                logger.info("Cycle completed successfully")
            else:
                logger.warning("Cycle completed with errors")

            log_memory_usage()

            # Force garbage collection between cycles to prevent memory accumulation
            collected = gc.collect()
            logger.debug(f"Garbage collection freed {collected} objects")
            log_memory_usage()

            logger.info(f"Sleeping for {UPDATE_INTERVAL_HOURS} hours")
            await asyncio.sleep(3600 * UPDATE_INTERVAL_HOURS)

        except Exception as e:
            logger.error(f"Main loop error: {e}")
            gc.collect()  # Also collect on error
            await asyncio.sleep(60)


class PlaylistHandler(http.server.BaseHTTPRequestHandler):
    """Secure HTTP handler serving only playlist and health endpoints."""

    def log_message(self, format, *args):
        """Route HTTP logs through our logger."""
        logger.debug(f"HTTP: {args[0]}")

    def do_GET(self):
        if self.path == "/playlist.m3u8":
            self._serve_playlist()
        elif self.path == "/health":
            self._serve_health()
        else:
            self.send_error(404, "Not Found")

    def _serve_playlist(self):
        playlist_path = Path("playlist.m3u8")
        if not playlist_path.exists():
            self.send_error(503, "Playlist not ready")
            return
        content = playlist_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.apple.mpegurl")
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)

    def _serve_health(self):
        process = psutil.Process(os.getpid())
        mem_mb = process.memory_info().rss / 1024 / 1024
        health = {"status": "ok", "memory_mb": round(mem_mb, 1)}
        content = json.dumps(health).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)


def run_http_server(port: int = 8000) -> None:
    """Start HTTP server in daemon thread."""
    httpd = socketserver.TCPServer(("", port), PlaylistHandler)
    logger.info(f"HTTP server started on port {port}")
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()


if __name__ == "__main__":
    asyncio.run(main())
