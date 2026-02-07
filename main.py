"""
EPIC Earth Bot – Orchestrator

Fetches the latest NASA EPIC images and stitches them into a
1080x1080 H.264 MP4 time-lapse video.

Designed to be run once per day via GitHub Actions.
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

from utils.nasa_api import fetch_frames
from utils.video_engine import create_video


# ── Configuration ──────────────────────────────────────────────────
FRAMES_DIR = Path("frames")
OUTPUT_DIR = Path("output")




def cleanup() -> None:
    """Remove temporary frames and video."""
    if FRAMES_DIR.exists():
        shutil.rmtree(FRAMES_DIR)
        print("[MAIN] Cleaned up frames directory")


def main() -> None:
    load_dotenv()

    nasa_api_key = os.getenv("NASA_API_KEY")

    try:
        # ── Step 1: Fetch NASA EPIC frames ──────────────────────
        print("\n" + "=" * 50)
        print("[MAIN] Step 1/2: Fetching NASA EPIC images")
        print("=" * 50)
        frames, metadata = fetch_frames(
            api_key=nasa_api_key,
            output_dir=str(FRAMES_DIR),
        )

        # ── Step 2: Create video ────────────────────────────────
        print("\n" + "=" * 50)
        print("[MAIN] Step 2/2: Creating video")
        print("=" * 50)

        # Name the video after the date of the images
        date_str = metadata[0]["date"]  # e.g. "2026-02-06 00:31:45"
        date_label = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
        output_video = OUTPUT_DIR / f"epic_earth_{date_label}.mp4"

        video_path = create_video(
            frame_paths=frames,
            output_path=str(output_video),
            fps=3,
            size=1080,
        )


        print("\n" + "=" * 50)
        print(f"[MAIN] Success!")
        print("=" * 50)

    except Exception as e:
        print(f"\n[MAIN] FAILED: {e}")
        sys.exit(1)

    finally:
        cleanup()


if __name__ == "__main__":
    main()
