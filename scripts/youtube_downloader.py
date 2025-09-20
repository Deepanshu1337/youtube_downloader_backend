import yt_dlp
import json
import sys
import os
from pathlib import Path
import time
import random

COOKIES_FILE = Path("cookies.txt")


def get_browser_headers():
    """Generate browser-like headers to avoid bot detection"""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.youtube.com/",
    }


def base_ydl_opts():
    """Base yt-dlp options with anti-bot settings"""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "http_headers": get_browser_headers(),
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "skip_download": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
    }
    # If cookies.txt exists, inject
    if COOKIES_FILE.exists():
        opts["cookiefile"] = str(COOKIES_FILE)
    return opts


def get_video_info(url: str):
    """Extract video information without downloading"""
    strategies = [
        {**base_ydl_opts(), "extractor_args": {"youtube": {"player_client": ["web"]}}},
        {**base_ydl_opts(), "extractor_args": {"youtube": {"player_client": ["android"]}}},
        {**base_ydl_opts(), "extractor_args": {"youtube": {"player_client": ["ios"]}}},
    ]

    for i, ydl_opts in enumerate(strategies):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            formats = []
            seen = set()
            for f in info.get("formats", []):
                if f.get("vcodec") != "none" and f.get("height"):
                    q = f"{f['height']}p"
                    if q not in seen:
                        formats.append(
                            {
                                "quality": q,
                                "format": "mp4",
                                "format_id": f["format_id"],
                                "filesize": f.get("filesize", 0),
                            }
                        )
                        seen.add(q)

            formats.append(
                {"quality": "Audio Only", "format": "mp3", "format_id": "bestaudio", "filesize": 0}
            )

            duration = info.get("duration") or 0
            duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "Unknown"

            vc = info.get("view_count") or 0
            if vc >= 1_000_000_000:
                views = f"{vc/1_000_000_000:.1f}B views"
            elif vc >= 1_000_000:
                views = f"{vc/1_000_000:.1f}M views"
            elif vc >= 1_000:
                views = f"{vc/1_000:.1f}K views"
            else:
                views = f"{vc} views"

            return {
                "success": True,
                "title": info.get("title", "Unknown"),
                "thumbnail": info.get("thumbnail", ""),
                "duration": duration_str,
                "views": views,
                "channel": info.get("uploader", "Unknown"),
                "videoId": info.get("id", ""),
                "formats": formats,
                "is_live": info.get("is_live", False),
            }
        except Exception as e:
            if i == len(strategies) - 1:
                return {"success": False, "error": str(e)}

    return {"success": False, "error": "Failed to fetch video info"}


def get_direct_download_url(url: str, quality: str, fmt: str):
    """Return a direct media URL (no download)"""
    try:
        if fmt == "mp3":
            selector = "bestaudio/best"
        elif quality == "1080p":
            selector = "best[height<=1080]"
        elif quality == "720p":
            selector = "best[height<=720]"
        elif quality == "480p":
            selector = "best[height<=480]"
        else:
            selector = "best"

        opts = {**base_ydl_opts(), "format": selector}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get("title", "video")
        safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).rstrip()
        file_ext = "mp3" if fmt == "mp3" else info.get("ext", "mp4")

        dl_url = None
        if "url" in info:
            dl_url = info["url"]
        else:
            for f in info.get("formats", []):
                if f.get("url"):
                    if fmt == "mp3" and f.get("acodec") != "none":
                        dl_url = f["url"]
                        break
                    elif fmt != "mp3" and f.get("vcodec") != "none":
                        dl_url = f["url"]
                        break

        if not dl_url:
            raise Exception("No direct media URL found")

        return {
            "success": True,
            "downloadUrl": dl_url,
            "filename": f"{safe_title}.{file_ext}",
            "title": title,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"success": False, "error": "Invalid args"}))
        sys.exit(1)

    cmd, url = sys.argv[1], sys.argv[2]
    if cmd == "info":
        print(json.dumps(get_video_info(url)))
    elif cmd == "get-url":
        quality = sys.argv[3]
        fmt = sys.argv[4]
        print(json.dumps(get_direct_download_url(url, quality, fmt)))
    else:
        print(json.dumps({"success": False, "error": "Unknown command"}))
