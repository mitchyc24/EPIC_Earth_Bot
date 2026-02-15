"""
EPIC Earth Bot - Orchestrator

Ensures the last 14 days of NASA EPIC Earth time-lapse videos are
created (9:16 vertical, date-stamped) and uploaded to YouTube.

Designed to be run once daily. Tracks state in data/tracking.json
to avoid duplicating work even if runs are missed for several days.

Workflow:
  1. Fetch available EPIC dates from the last 14 days
  2. Create missing 9:16 videos with date overlays
  3. Authenticate with YouTube
  4. Upload any videos not yet on YouTube
  5. Update tracking state
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from utils.nasa_api import get_available_dates, get_images_metadata_for_date, download_images
from utils.video_engine import create_video
from utils.youtube_upload import (
    get_authenticated_service,
    get_uploaded_video_titles,
    make_video_title,
    upload_video,
)
from utils.tracking import (
    is_video_created,
    is_uploaded,
    mark_video_created,
    mark_uploaded,
    get_dates_needing_video,
    get_dates_needing_upload,
    print_summary,
    cleanup_old_entries,
)


# -- Configuration --
FRAMES_DIR = Path("frames")
OUTPUT_DIR = Path("output")
LOOKBACK_DAYS = 14


def get_recent_epic_dates(api_key: str | None) -> list[str]:
    """Fetch EPIC dates from the last LOOKBACK_DAYS days."""
    all_dates = get_available_dates(api_key)
    today = datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=LOOKBACK_DAYS)

    recent = [
        d for d in all_dates
        if cutoff <= datetime.strptime(d, "%Y-%m-%d").date() <= today
    ]
    recent.sort()
    print(f"[MAIN] {len(recent)} dates in the last {LOOKBACK_DAYS} days")
    return recent


def cleanup_frames() -> None:
    """Remove temporary frames directory."""
    if FRAMES_DIR.exists():
        shutil.rmtree(FRAMES_DIR)


def create_missing_videos(dates: list[str], api_key: str | None) -> int:
    """
    Create videos for dates that don't have one yet.

    Returns the number of videos successfully created.
    """
    need_video = get_dates_needing_video(dates)
    if not need_video:
        print("[MAIN] All videos already created. Nothing to do.")
        return 0

    print(f"[MAIN] Need to create {len(need_video)} videos: {need_video}")
    OUTPUT_DIR.mkdir(exist_ok=True)
    created = 0

    for date_str in need_video:
        print(f"\n{'='*50}")
        print(f"[MAIN] Creating video for {date_str}")
        print(f"{'='*50}")

        try:
            # Fetch metadata and download frames
            metadata = get_images_metadata_for_date(date_str, api_key)
            if not metadata:
                print(f"[MAIN] No images available for {date_str}. Skipping.")
                continue

            frames = download_images(metadata, FRAMES_DIR)
            if len(frames) < 2:
                print(f"[MAIN] Only {len(frames)} frame(s) for {date_str}. Skipping.")
                continue

            # Create the video
            video_filename = f"epic_earth_{date_str}.mp4"
            output_path = OUTPUT_DIR / video_filename

            video_path = create_video(
                frame_paths=frames,
                output_path=str(output_path),
                date_str=date_str,
                fps=12,
            )

            # Record in tracking
            mark_video_created(date_str, str(video_path))
            created += 1
            print(f"[MAIN] Successfully created video for {date_str}")

        except Exception as e:
            print(f"[MAIN] FAILED to create video for {date_str}: {e}")
            import traceback
            traceback.print_exc()

        finally:
            cleanup_frames()

    return created


def upload_missing_videos(dates: list[str]) -> int:
    """
    Upload videos to YouTube for dates that haven't been uploaded yet.

    Returns the number of videos successfully uploaded.
    """
    need_upload = get_dates_needing_upload(dates)
    if not need_upload:
        print("[MAIN] All videos already uploaded. Nothing to do.")
        return 0

    print(f"[MAIN] Need to upload {len(need_upload)} videos: {need_upload}")

    # Authenticate with YouTube
    try:
        service = get_authenticated_service()
    except Exception as e:
        print(f"[MAIN] YouTube authentication failed: {e}")
        return 0

    # Fetch existing uploads to double-check against YouTube
    try:
        existing_titles = get_uploaded_video_titles(service)
    except Exception as e:
        print(f"[MAIN] Failed to fetch existing YouTube uploads: {e}")
        existing_titles = {}

    uploaded = 0

    for date_str in need_upload:
        title = make_video_title(date_str)

        # Double-check: skip if already on YouTube (not in tracking but is uploaded)
        if title in existing_titles:
            video_id = existing_titles[title]
            print(f"[MAIN] {date_str} already on YouTube (ID: {video_id}). Updating tracking.")
            mark_uploaded(date_str, video_id)
            uploaded += 1
            continue

        # Find the video file
        from utils.tracking import get_entry
        entry = get_entry(date_str)
        if not entry or not entry.get("video_path"):
            print(f"[MAIN] No video path found for {date_str}. Skipping upload.")
            continue

        video_path = Path(entry["video_path"])
        if not video_path.exists():
            print(f"[MAIN] Video file missing: {video_path}. Skipping upload.")
            continue

        print(f"\n{'='*50}")
        print(f"[MAIN] Uploading video for {date_str}")
        print(f"{'='*50}")

        try:
            video_id = upload_video(service, video_path, date_str)
            if video_id:
                mark_uploaded(date_str, video_id)
                uploaded += 1
                print(f"[MAIN] Successfully uploaded {date_str}")
            else:
                print(f"[MAIN] Upload returned no video ID for {date_str}")
        except Exception as e:
            print(f"[MAIN] FAILED to upload {date_str}: {e}")
            import traceback
            traceback.print_exc()

    return uploaded


def main() -> None:
    load_dotenv()
    nasa_api_key = os.getenv("NASA_API_KEY")

    print("\n" + "=" * 60)
    print("  EPIC EARTH BOT - Daily Run")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)

    try:
        # Step 1: Get recent EPIC dates
        print("\n[STEP 1] Fetching available NASA EPIC dates...")
        recent_dates = get_recent_epic_dates(nasa_api_key)
        if not recent_dates:
            print("[MAIN] No recent EPIC dates found. Exiting.")
            return

        # Step 2: Create missing videos
        print("\n[STEP 2] Creating missing videos...")
        videos_created = create_missing_videos(recent_dates, nasa_api_key)
        print(f"[MAIN] Videos created this run: {videos_created}")

        # Step 3: Upload missing videos to YouTube
        print("\n[STEP 3] Uploading missing videos to YouTube...")
        videos_uploaded = upload_missing_videos(recent_dates)
        print(f"[MAIN] Videos uploaded this run: {videos_uploaded}")

        # Step 4: Cleanup old tracking entries (older than 30 days)
        print("\n[STEP 4] Cleaning up old tracking data...")
        cleanup_old_entries(keep_days=30)

        # Print final summary
        print_summary(recent_dates)

        print("\n" + "=" * 60)
        print(f"  RUN COMPLETE")
        print(f"  Videos created:  {videos_created}")
        print(f"  Videos uploaded: {videos_uploaded}")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n[MAIN] FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
