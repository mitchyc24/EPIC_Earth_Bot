"""
Video engine - converts a sequence of EPIC Earth frames into a
9:16 vertical (1080x1920) H.264 MP4 with date overlay and background
music, suitable for YouTube Shorts.

Uses FFmpeg via ffmpeg-python. The Earth (2048x2048 source) is
centered in the vertical frame with the date stamped at the top.
Each video is exactly 30 seconds with a different music track.
"""

import ffmpeg
import hashlib
import random
import subprocess
import json
from pathlib import Path

MUSIC_DIR = Path(__file__).parent.parent / "music"
TARGET_DURATION = 30  # seconds


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


def _pick_music_track(date_str: str) -> tuple[Path | None, float]:
    """
    Pick a music track and a random start offset.

    Uses the date string as a seed so the same date always gets the
    same track and offset, but different dates get different ones.

    Returns
    -------
    tuple[Path | None, float]
        (track_path, start_offset_seconds)
    """
    if not MUSIC_DIR.exists():
        return None, 0.0

    tracks = sorted([
        f for f in MUSIC_DIR.iterdir()
        if f.suffix.lower() in (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac")
    ])

    if not tracks:
        return None, 0.0

    # Use date hash for deterministic but varied selection
    seed = int(hashlib.md5(date_str.encode()).hexdigest(), 16)
    track = tracks[seed % len(tracks)]

    # Pick a random start offset within the track
    rng = random.Random(seed)
    track_duration = _get_audio_duration(track)

    start_offset = 0.0
    if track_duration and track_duration > TARGET_DURATION:
        max_start = track_duration - TARGET_DURATION
        start_offset = rng.uniform(0, max_start)

    print(f"[VIDEO] Selected music: {track.name} (start at {start_offset:.1f}s)")
    return track, start_offset


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
    music_track, start_offset = _pick_music_track(date_str)

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
        print("[VIDEO] No music tracks found in music/ directory. Creating silent video.")
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

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"[VIDEO] Done -> {output_path} ({file_size_mb:.1f} MB)")
    return output_path.resolve()
