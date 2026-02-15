"""
TUI (Text User Interface) for EPIC Earth Bot.

Provides an interactive CLI menu for managing videos, uploads,
and the full pipeline. Uses 'rich' for rendering and standard
input for navigation.
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime, timedelta, timezone

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm, IntPrompt
from rich import box

console = Console()

# Directories (same as main.py)
FRAMES_DIR = Path("frames")
OUTPUT_DIR = Path("output")
LOOKBACK_DAYS = 14


# ── Helpers ──────────────────────────────────────────────────────

def _get_api_key() -> str | None:
    from dotenv import load_dotenv
    load_dotenv()
    return os.getenv("NASA_API_KEY")


def _get_recent_dates() -> list[str]:
    """Fetch recent EPIC dates from NASA API."""
    from utils.nasa_api import get_available_dates
    api_key = _get_api_key()
    all_dates = get_available_dates(api_key)
    today = datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=LOOKBACK_DAYS)
    recent = [
        d for d in all_dates
        if cutoff <= datetime.strptime(d, "%Y-%m-%d").date() <= today
    ]
    recent.sort()
    return recent


def _get_youtube_service():
    """Get authenticated YouTube service, or None on failure."""
    try:
        from utils.youtube_upload import get_authenticated_service
        return get_authenticated_service()
    except Exception as e:
        console.print(f"[red]YouTube authentication failed: {e}[/red]")
        return None


def _clear():
    """Clear the terminal."""
    os.system("cls" if os.name == "nt" else "clear")


def _pause():
    """Wait for user to press Enter."""
    console.print()
    Prompt.ask("[dim]Press Enter to continue[/dim]", default="")


def _format_date_display(date_str: str) -> str:
    """Format YYYY-MM-DD into a nice display string."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%B %d, %Y")
    except ValueError:
        return date_str


# ── Main Menu ────────────────────────────────────────────────────

def show_main_menu():
    """Display and handle the main TUI menu."""
    while True:
        _clear()
        console.print(Panel(
            "[bold cyan]EPIC Earth Bot[/bold cyan]\n"
            "[dim]NASA EPIC Daily Earth Time-lapse Manager[/dim]",
            box=box.DOUBLE,
            padding=(1, 4),
        ))

        console.print()
        console.print("[bold]Main Menu[/bold]")
        console.print()
        console.print("  [cyan]1[/cyan]  Dashboard        - View status of all tracked dates")
        console.print("  [cyan]2[/cyan]  Auto Run          - Run full pipeline (create + upload)")
        console.print("  [cyan]3[/cyan]  Manage Videos     - Browse and manage individual dates")
        console.print("  [cyan]4[/cyan]  Batch Operations  - Create/upload all missing at once")
        console.print("  [cyan]5[/cyan]  YouTube Sync      - Sync tracking with YouTube channel")
        console.print("  [cyan]6[/cyan]  Settings          - View/edit configuration")
        console.print("  [cyan]0[/cyan]  Exit")
        console.print()

        choice = Prompt.ask("Select", choices=["0", "1", "2", "3", "4", "5", "6"], default="1")

        if choice == "0":
            console.print("[dim]Goodbye![/dim]")
            break
        elif choice == "1":
            show_dashboard()
        elif choice == "2":
            run_auto_pipeline()
        elif choice == "3":
            manage_videos_menu()
        elif choice == "4":
            batch_operations_menu()
        elif choice == "5":
            youtube_sync()
        elif choice == "6":
            show_settings()


# ── Dashboard ────────────────────────────────────────────────────

