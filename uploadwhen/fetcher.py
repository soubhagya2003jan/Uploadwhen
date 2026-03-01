"""Fetch metadata from YouTube videos and channels via yt-dlp."""

import yt_dlp
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
    IST    = ZoneInfo("Asia/Kolkata")
    US_ET  = ZoneInfo("America/New_York")
    AU_SYD = ZoneInfo("Australia/Sydney")
    JP     = ZoneInfo("Asia/Tokyo")
except ImportError:
    IST    = timezone(timedelta(hours=5, minutes=30), name="IST")
    US_ET  = timezone(timedelta(hours=-5),            name="ET")
    AU_SYD = timezone(timedelta(hours=11),             name="AEDT")
    JP     = timezone(timedelta(hours=9),              name="JST")


def _extract_video_info(info: dict) -> dict:
    """Parse a yt-dlp info dict into a clean record."""
    title       = info.get("title", "Unknown")
    channel     = info.get("channel") or info.get("uploader") or "Unknown"
    channel_url = info.get("channel_url") or info.get("uploader_url") or ""
    video_id    = info.get("id", "")
    video_url   = info.get("webpage_url") or info.get("url") or ""
    duration    = info.get("duration_string") or info.get("duration") or "Unknown"
    timestamp   = info.get("timestamp")
    upload_date = info.get("upload_date")

    date_str = time_ist = time_utc = time_us = time_au = time_jp = dt_utc = None
    na = "N/A"

    if timestamp:
        dt_utc   = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        dt_ist   = dt_utc.astimezone(IST)
        dt_us    = dt_utc.astimezone(US_ET)
        dt_au    = dt_utc.astimezone(AU_SYD)
        dt_jp    = dt_utc.astimezone(JP)
        date_str = dt_ist.strftime("%d %B %Y")
        time_ist = dt_ist.strftime("%H:%M:%S IST")
        time_utc = dt_utc.strftime("%H:%M:%S UTC")
        time_us  = dt_us.strftime("%H:%M:%S ET")
        time_au  = dt_au.strftime("%H:%M:%S AEST")
        time_jp  = dt_jp.strftime("%H:%M:%S JST")
    elif upload_date:
        dt_utc   = datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=timezone.utc)
        date_str = dt_utc.strftime("%d %B %Y")
        time_ist = time_utc = time_us = time_au = time_jp = na
    else:
        date_str = time_ist = time_utc = time_us = time_au = time_jp = na

    return {
        "title": title, "channel": channel, "channel_url": channel_url,
        "video_id": video_id, "video_url": video_url,
        "date": date_str, "time_ist": time_ist, "time_us": time_us,
        "time_au": time_au, "time_jp": time_jp, "time_utc": time_utc,
        "duration": str(duration), "datetime_utc": dt_utc,
    }


def fetch_video(url: str, verbose: bool = False) -> dict | None:
    """Fetch info for a single video URL."""
    ydl_opts = {
        "quiet": not verbose, "no_warnings": not verbose,
        "skip_download": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return _extract_video_info(info) if info else None
    except Exception:
        return None


def _normalise_channel_url(url: str) -> str:
    """Ensure channel URL points to /videos tab for yt-dlp."""
    url = url.rstrip("/")
    if url.endswith("/videos"):
        return url
    for suffix in ("/shorts", "/streams", "/playlists", "/community", "/about"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
            break
    return url + "/videos"


def _is_channel_url(url: str) -> bool:
    """Check if URL is a YouTube channel (not a video)."""
    path = urlparse(url).path.lower()
    if any(path.startswith(p) for p in ("/@", "/channel/", "/c/", "/user/")):
        return True
    return False


def fetch_channel_videos(channel_url: str, count: int = 10,
                         verbose: bool = False) -> list[dict]:
    """Fetch the last N uploads from a YouTube channel."""
    videos_url = _normalise_channel_url(channel_url)
    ydl_opts = {
        "quiet": not verbose, "no_warnings": not verbose,
        "skip_download": True, "extract_flat": False,
        "ignoreerrors": True, "playlistend": count,
    }
    results: list[dict] = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(videos_url, download=False)
            if info:
                for entry in (info.get("entries") or []):
                    if entry is not None:
                        results.append(_extract_video_info(entry))
    except Exception:
        pass
    return results
