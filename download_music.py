"""
Download public domain / CC0 space-themed ambient music for EPIC Earth Bot.

Sources tracks from the Internet Archive (stable permanent URLs).
All tracks are CC0 1.0 Universal — no attribution required.

Run once to populate the music/ directory:
    python download_music.py

You can also drop your own .mp3/.wav/.ogg files into music/ and
the video engine will include them in the rotation automatically.
"""

import requests
from pathlib import Path

MUSIC_DIR = Path(__file__).parent / "music"

# ── Internet Archive CC0 ambient / space tracks ──────────────────────
# URLs follow the permanent pattern: archive.org/download/{id}/{file}
#
# Sources:
#   "La Luna e Le Stelle – Electric Stratosphere" (CC0 1.0)
#     https://archive.org/details/LiveCellarBar24-11-14ElectricStratosphere
#   "Andromeda – Acoustics among stars" (CC0 1.0)
#     https://archive.org/details/gt446Andromeda-AcousticsAmongStars
#   "graphite412 – A Grain of Wheat" (CC0 1.0)
#     https://archive.org/details/E4g004-Graphite412AGrainOfWheat
#   "graphite412 – Deus est Lux I" (CC0 1.0)
#     https://archive.org/details/E4g020-Graphite412DeusEstLuxI_800

_IA = "https://archive.org/download"
_ES = f"{_IA}/LiveCellarBar24-11-14ElectricStratosphere"
_AN = f"{_IA}/gt446Andromeda-AcousticsAmongStars"
_GW = f"{_IA}/E4g004-Graphite412AGrainOfWheat"
_DL = f"{_IA}/E4g020-Graphite412DeusEstLuxI_800"

TRACKS = [
    {
        "name": "ambient-space-01.mp3",
        "url": f"{_ES}/02VoyagerOne.mp3",
        "description": "Voyager One – La Luna e Le Stelle (6:26)",
    },
    {
        "name": "ambient-space-02.mp3",
        "url": f"{_ES}/04Jupiter.mp3",
        "description": "Jupiter – La Luna e Le Stelle (4:53)",
    },
    {
        "name": "ambient-space-03.mp3",
        "url": f"{_ES}/05AlphaRise.mp3",
        "description": "Alpha Rise – La Luna e Le Stelle (5:57)",
    },
    {
        "name": "ambient-space-04.mp3",
        "url": f"{_ES}/06CelestialCataylizer.mp3",
        "description": "Celestial Cataylizer – La Luna e Le Stelle (9:55)",
    },
    {
        "name": "ambient-space-05.mp3",
        "url": f"{_ES}/05Mars.mp3",
        "description": "Mars – La Luna e Le Stelle (13:34)",
    },
    {
        "name": "ambient-space-06.mp3",
        "url": f"{_ES}/01Cyberhawk.mp3",
        "description": "Cyberhawk – La Luna e Le Stelle (5:38)",
    },
    {
        "name": "ambient-space-07.mp3",
        "url": f"{_AN}/5.part2.mp3",
        "description": "Signals from Emptiness Pt 2 – Andromeda (4:36)",
    },
    {
        "name": "ambient-space-08.mp3",
        "url": f"{_AN}/6..mp3",
        "description": "Boreas (Sky Wanderer) – Andromeda (6:03)",
    },
    {
        "name": "ambient-space-09.mp3",
        "url": f"{_AN}/3..mp3",
        "description": "Jupiter's Shadow – Andromeda (3:57)",
    },
    {
        "name": "ambient-space-10.mp3",
        "url": f"{_GW}/AGrainOfWheat.mp3",
        "description": "A Grain of Wheat – graphite412 (9:03)",
    },
]


def download_tracks() -> None:
    """Download all music tracks to the music/ directory."""
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {len(TRACKS)} CC0 space ambient tracks from Internet Archive...")
    print(f"Destination: {MUSIC_DIR.resolve()}\n")

    downloaded = 0
    failed = 0

    for track in TRACKS:
        dest = MUSIC_DIR / track["name"]

        if dest.exists() and dest.stat().st_size > 1024:
            size_mb = dest.stat().st_size / (1024 * 1024)
            print(f"  SKIP  {track['name']} ({size_mb:.1f} MB) — {track['description']}")
            downloaded += 1
            continue

        print(f"  GET   {track['name']} — {track['description']}...", end=" ", flush=True)

        try:
            resp = requests.get(track["url"], timeout=120, stream=True)
            resp.raise_for_status()

            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            size_mb = dest.stat().st_size / (1024 * 1024)
            print(f"OK ({size_mb:.1f} MB)")
            downloaded += 1

        except Exception as e:
            print(f"FAILED ({e})")
            failed += 1
            if dest.exists():
                dest.unlink()

    print(f"\nDone: {downloaded} ready, {failed} failed")
    print(f"Music directory: {MUSIC_DIR.resolve()}")

    if downloaded > 0:
        print(
            "\nThe video engine will automatically pick a different "
            "track for each date."
        )
    if failed > 0:
        print(
            "\nTip: You can also place your own .mp3/.wav/.ogg files "
            "directly into the music/ directory."
        )


if __name__ == "__main__":
    download_tracks()
