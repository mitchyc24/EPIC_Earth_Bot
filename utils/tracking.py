"""
Tracking module – persistent JSON-based state tracking.

Tracks per-date status for:
  - video_created: whether the MP4 has been generated
  - video_path: path to the local MP4 file
  - youtube_uploaded: whether it's been uploaded to YouTube
  - youtube_video_id: the YouTube video ID after upload
  - created_at: timestamp of video creation
  - uploaded_at: timestamp of YouTube upload
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

TRACKING_FILE = Path(__file__).parent.parent / "data" / "tracking.json"


def _load() -> dict:
    """Load tracking data from disk."""
    TRACKING_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not TRACKING_FILE.exists() or TRACKING_FILE.stat().st_size == 0:
        return {}
    with open(TRACKING_FILE, "r") as f:
        return json.load(f)


def _save(data: dict) -> None:
    """Save tracking data to disk."""
    TRACKING_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRACKING_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def get_all_entries() -> dict:
    """Return the full tracking dictionary."""
    return _load()


def get_entry(date_str: str) -> Optional[dict]:
    """Get tracking entry for a specific date."""
    data = _load()
    return data.get(date_str)


def is_video_created(date_str: str) -> bool:
    """Check if video has been created for a date."""
    entry = get_entry(date_str)
    if entry is None:
        return False
    # Also verify the file actually exists on disk
    if entry.get("video_created") and entry.get("video_path"):
        return Path(entry["video_path"]).exists()
    return False


def is_uploaded(date_str: str) -> bool:
    """Check if video has been uploaded to YouTube for a date."""
    entry = get_entry(date_str)
    if entry is None:
        return False
    return bool(entry.get("youtube_uploaded"))


def mark_video_created(date_str: str, video_path: str) -> None:
    """Record that a video has been created for a date."""
    data = _load()
    if date_str not in data:
        data[date_str] = {}
    data[date_str].update({
        "video_created": True,
        "video_path": str(Path(video_path).resolve()),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    _save(data)
    print(f"[TRACKING] Marked video created for {date_str}")


def mark_uploaded(date_str: str, youtube_video_id: str) -> None:
    """Record that a video has been uploaded to YouTube."""
    data = _load()
    if date_str not in data:
        data[date_str] = {}
    data[date_str].update({
        "youtube_uploaded": True,
        "youtube_video_id": youtube_video_id,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    })
    _save(data)
    print(f"[TRACKING] Marked uploaded for {date_str} (video ID: {youtube_video_id})")


def get_dates_needing_video(date_list: list[str]) -> list[str]:
    """Return dates from the list that don't have videos created yet."""
    return [d for d in date_list if not is_video_created(d)]


def get_dates_needing_upload(date_list: list[str]) -> list[str]:
    """Return dates from the list that have videos but haven't been uploaded."""
    return [d for d in date_list if is_video_created(d) and not is_uploaded(d)]


def cleanup_old_entries(keep_days: int = 30) -> None:
    """Remove tracking entries older than keep_days."""
    from datetime import timedelta
    data = _load()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).date()
    removed = []
    for date_str in list(data.keys()):
        try:
            entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if entry_date < cutoff:
                removed.append(date_str)
                del data[date_str]
        except ValueError:
            continue
    if removed:
        _save(data)
        print(f"[TRACKING] Cleaned up {len(removed)} old entries: {removed}")


def print_summary(date_list: list[str]) -> None:
    """Print a summary of tracking status for the given dates."""
    data = _load()
    print("\n" + "=" * 60)
    print("  TRACKING SUMMARY")
    print("=" * 60)
    print(f"  {'Date':<14} {'Video':<12} {'Uploaded':<12} {'YouTube ID'}")
    print("-" * 60)
    for d in sorted(date_list):
        entry = data.get(d, {})
        video = "YES" if is_video_created(d) else "NO"
        uploaded = "YES" if entry.get("youtube_uploaded") else "NO"
        yt_id = entry.get("youtube_video_id", "-")
        print(f"  {d:<14} {video:<12} {uploaded:<12} {yt_id}")
    print("=" * 60 + "\n")
