"""
NASA EPIC API client.
Fetches the most recent natural-color images of Earth taken by the
DSCOVR satellite's EPIC camera from ~1 million miles away.
"""

import os
import requests
from pathlib import Path
from datetime import datetime


EPIC_API_URL = "https://epic.gsfc.nasa.gov/api/natural"
EPIC_ARCHIVE_URL = "https://epic.gsfc.nasa.gov/archive/natural"


def get_latest_images_metadata(api_key: str | None = None) -> list[dict]:
    """
    Query the NASA EPIC API for the most recent set of natural-color images.

    Parameters
    ----------
    api_key : str, optional
        NASA API key. Falls back to the DEMO_KEY if not provided, but the
        demo key has very low rate limits.

    Returns
    -------
    list[dict]
        A list of image metadata dicts straight from the API.
    """
    params = {}
    if api_key:
        params["api_key"] = api_key

    response = requests.get(EPIC_API_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    if not data:
        raise RuntimeError("NASA EPIC API returned no images. Try again later.")

    print(f"[NASA] Found {len(data)} images for {data[0]['date'][:10]}")
    return data


def _build_image_url(image_meta: dict) -> str:
    """
    Construct the full download URL for a single EPIC image.

    The archive URL pattern is:
        /archive/natural/{YYYY}/{MM}/{DD}/png/{image_name}.png
    """
    date_str = image_meta["date"]  # e.g. "2026-02-06 00:31:45"
    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    image_name = image_meta["image"]
    return f"{EPIC_ARCHIVE_URL}/{dt.year}/{dt.month:02d}/{dt.day:02d}/png/{image_name}.png"


def download_images(metadata: list[dict], output_dir: str | Path) -> list[Path]:
    """
    Download full-resolution PNGs for every image in *metadata*.

    Parameters
    ----------
    metadata : list[dict]
        Image metadata as returned by `get_latest_images_metadata`.
    output_dir : str | Path
        Directory where files will be saved. Created if it doesn't exist.

    Returns
    -------
    list[Path]
        Sorted list of paths to the downloaded PNGs.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    downloaded: list[Path] = []

    for i, meta in enumerate(metadata):
        url = _build_image_url(meta)
        dest = output_dir / f"frame_{i:03d}.png"

        if dest.exists():
            print(f"[NASA]   Skipping {dest.name} (already downloaded)")
            downloaded.append(dest)
            continue

        print(f"[NASA]   Downloading frame {i + 1}/{len(metadata)}: {meta['image']}")
        resp = requests.get(url, timeout=120, stream=True)
        resp.raise_for_status()

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        downloaded.append(dest)

    downloaded.sort()
    print(f"[NASA] Downloaded {len(downloaded)} frames to {output_dir}")
    return downloaded


def fetch_frames(api_key: str | None = None, output_dir: str = "frames") -> tuple[list[Path], list[dict]]:
    """
    High-level helper: fetch metadata then download all frames.

    Returns
    -------
    tuple[list[Path], list[dict]]
        (list of frame paths, raw metadata list)
    """
    metadata = get_latest_images_metadata(api_key)
    frames = download_images(metadata, output_dir)
    return frames, metadata
