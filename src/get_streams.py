"""
YouTube Live Webcam Aggregator

A service that automatically discovers live webcam streams on YouTube and generates
an M3U8 playlist for IPTV applications. Searches for various webcam categories
and filters out unwanted content based on configurable exclusions.
"""

import asyncio
import http.server
import logging
import os
import re
import socketserver
import threading
import unicodedata
from collections import defaultdict
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

    Returns:
        Configured YouTube API client

    Raises:
        Exception: If client initialization fails
    """
    try:
        return build("youtube", "v3", developerKey=API_KEY)
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
        response = request.execute()
        return {
            item["id"]: item["snippet"]["title"] for item in response.get("items", [])
        }
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


def get_live_webcams(youtube: Any) -> List[str]:
    """
    Search for live webcam streams on YouTube.

    Performs paginated search using the configured search query and returns
    video IDs of live streams.

    Args:
        youtube: YouTube API client

    Returns:
        List of YouTube video IDs for live streams
    """
    video_ids = []
    published_before = None

    try:
        while True:
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
            response = request.execute()
            items = response.get("items", [])

            if not items:
                logger.info("No more results available")
                break

            new_ids = [item["id"]["videoId"] for item in items]
            video_ids.extend(new_ids)
            published_before = items[-1]["snippet"]["publishedAt"]
            logger.info(
                f"Batch fetch complete: +{len(new_ids)} videos, total: {len(video_ids)}"
            )
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

    Retrieves video metadata, extracts stream URLs, and groups results by
    YouTube category while filtering out excluded categories.

    Args:
        youtube: YouTube API client
        video_ids: List of YouTube video IDs to process
        categories: Mapping of category IDs to names

    Returns:
        Dictionary mapping category names to lists of video info dictionaries.
        Each video info dict contains 'title' and 'stream_url' keys.
    """
    categorized_results = defaultdict(list)

    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        logger.info(f"Processing batch {i + 1}-{i + len(chunk)}/{len(video_ids)}")
        log_memory_usage()

        try:
            request = youtube.videos().list(part="snippet", id=",".join(chunk))
            response = request.execute()

            for item in response.get("items", []):
                category = categories.get(item["snippet"]["categoryId"], "Unknown")
                title = clean_title(item["snippet"]["title"])

                if category in EXCLUDED_CATEGORIES:
                    logger.debug(f"Skipped excluded category: {category}")
                    continue

                stream_url = get_youtube_stream_url(item["id"])
                if not stream_url:
                    continue

                logger.info(f"Added stream: {title}")
                categorized_results[category].append(
                    {"title": title, "stream_url": stream_url}
                )

        except HttpError as e:
            logger.error(f"Batch processing failed: {e}")

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

        with open(temp_playlist, "w", encoding="utf-8") as playlist_file:
            playlist_file.write("#EXTM3U\n")
            playlist_file.write("# Generated by YouTube Webcam Scraper\n")
            playlist_file.write(
                f"# Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )

            for category, videos in categorized_results.items():
                for video in videos:
                    write_stream_to_playlist(
                        playlist_file, video["title"], category, video["stream_url"]
                    )

        os.replace(temp_playlist, final_playlist)
        logger.info(f"Playlist updated: {final_playlist}")
        return True

    except Exception as e:
        logger.error(f"Playlist generation failed: {str(e)}")
        if temp_playlist.exists():
            temp_playlist.unlink()
        return False


async def main() -> None:
    """
    Main service loop that periodically generates webcam playlists.

    Starts HTTP server for playlist serving and runs continuous update cycle
    at configured intervals.
    """
    logger.info("Scraper service starting")
    logger.info(f"Using search query: {SEARCH_QUERY}")
    logger.info(f"Excluded categories: {', '.join(sorted(EXCLUDED_CATEGORIES))}")
    logger.info(f"Update interval: {UPDATE_INTERVAL_HOURS} hours")
    run_http_server()

    while True:
        try:
            logger.info("Starting scrape cycle")
            log_memory_usage()
            success = generate_playlist()

            if success:
                logger.info("Cycle completed successfully")
            else:
                logger.warning("Cycle completed with errors")

            log_memory_usage()
            logger.info(f"Sleeping for {UPDATE_INTERVAL_HOURS} hours")
            await asyncio.sleep(3600 * UPDATE_INTERVAL_HOURS)

        except Exception as e:
            logger.error(f"Main loop error: {e}")
            await asyncio.sleep(60)


def run_http_server(port: int = 8000) -> None:
    """
    Start HTTP server in daemon thread to serve playlist files.

    Args:
        port: Port number for HTTP server (default: 8000)
    """
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("", port), handler)
    logger.info(f"HTTP server started on port {port}")
    thread = threading.Thread(target=httpd.serve_forever)
    thread.daemon = True
    thread.start()


if __name__ == "__main__":
    asyncio.run(main())