def show_dashboard():
    """Show status overview of all dates in the last 14 days."""
    _clear()
    console.print(Panel("[bold]Dashboard[/bold]", box=box.ROUNDED))

    from utils.tracking import get_entry, is_video_created, is_uploaded

    with console.status("[cyan]Fetching EPIC dates from NASA...[/cyan]"):
        try:
            dates = _get_recent_dates()
        except Exception as e:
            console.print(f"[red]Failed to fetch dates: {e}[/red]")
            _pause()
            return

    table = Table(box=box.SIMPLE_HEAVY, show_lines=False, padding=(0, 2))
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Date", style="bold", width=14)
    table.add_column("Display", width=22)
    table.add_column("Video", width=10, justify="center")
    table.add_column("Uploaded", width=10, justify="center")
    table.add_column("YouTube ID", width=14)
    table.add_column("Video File", width=12, justify="center")

    stats = {"total": len(dates), "videos": 0, "uploaded": 0, "missing_video": 0, "missing_upload": 0}

    for i, d in enumerate(dates, 1):
        entry = get_entry(d) or {}
        has_video = is_video_created(d)
        has_upload = is_uploaded(d)

        video_status = "[green]YES[/green]" if has_video else "[red]NO[/red]"
        upload_status = "[green]YES[/green]" if has_upload else "[yellow]NO[/yellow]"
        yt_id = entry.get("youtube_video_id", "-")

        # Check if video file actually exists
        video_path = entry.get("video_path", "")
        file_exists = Path(video_path).exists() if video_path else False
        file_status = "[green]exists[/green]" if file_exists else "[red]missing[/red]" if video_path else "[dim]-[/dim]"

        if has_video:
            stats["videos"] += 1
        else:
            stats["missing_video"] += 1
        if has_upload:
            stats["uploaded"] += 1
        elif has_video:
            stats["missing_upload"] += 1

        table.add_row(str(i), d, _format_date_display(d), video_status, upload_status, yt_id, file_status)

    console.print(table)
    console.print()

    # Summary bar
    summary = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    summary.add_column("Label", style="bold")
    summary.add_column("Value")
    summary.add_row("Total Dates", str(stats["total"]))
    summary.add_row("Videos Created", f"[green]{stats['videos']}[/green]")
    summary.add_row("Missing Videos", f"[red]{stats['missing_video']}[/red]" if stats["missing_video"] else "[green]0[/green]")
    summary.add_row("Uploaded to YouTube", f"[green]{stats['uploaded']}[/green]")
    summary.add_row("Awaiting Upload", f"[yellow]{stats['missing_upload']}[/yellow]" if stats["missing_upload"] else "[green]0[/green]")
    console.print(summary)

    _pause()


# ── Auto Run ─────────────────────────────────────────────────────

def run_auto_pipeline():
    """Run the full auto pipeline (same as main.py auto mode)."""
    _clear()
    console.print(Panel("[bold]Auto Run - Full Pipeline[/bold]", box=box.ROUNDED))
    console.print("[dim]This will create all missing videos and upload them to YouTube.[/dim]")
    console.print()

    if not Confirm.ask("Proceed with auto run?", default=True):
        return

    # Import and run the main pipeline functions
    from main import get_recent_epic_dates, create_missing_videos, upload_missing_videos
    from utils.tracking import cleanup_old_entries, print_summary

    api_key = _get_api_key()

    try:
        console.print("\n[bold cyan]Step 1:[/bold cyan] Fetching EPIC dates...")
        recent_dates = get_recent_epic_dates(api_key)
        if not recent_dates:
            console.print("[yellow]No recent dates found.[/yellow]")
            _pause()
            return

        console.print(f"\n[bold cyan]Step 2:[/bold cyan] Creating missing videos...")
        created = create_missing_videos(recent_dates, api_key)
        console.print(f"  Videos created: [green]{created}[/green]")

        console.print(f"\n[bold cyan]Step 3:[/bold cyan] Uploading to YouTube...")
        uploaded = upload_missing_videos(recent_dates)
        console.print(f"  Videos uploaded: [green]{uploaded}[/green]")

        cleanup_old_entries(keep_days=30)

        console.print(Panel(
            f"[green]Pipeline complete![/green]\n"
            f"Created: {created}  |  Uploaded: {uploaded}",
            box=box.ROUNDED
        ))

    except Exception as e:
        console.print(f"[red]Pipeline error: {e}[/red]")

    _pause()


# ── Manage Videos Menu ───────────────────────────────────────────

