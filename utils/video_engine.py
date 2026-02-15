"""
Video engine - converts a sequence of EPIC Earth frames into a
9:16 vertical (1080x1920) H.264 MP4 with date overlay, suitable
for YouTube Shorts.

Uses FFmpeg via ffmpeg-python. The Earth (2048x2048 source) is
centered in the vertical frame with the date stamped at the bottom.
"""

import ffmpeg
from pathlib import Path


def create_video(
    frame_paths: list[Path],
    output_path: str | Path = "output.mp4",
    date_str: str = "",
    fps: int = 12,
    width: int = 1080,
    height: int = 1920,
    subtitle_text: str | None = None,
) -> Path:
    """
    Stitch frames into a 9:16 vertical MP4 with date overlay.

    Parameters
    ----------
    frame_paths : list[Path]
        Ordered list of PNG frame files.
    output_path : str | Path
        Where to write the final video.
    date_str : str
        Date string to overlay on the video (e.g. "2026-02-06").
    fps : int
        Playback frame-rate.
    width : int
        Output width (default 1080 for 9:16).
    height : int
        Output height (default 1920 for 9:16).
    subtitle_text : str | None
        Custom subtitle text. If None, uses the default.

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
    duration = total_frames / fps

    print(f"[VIDEO] Creating {width}x{height} video @ {fps}fps from {total_frames} frames")
    print(f"[VIDEO] Total duration: {duration:.1f}s | Date overlay: {date_str}")

    # Build FFmpeg filter chain:
    # 1. Scale source to fit width (Earth is 2048x2048, scale to 1080x1080)
    # 2. Pad to 1080x1920, centering the Earth vertically
    # 3. Overlay the date text at the bottom
    stream = ffmpeg.input(pattern, framerate=fps)

    # Scale to fit the width while maintaining aspect ratio
    stream = ffmpeg.filter(stream, "scale", width, -1)

    # Pad to full 9:16 canvas, centered vertically (black bars top/bottom)
    stream = ffmpeg.filter(
        stream, "pad",
        width, height,
        "(ow-iw)/2", "(oh-ih)/2",
        color="black"
    )

    # Draw date text overlay
    if date_str:
        # Format the date nicely
        from datetime import datetime
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            display_date = dt.strftime("%B %d, %Y")  # e.g. "February 06, 2026"
        except ValueError:
            display_date = date_str

        stream = ffmpeg.filter(
            stream, "drawtext",
            text=display_date,
            fontsize=48,
            fontcolor="white",
            borderw=3,
            bordercolor="black",
            x="(w-text_w)/2",
            y=40,
            font="Arial",
        )

        # Add a subtitle line
        sub = subtitle_text if subtitle_text else "NASA EPIC - View from ~1.5 million km above Earth"
        stream = ffmpeg.filter(
            stream, "drawtext",
            text=sub,
            fontsize=28,
            fontcolor="white@0.8",
            borderw=2,
            bordercolor="black",
            x="(w-text_w)/2",
            y=95,
            font="Arial",
        )

    # Output with YouTube-friendly encoding settings
    stream = ffmpeg.output(
        stream,
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
