"""
Video engine – converts a sequence of EPIC Earth frames into an
Instagram-ready 1:1 H.264 MP4 using FFmpeg (via ffmpeg-python).
"""

import ffmpeg
from pathlib import Path


def create_video(
    frame_paths: list[Path],
    output_path: str | Path = "output.mp4",
    fps: int = 3,
    size: int = 1080,
) -> Path:
    """
    Stitch frames into a square MP4 suitable for Instagram.

    Parameters
    ----------
    frame_paths : list[Path]
        Ordered list of PNG frame files.
    output_path : str | Path
        Where to write the final video.
    fps : int
        Playback frame-rate (3 for a slow, cinematic feel).
    size : int
        Output dimension (square). Instagram prefers 1080x1080.

    Returns
    -------
    Path
        Absolute path to the generated video.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if len(frame_paths) < 2:
        raise ValueError("Need at least 2 frames to create a video.")

    # Use the first frame's parent dir with a glob pattern
    frame_dir = frame_paths[0].parent
    pattern = str(frame_dir / "frame_%03d.png")

    total_frames = len(frame_paths)
    duration = total_frames / fps  # total video length in seconds

    print(f"[VIDEO] Creating {size}x{size} video @ {fps}fps from {total_frames} frames")
    print(f"[VIDEO] Total duration: {duration:.1f}s")

    # Build FFmpeg pipeline
    stream = ffmpeg.input(pattern, framerate=fps)

    # Center-crop to square (EPIC images are 2048x2048 already, but be safe)
    stream = ffmpeg.filter(stream, "crop", "min(iw,ih)", "min(iw,ih)")
    # Scale to target size
    stream = ffmpeg.filter(stream, "scale", size, size)

    # Output with Instagram-friendly encoding settings
    stream = ffmpeg.output(
        stream,
        str(output_path),
        vcodec="libx264",
        pix_fmt="yuv420p",
        preset="slow",
        crf=18,
        movflags="+faststart",
    )

    # Overwrite if exists
    stream = ffmpeg.overwrite_output(stream)

    print("[VIDEO] Running FFmpeg...")
    ffmpeg.run(stream, quiet=True)

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"[VIDEO] Done → {output_path} ({file_size_mb:.1f} MB)")
    return output_path.resolve()