def manage_videos_menu():
    """Browse dates and manage individual videos."""
    while True:
        _clear()
        console.print(Panel("[bold]Manage Videos[/bold]", box=box.ROUNDED))

        from utils.tracking import get_entry, is_video_created, is_uploaded

        with console.status("[cyan]Fetching dates...[/cyan]"):
            try:
                dates = _get_recent_dates()
            except Exception as e:
                console.print(f"[red]Failed to fetch dates: {e}[/red]")
                _pause()
                return

        # Compact date list
        table = Table(box=box.SIMPLE, show_lines=False, padding=(0, 1))
        table.add_column("#", style="dim", width=4, justify="right")
        table.add_column("Date", width=14)
        table.add_column("Video", width=8, justify="center")
        table.add_column("Upload", width=8, justify="center")

        for i, d in enumerate(dates, 1):
            has_video = is_video_created(d)
            has_upload = is_uploaded(d)
            v = "[green]YES[/green]" if has_video else "[red]NO[/red]"
            u = "[green]YES[/green]" if has_upload else "[yellow]NO[/yellow]"
            table.add_row(str(i), d, v, u)

        console.print(table)
        console.print()
        console.print("Enter a [cyan]number[/cyan] to manage that date, or [cyan]0[/cyan] to go back.")
        console.print()

        choice = Prompt.ask("Select date #", default="0")
        if choice == "0":
            return

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(dates):
                manage_single_date(dates[idx])
            else:
                console.print("[red]Invalid selection.[/red]")
                _pause()
        except ValueError:
            console.print("[red]Please enter a number.[/red]")
            _pause()


def manage_single_date(date_str: str):
    """Full management interface for a single date."""
    while True:
        _clear()
        from utils.tracking import get_entry, is_video_created, is_uploaded
        from utils.youtube_upload import make_video_title, make_video_description

        entry = get_entry(date_str) or {}
        has_video = is_video_created(date_str)
        has_upload = is_uploaded(date_str)

        # Header
        console.print(Panel(
            f"[bold]{_format_date_display(date_str)}[/bold]  ({date_str})",
            box=box.DOUBLE,
        ))

        # Status info
        info = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        info.add_column("Field", style="bold", width=20)
        info.add_column("Value")

        info.add_row("Video Created", "[green]Yes[/green]" if has_video else "[red]No[/red]")
        video_path = entry.get("video_path", "-")
        if video_path != "-":
            exists = Path(video_path).exists()
            file_info = f"{video_path}"
            if exists:
                size_mb = Path(video_path).stat().st_size / (1024 * 1024)
                file_info += f" [dim]({size_mb:.1f} MB)[/dim]"
            else:
                file_info += " [red](FILE MISSING)[/red]"
            info.add_row("Video Path", file_info)
        info.add_row("Created At", entry.get("created_at", "-"))
        info.add_row("YouTube Uploaded", "[green]Yes[/green]" if has_upload else "[yellow]No[/yellow]")
        yt_id = entry.get("youtube_video_id", "-")
        info.add_row("YouTube ID", yt_id)
        if yt_id and yt_id != "-":
            info.add_row("YouTube URL", f"https://www.youtube.com/watch?v={yt_id}")
        info.add_row("Uploaded At", entry.get("uploaded_at", "-"))

        # Show what the title/description will be
        info.add_row("", "")
        info.add_row("Video Title", make_video_title(date_str))
        desc = make_video_description(date_str)
        # Truncate for display
        info.add_row("Description", desc[:80] + "..." if len(desc) > 80 else desc)

        console.print(info)
        console.print()

        # Actions
        console.print("[bold]Actions:[/bold]")
        console.print()

        actions = []
        if not has_video:
            actions.append(("1", "Create Video", "create"))
        else:
            actions.append(("1", "Regenerate Video", "regenerate"))

        if has_video and not has_upload:
            actions.append(("2", "Upload to YouTube", "upload"))
        elif has_upload:
            actions.append(("2", "Re-upload to YouTube (delete old + upload new)", "reupload"))

        if has_upload:
            actions.append(("3", "Remove from YouTube", "remove_yt"))

        if has_upload:
            actions.append(("4", "Edit YouTube Title/Description", "edit_meta"))

        if has_video:
            actions.append(("5", "Edit Video Overlay Text", "edit_overlay"))

        if has_video:
            actions.append(("6", "Delete Local Video File", "delete_local"))

        actions.append(("0", "Back", "back"))

        for key, label, _ in actions:
            console.print(f"  [cyan]{key}[/cyan]  {label}")
        console.print()

        valid_keys = [a[0] for a in actions]
        choice = Prompt.ask("Select action", choices=valid_keys, default="0")

        action = next(a[2] for a in actions if a[0] == choice)

        if action == "back":
            return
        elif action == "create":
            _action_create_video(date_str)
        elif action == "regenerate":
            _action_regenerate_video(date_str)
        elif action == "upload":
            _action_upload_video(date_str)
        elif action == "reupload":
            _action_reupload_video(date_str)
        elif action == "remove_yt":
            _action_remove_from_youtube(date_str)
        elif action == "edit_meta":
            _action_edit_youtube_metadata(date_str)
        elif action == "edit_overlay":
            _action_edit_overlay(date_str)
        elif action == "delete_local":
            _action_delete_local(date_str)


