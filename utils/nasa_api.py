"""
NASA EPIC API client.
Fetches natural-color images of Earth taken by the DSCOVR satellite's
EPIC camera from ~1.5 million km away.
"""

import requests
from pathlib import Path
from datetime import datetime


EPIC_API_URL = "https://epic.gsfc.nasa.gov/api/natural"
EPIC_ARCHIVE_URL = "https://epic.gsfc.nasa.gov/archive/natural"
EPIC_DATES_URL = "https://epic.gsfc.nasa.gov/api/natural/all"


def get_available_dates(api_key: str | None = None) -> list[str]:
    """
    Fetch all available dates from NASA EPIC API.

    Returns a list of date strings in 'YYYY-MM-DD' format.
    """
    params = {}
    if api_key:
        params["api_key"] = api_key
    response = requests.get(EPIC_DATES_URL, params=params, timeout=30)
    response.raise_for_status()
    dates = [d["date"] for d in response.json()]
    print(f"[NASA] Available dates: {len(dates)} total")
    return dates


def get_images_metadata_for_date(date: str, api_key: str | None = None) -> list[dict]:
    """
    Query the NASA EPIC API for a specific date's natural-color images.

    Parameters
    ----------
    date : str
        Date string in 'YYYY-MM-DD' format.
    api_key : str, optional
        NASA API key.

    Returns
    -------
    list[dict]
        A list of image metadata dicts for the given date.
    """
    url = f"{EPIC_API_URL}/date/{date}"
    params = {}
    if api_key:
        params["api_key"] = api_key
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not data:
        print(f"[NASA] No images found for {date}")
    else:
        print(f"[NASA] Found {len(data)} images for {date}")
    return data


def _build_image_url(image_meta: dict) -> str:
    """
    Construct the full download URL for a single EPIC image.

    Archive URL pattern:
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
        Image metadata as returned by `get_images_metadata_for_date`.
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
            print(f"[NASA]   Skipping {dest.name} (cached)")
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
