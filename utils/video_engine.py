"""
Video engine - converts a sequence of EPIC Earth frames into a
9:16 vertical (1080x1920) H.264 MP4 with date overlay and background
music, suitable for YouTube Shorts.

Uses FFmpeg via ffmpeg-python. The Earth (2048x2048 source) is
centered in the vertical frame with the date stamped at the top.
Each video is exactly 30 seconds with a different music track.

Music is downloaded fresh on every run: a track is chosen
deterministically from the catalogue using a date-based seed,
fetched from the Internet Archive, used, then discarded.
"""

import ffmpeg
import hashlib
import random
import requests
import subprocess
import json
import tempfile
from pathlib import Path

TARGET_DURATION = 30  # seconds

# ── CC0 / public-domain space-themed catalogue ────────────────────────
# All tracks are CC0 1.0 Universal — no attribution required.
# Sources: Internet Archive (stable permanent URLs)
_IA = "https://archive.org/download"
_ES = f"{_IA}/LiveCellarBar24-11-14ElectricStratosphere"
_AN = f"{_IA}/gt446Andromeda-AcousticsAmongStars"
_GW = f"{_IA}/E4g004-Graphite412AGrainOfWheat"

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
        "description": "Celestial Catalyzer – La Luna e Le Stelle (9:55)",
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


def _get_audio_duration(path: Path) -> float | None:
    """Get the duration of an audio file in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(path),
            ],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            info = json.loads(result.stdout)
            return float(info["format"]["duration"])
    except Exception:
        pass
    return None


def _fetch_music_track(date_str: str) -> tuple[Path | None, float]:
    """
    Select a track deterministically from the catalogue using the date
    string as a seed, download it to a temporary file, and return a
    random start offset within the track.

    The temp file is the caller's responsibility to delete when done.

    Returns
    -------
    tuple[Path | None, float]
        (temp_track_path, start_offset_seconds)
    """
    # Use date hash for deterministic but varied selection
    seed = int(hashlib.md5(date_str.encode()).hexdigest(), 16)
    track_meta = TRACKS[seed % len(TRACKS)]

    print(f"[VIDEO] Downloading music: {track_meta['description']} ...")

    tmp_path = None
    try:
        resp = requests.get(track_meta["url"], timeout=120, stream=True)
        resp.raise_for_status()

        suffix = Path(track_meta["name"]).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = Path(tmp.name)
            for chunk in resp.iter_content(chunk_size=8192):
                tmp.write(chunk)
    except Exception as e:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        print(f"[VIDEO] Failed to download music ({e}). Creating silent video.")
        return None, 0.0

    track_path = tmp_path

    # Pick a random start offset within the track
    rng = random.Random(seed)
    track_duration = _get_audio_duration(track_path)

    start_offset = 0.0
    if track_duration and track_duration > TARGET_DURATION:
        max_start = track_duration - TARGET_DURATION
        start_offset = rng.uniform(0, max_start)

    print(f"[VIDEO] Selected: {track_meta['name']} (start at {start_offset:.1f}s)")
    return track_path, start_offset


def create_video(
    frame_paths: list[Path],
    output_path: str | Path = "output.mp4",
    date_str: str = "",
    fps: int | None = None,
    width: int = 1080,
    height: int = 1920,
    subtitle_text: str | None = None,
    duration: int = TARGET_DURATION,
) -> Path:
    """
    Stitch frames into a 30-second 9:16 vertical MP4 with date overlay
    and background music.

    Parameters
    ----------
    frame_paths : list[Path]
        Ordered list of PNG frame files.
    output_path : str | Path
        Where to write the final video.
    date_str : str
        Date string to overlay on the video (e.g. "2026-02-06").
    fps : int | None
        Playback frame-rate. If None, auto-calculated for 30s duration.
    width : int
        Output width (default 1080 for 9:16).
    height : int
        Output height (default 1920 for 9:16).
    subtitle_text : str | None
        Custom subtitle text. If None, uses the default.
    duration : int
        Target video duration in seconds (default 30).

    Returns
    -------
    Path
        Absolute path to the generated video.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if len(frame_paths) < 2:
        raise ValueError("Need at least 2 frames to create a video.")

    frame_dir = frame_paths[0].parent
    pattern = str(frame_dir / "frame_%03d.png")
    total_frames = len(frame_paths)

    # Auto-calculate FPS to hit target duration
    if fps is None:
        fps_calc = total_frames / duration
        # Clamp to a reasonable minimum to avoid FFmpeg issues
        fps_calc = max(fps_calc, 0.1)
    else:
        fps_calc = fps

    actual_duration = total_frames / fps_calc

    print(f"[VIDEO] Creating {width}x{height} video from {total_frames} frames")
    print(f"[VIDEO] Framerate: {fps_calc:.3f} fps | Duration: {actual_duration:.1f}s")
    print(f"[VIDEO] Date overlay: {date_str}")

    # ── Video stream ─────────────────────────────────────────────
    video = ffmpeg.input(pattern, framerate=fps_calc)

    # Scale to fit width, maintain aspect ratio
    video = ffmpeg.filter(video, "scale", width, -1)

    # Pad to full 9:16 canvas, centered vertically
    video = ffmpeg.filter(
        video, "pad",
        width, height,
        "(ow-iw)/2", "(oh-ih)/2",
        color="black"
    )

    # Draw date text overlay at the top
    if date_str:
        from datetime import datetime
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            display_date = dt.strftime("%B %d, %Y")
        except ValueError:
            display_date = date_str

        video = ffmpeg.filter(
            video, "drawtext",
            text=display_date,
            fontsize=48,
            fontcolor="white",
            borderw=3,
            bordercolor="black",
            x="(w-text_w)/2",
            y=300,
            font="Arial",
        )

        sub = subtitle_text if subtitle_text else "NASA EPIC - View from ~1.5 million km above Earth"
        video = ffmpeg.filter(
            video, "drawtext",
            text=sub,
            fontsize=28,
            fontcolor="white@0.8",
            borderw=2,
            bordercolor="black",
            x="(w-text_w)/2",
            y=350,
            font="Arial",
        )

    # ── Audio stream ─────────────────────────────────────────────
    music_track, start_offset = _fetch_music_track(date_str)

    if music_track:
        print(f"[VIDEO] Adding music: {music_track.name} (offset {start_offset:.1f}s)")
        # Input audio from random offset, trim to video duration, fade out last 3s
        audio = ffmpeg.input(str(music_track), ss=start_offset, t=actual_duration)
        fade_start = max(0, actual_duration - 3)
        audio = ffmpeg.filter(audio, "afade", t="out", st=fade_start, d=3)

        # Mux video + audio
        stream = ffmpeg.output(
            video, audio,
            str(output_path),
            vcodec="libx264",
            acodec="aac",
            audio_bitrate="192k",
            pix_fmt="yuv420p",
            preset="slow",
            crf=18,
            movflags="+faststart",
            shortest=None,  # end when shortest stream ends
        )
    else:
        print("[VIDEO] No music available. Creating silent video.")
        stream = ffmpeg.output(
            video,
            str(output_path),
            vcodec="libx264",
            pix_fmt="yuv420p",
            preset="slow",
            crf=18,
            movflags="+faststart",
        )

    stream = ffmpeg.overwrite_output(stream)

    print("[VIDEO] Running FFmpeg...")
    ffmpeg.run(stream, quiet=True)

    # Clean up the temporary music file now that FFmpeg is done
    if music_track and music_track.exists():
        music_track.unlink()

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"[VIDEO] Done -> {output_path} ({file_size_mb:.1f} MB)")
    return output_path.resolve()