# ── Single-Date Actions ─────────────────────────────────────────

def _action_create_video(date_str: str):
    """Create video for a date that doesn't have one."""
    from utils.nasa_api import get_images_metadata_for_date, download_images
    from utils.video_engine import create_video
    from utils.tracking import mark_video_created

    api_key = _get_api_key()
    console.print()

    try:
        with console.status(f"[cyan]Fetching EPIC images for {date_str}...[/cyan]"):
            metadata = get_images_metadata_for_date(date_str, api_key)

        if not metadata:
            console.print(f"[yellow]No images available for {date_str}.[/yellow]")
            _pause()
            return

        console.print(f"Found [green]{len(metadata)}[/green] frames.")

        with console.status("[cyan]Downloading frames...[/cyan]"):
            frames = download_images(metadata, FRAMES_DIR)

        if len(frames) < 2:
            console.print("[yellow]Not enough frames to create a video.[/yellow]")
            _pause()
            return

        OUTPUT_DIR.mkdir(exist_ok=True)
        video_filename = f"epic_earth_{date_str}.mp4"
        output_path = OUTPUT_DIR / video_filename

        console.print(f"Creating video with [cyan]{len(frames)}[/cyan] frames...")
        video_path = create_video(
            frame_paths=frames,
            output_path=str(output_path),
            date_str=date_str,
            fps=12,
        )

        mark_video_created(date_str, str(video_path))
        console.print(f"[green]Video created successfully![/green] -> {video_path}")

    except Exception as e:
        console.print(f"[red]Failed: {e}[/red]")
    finally:
        if FRAMES_DIR.exists():
            shutil.rmtree(FRAMES_DIR)

    _pause()


def _action_regenerate_video(date_str: str):
    """Delete and recreate a video with fresh frames."""
    from utils.tracking import get_entry, unmark_video_created

    console.print()
    entry = get_entry(date_str) or {}
    video_path = entry.get("video_path", "")

    console.print("[yellow]This will delete the existing video and create a new one.[/yellow]")

    # Ask for custom overlay text
    default_overlay = date_str
    custom_overlay = Prompt.ask(
        "Custom overlay date text (or Enter for default)",
        default=default_overlay
    )

    # Ask for custom subtitle
    default_subtitle = ""
    custom_subtitle = Prompt.ask(
        "Custom subtitle text (or Enter for default)",
        default=default_subtitle
    )

    if not Confirm.ask("Proceed with regeneration?", default=True):
        return

    # Delete old video file
    if video_path and Path(video_path).exists():
        Path(video_path).unlink()
        console.print(f"[dim]Deleted old video: {video_path}[/dim]")

    unmark_video_created(date_str)

    # Recreate with custom overlay if provided
    from utils.nasa_api import get_images_metadata_for_date, download_images
    from utils.video_engine import create_video
    from utils.tracking import mark_video_created

    api_key = _get_api_key()

    try:
        with console.status(f"[cyan]Fetching EPIC images for {date_str}...[/cyan]"):
            metadata = get_images_metadata_for_date(date_str, api_key)

        if not metadata:
            console.print(f"[yellow]No images available for {date_str}.[/yellow]")
            _pause()
            return

        with console.status("[cyan]Downloading frames...[/cyan]"):
            frames = download_images(metadata, FRAMES_DIR)

        if len(frames) < 2:
            console.print("[yellow]Not enough frames.[/yellow]")
            _pause()
            return

        OUTPUT_DIR.mkdir(exist_ok=True)
        video_filename = f"epic_earth_{date_str}.mp4"
        output_path = OUTPUT_DIR / video_filename

        # Use custom overlay text
        overlay_date = custom_overlay if custom_overlay != date_str else date_str

        console.print(f"Creating video with [cyan]{len(frames)}[/cyan] frames...")
        video_path = create_video(
            frame_paths=frames,
            output_path=str(output_path),
            date_str=overlay_date,
            fps=12,
            subtitle_text=custom_subtitle if custom_subtitle else None,
        )

        mark_video_created(date_str, str(video_path))
        console.print(f"[green]Video regenerated successfully![/green]")

    except Exception as e:
        console.print(f"[red]Failed: {e}[/red]")
    finally:
        if FRAMES_DIR.exists():
            shutil.rmtree(FRAMES_DIR)

    _pause()


def _action_upload_video(date_str: str):
    """Upload a video to YouTube."""
    from utils.tracking import get_entry, mark_uploaded
    from utils.youtube_upload import upload_video

    entry = get_entry(date_str) or {}
    video_path = entry.get("video_path", "")

    if not video_path or not Path(video_path).exists():
        console.print("[red]Video file not found. Create the video first.[/red]")
        _pause()
        return

    console.print()
    privacy = Prompt.ask("Privacy", choices=["public", "unlisted", "private"], default="public")

    if not Confirm.ask(f"Upload {date_str} as [bold]{privacy}[/bold]?", default=True):
        return

    service = _get_youtube_service()
    if not service:
        _pause()
        return

    try:
        video_id = upload_video(service, video_path, date_str, privacy=privacy)
        if video_id:
            mark_uploaded(date_str, video_id)
            console.print(f"[green]Uploaded! Video ID: {video_id}[/green]")
            console.print(f"[dim]https://www.youtube.com/watch?v={video_id}[/dim]")
        else:
            console.print("[red]Upload failed (no video ID returned).[/red]")
    except Exception as e:
        console.print(f"[red]Upload error: {e}[/red]")

    _pause()


def _action_reupload_video(date_str: str):
    """Delete from YouTube and re-upload."""
    console.print()
    console.print("[yellow]This will delete the current YouTube video and upload a new one.[/yellow]")

    if not Confirm.ask("Are you sure?", default=False):
        return

    # First delete from YouTube
    _action_remove_from_youtube(date_str, pause=False)

    # Then upload
    _action_upload_video(date_str)


def _action_remove_from_youtube(date_str: str, pause: bool = True):
    """Remove a video from YouTube."""
    from utils.tracking import get_entry, unmark_uploaded
    from utils.youtube_upload import delete_video

    entry = get_entry(date_str) or {}
    video_id = entry.get("youtube_video_id")

    if not video_id:
        console.print("[yellow]No YouTube video ID found in tracking.[/yellow]")
        if pause:
            _pause()
        return

    console.print()
    if not Confirm.ask(f"Delete YouTube video [bold]{video_id}[/bold]?", default=False):
        return

    service = _get_youtube_service()
    if not service:
        if pause:
            _pause()
        return

    try:
        success = delete_video(service, video_id)
        if success:
            unmark_uploaded(date_str)
            console.print(f"[green]Removed from YouTube and tracking updated.[/green]")
        else:
            console.print("[red]Failed to delete from YouTube.[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

    if pause:
        _pause()


def _action_edit_youtube_metadata(date_str: str):
    """Edit the title and description of an existing YouTube video."""
    from utils.tracking import get_entry
    from utils.youtube_upload import (
        make_video_title, make_video_description, update_video_metadata
    )

    entry = get_entry(date_str) or {}
    video_id = entry.get("youtube_video_id")

    if not video_id:
        console.print("[red]No YouTube video ID found.[/red]")
        _pause()
        return

    current_title = make_video_title(date_str)
    current_desc = make_video_description(date_str)

    console.print()
    console.print(f"[bold]Current title:[/bold] {current_title}")
    console.print(f"[bold]Current description:[/bold]")
    console.print(f"[dim]{current_desc}[/dim]")
    console.print()

    new_title = Prompt.ask("New title (Enter to keep current)", default="")
    new_desc = Prompt.ask("New description (Enter to keep current)", default="")

    if not new_title and not new_desc:
        console.print("[dim]No changes.[/dim]")
        _pause()
        return

    service = _get_youtube_service()
    if not service:
        _pause()
        return

    try:
        success = update_video_metadata(
            service, video_id,
            title=new_title if new_title else None,
            description=new_desc if new_desc else None,
        )
        if success:
            console.print("[green]YouTube metadata updated![/green]")
        else:
            console.print("[red]Failed to update metadata.[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

    _pause()


def _action_edit_overlay(date_str: str):
    """Edit the overlay text and regenerate the video."""
    console.print()
    console.print("[yellow]This will regenerate the video with new overlay text.[/yellow]")
    console.print("[dim]The video will be re-encoded. If uploaded, you'll need to re-upload.[/dim]")
    console.print()

    # Just delegate to regenerate which already prompts for custom overlay  
    _action_regenerate_video(date_str)


def _action_delete_local(date_str: str):
    """Delete the local video file."""
    from utils.tracking import get_entry, unmark_video_created

    entry = get_entry(date_str) or {}
    video_path = entry.get("video_path", "")

    if not video_path or not Path(video_path).exists():
        console.print("[yellow]No local video file found.[/yellow]")
        _pause()
        return

    size_mb = Path(video_path).stat().st_size / (1024 * 1024)
    console.print()
    console.print(f"File: {video_path} ({size_mb:.1f} MB)")

    if not Confirm.ask("Delete this file?", default=False):
        return

    try:
        Path(video_path).unlink()
        unmark_video_created(date_str)
        console.print("[green]Deleted.[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

    _pause()


# ── Batch Operations ─────────────────────────────────────────────

def batch_operations_menu():
    """Menu for batch create/upload operations."""
    while True:
        _clear()
        console.print(Panel("[bold]Batch Operations[/bold]", box=box.ROUNDED))
        console.print()
        console.print("  [cyan]1[/cyan]  Create all missing videos")
        console.print("  [cyan]2[/cyan]  Upload all unuploaded videos")
        console.print("  [cyan]3[/cyan]  Create + Upload all (full pipeline)")
        console.print("  [cyan]4[/cyan]  Regenerate ALL videos")
        console.print("  [cyan]0[/cyan]  Back")
        console.print()

        choice = Prompt.ask("Select", choices=["0", "1", "2", "3", "4"], default="0")

        if choice == "0":
            return
        elif choice == "1":
            _batch_create_videos()
        elif choice == "2":
            _batch_upload_videos()
        elif choice == "3":
            _batch_create_videos()
            _batch_upload_videos()
        elif choice == "4":
            _batch_regenerate_all()


def _batch_create_videos():
    """Create all missing videos."""
    from main import create_missing_videos
    api_key = _get_api_key()

    console.print()
    with console.status("[cyan]Fetching dates...[/cyan]"):
        try:
            dates = _get_recent_dates()
        except Exception as e:
            console.print(f"[red]Failed: {e}[/red]")
            _pause()
            return

    from utils.tracking import get_dates_needing_video
    need = get_dates_needing_video(dates)
    console.print(f"Dates needing videos: [bold]{len(need)}[/bold]")

    if not need:
        console.print("[green]All videos are created![/green]")
        _pause()
        return

    for d in need:
        console.print(f"  - {d}")

    console.print()
    if not Confirm.ask("Create all missing videos?", default=True):
        return

    created = create_missing_videos(dates, api_key)
    console.print(f"\n[green]Created {created} videos.[/green]")
    _pause()


def _batch_upload_videos():
    """Upload all unuploaded videos."""
    from main import upload_missing_videos

    console.print()
    with console.status("[cyan]Fetching dates...[/cyan]"):
        try:
            dates = _get_recent_dates()
        except Exception as e:
            console.print(f"[red]Failed: {e}[/red]")
            _pause()
            return

    from utils.tracking import get_dates_needing_upload
    need = get_dates_needing_upload(dates)
    console.print(f"Videos awaiting upload: [bold]{len(need)}[/bold]")

    if not need:
        console.print("[green]All videos are uploaded![/green]")
        _pause()
        return

    for d in need:
        console.print(f"  - {d}")

    console.print()
    if not Confirm.ask("Upload all?", default=True):
        return

    uploaded = upload_missing_videos(dates)
    console.print(f"\n[green]Uploaded {uploaded} videos.[/green]")
    _pause()


def _batch_regenerate_all():
    """Regenerate ALL videos for recent dates."""
    from utils.tracking import unmark_video_created, get_entry
    from main import create_missing_videos

    console.print()
    with console.status("[cyan]Fetching dates...[/cyan]"):
        try:
            dates = _get_recent_dates()
        except Exception as e:
            console.print(f"[red]Failed: {e}[/red]")
            _pause()
            return

    console.print(f"[yellow]This will regenerate ALL {len(dates)} videos.[/yellow]")
    console.print("[yellow]Existing video files will be overwritten.[/yellow]")
    console.print()

    if not Confirm.ask("Are you absolutely sure?", default=False):
        return

    # Unmark all, delete old files
    for d in dates:
        entry = get_entry(d) or {}
        vp = entry.get("video_path", "")
        if vp and Path(vp).exists():
            Path(vp).unlink()
        unmark_video_created(d)

    api_key = _get_api_key()
    created = create_missing_videos(dates, api_key)
    console.print(f"\n[green]Regenerated {created} videos.[/green]")
    _pause()


# ── YouTube Sync ─────────────────────────────────────────────────

def youtube_sync():
    """Sync local tracking state with actual YouTube channel uploads."""
    _clear()
    console.print(Panel("[bold]YouTube Sync[/bold]", box=box.ROUNDED))
    console.print("[dim]Checks YouTube channel and updates local tracking to match.[/dim]")
    console.print()

    service = _get_youtube_service()
    if not service:
        _pause()
        return

    from utils.youtube_upload import get_uploaded_video_titles, make_video_title
    from utils.tracking import get_entry, mark_uploaded, unmark_uploaded, is_uploaded

    with console.status("[cyan]Fetching YouTube uploads...[/cyan]"):
        try:
            yt_titles = get_uploaded_video_titles(service)
        except Exception as e:
            console.print(f"[red]Failed: {e}[/red]")
            _pause()
            return

    with console.status("[cyan]Fetching EPIC dates...[/cyan]"):
        try:
            dates = _get_recent_dates()
        except Exception as e:
            console.print(f"[red]Failed: {e}[/red]")
            _pause()
            return

    synced = 0
    desynced = 0

    for d in dates:
        title = make_video_title(d)
        on_youtube = title in yt_titles
        in_tracking = is_uploaded(d)

        if on_youtube and not in_tracking:
            video_id = yt_titles[title]
            mark_uploaded(d, video_id)
            console.print(f"  [green]+[/green] {d}: Found on YouTube (ID: {video_id}), updated tracking")
            synced += 1
        elif not on_youtube and in_tracking:
            unmark_uploaded(d)
            console.print(f"  [yellow]-[/yellow] {d}: Not on YouTube but tracked as uploaded. Cleared.")
            desynced += 1

    if synced == 0 and desynced == 0:
        console.print("[green]Tracking is in sync with YouTube![/green]")
    else:
        console.print(f"\nSync complete: [green]{synced} added[/green], [yellow]{desynced} cleared[/yellow]")

    _pause()


# ── Settings ─────────────────────────────────────────────────────

def show_settings():
    """Display current configuration."""
    _clear()
    console.print(Panel("[bold]Settings[/bold]", box=box.ROUNDED))

    from dotenv import load_dotenv
    load_dotenv()

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Setting", style="bold", width=25)
    table.add_column("Value")

    api_key = os.getenv("NASA_API_KEY", "")
    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "(not set)"
    table.add_row("NASA API Key", masked_key)

    from utils.youtube_upload import CLIENT_SECRETS_FILE, TOKEN_FILE
    table.add_row("Client Secrets", f"{'[green]exists' if CLIENT_SECRETS_FILE.exists() else '[red]MISSING'}[/]")
    table.add_row("OAuth Token", f"{'[green]exists' if TOKEN_FILE.exists() else '[yellow]not yet created'}[/]")

    from utils.tracking import TRACKING_FILE
    table.add_row("Tracking File", f"{'[green]exists' if TRACKING_FILE.exists() else '[yellow]will be created'}[/]")

    table.add_row("Output Directory", str(OUTPUT_DIR.resolve()))
    table.add_row("Lookback Days", str(LOOKBACK_DAYS))
    table.add_row("Video Resolution", "1080 x 1920 (9:16)")
    table.add_row("Video FPS", "12")

    # Count existing files
    output_count = len(list(OUTPUT_DIR.glob("epic_earth_*.mp4"))) if OUTPUT_DIR.exists() else 0
    total_size = sum(f.stat().st_size for f in OUTPUT_DIR.glob("epic_earth_*.mp4")) / (1024*1024) if OUTPUT_DIR.exists() else 0
    table.add_row("Local Videos", f"{output_count} files ({total_size:.0f} MB)")

    console.print(table)
    _pause()
