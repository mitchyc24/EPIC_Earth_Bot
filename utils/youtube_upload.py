"""
YouTube upload module - handles OAuth2 authentication and video uploads
to YouTube using the YouTube Data API v3.

Features:
  - OAuth2 flow with persistent token storage
  - Upload videos with metadata (title, description, tags)
  - Check existing uploads to avoid duplicates
  - Retry logic for transient failures
"""

import os
import time
import json
from pathlib import Path
from datetime import datetime

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError


# Paths
YOUTUBE_DIR = Path(__file__).parent.parent / "Youtube"
CLIENT_SECRETS_FILE = YOUTUBE_DIR / "client_secrets.json"
TOKEN_FILE = YOUTUBE_DIR / "oauth_token.json"

# YouTube API settings
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly",
          "https://www.googleapis.com/auth/youtube"]  # full scope needed for delete/update

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


def get_authenticated_service():
    """
    Build and return an authenticated YouTube API service object.

    First run will open a browser for OAuth2 consent. Subsequent runs
    use the saved token from oauth_token.json.
    """
    creds = None

    # Load existing token
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    # Refresh or get new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[YOUTUBE] Refreshing expired OAuth token...")
            creds.refresh(Request())
        else:
            if not CLIENT_SECRETS_FILE.exists():
                raise FileNotFoundError(
                    f"YouTube client_secrets.json not found at {CLIENT_SECRETS_FILE}. "
                    "Please set up OAuth2 credentials for the YouTube Data API v3."
                )
            print("[YOUTUBE] Starting OAuth2 authorization flow...")
            print("[YOUTUBE] A browser window will open for you to authorize access.")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRETS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save credentials for next run
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print("[YOUTUBE] OAuth token saved for future use.")

    service = build("youtube", "v3", credentials=creds)
    print("[YOUTUBE] Authenticated successfully.")
    return service


def get_uploaded_video_titles(service) -> dict[str, str]:
    """
    Fetch all video titles from the authenticated channel.

    Returns a dict mapping video title -> video ID.
    This is used to check which dates already have uploads.
    """
    print("[YOUTUBE] Fetching existing uploads from channel...")

    # Get the channel's uploads playlist
    channels_response = service.channels().list(
        part="contentDetails",
        mine=True
    ).execute()

    if not channels_response.get("items"):
        print("[YOUTUBE] No channel found for authenticated user.")
        return {}

    uploads_playlist_id = (
        channels_response["items"][0]["contentDetails"]
        ["relatedPlaylists"]["uploads"]
    )

    # Paginate through all uploads
    title_to_id: dict[str, str] = {}
    next_page_token = None

    while True:
        playlist_response = service.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page_token
        ).execute()

        for item in playlist_response.get("items", []):
            title = item["snippet"]["title"]
            video_id = item["snippet"]["resourceId"]["videoId"]
            title_to_id[title] = video_id

        next_page_token = playlist_response.get("nextPageToken")
        if not next_page_token:
            break

    print(f"[YOUTUBE] Found {len(title_to_id)} existing uploads.")
    return title_to_id


def make_video_title(date_str: str) -> str:
    """Generate a consistent video title for a given date."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        formatted = dt.strftime("%B %d, %Y")
    except ValueError:
        formatted = date_str
    return f"Earth from Space - {formatted} | NASA EPIC"


def make_video_description(date_str: str) -> str:
    """Generate a video description for a given date."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        formatted = dt.strftime("%B %d, %Y")
    except ValueError:
        formatted = date_str

    return (
        f"A time-lapse of Earth on {formatted}, captured by NASA's EPIC camera "
        f"aboard the DSCOVR satellite, orbiting approximately 1.5 million km from Earth.\n\n"
        f"These images show the sunlit side of Earth as it rotates throughout the day.\n\n"
        f"Source: NASA EPIC (Earth Polychromatic Imaging Camera)\n"
        f"https://epic.gsfc.nasa.gov/\n\n"
        f"#NASA #Earth #Space #EPIC #DSCOVR #Timelapse #Shorts"
    )


def upload_video(
    service,
    video_path: str | Path,
    date_str: str,
    privacy: str = "public",
) -> str | None:
    """
    Upload a video to YouTube.

    Parameters
    ----------
    service
        Authenticated YouTube API service object.
    video_path : str | Path
        Path to the MP4 file to upload.
    date_str : str
        Date string (YYYY-MM-DD) for generating title/description.
    privacy : str
        Privacy status: "public", "unlisted", or "private".

    Returns
    -------
    str | None
        The YouTube video ID if successful, None otherwise.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        print(f"[YOUTUBE] Video file not found: {video_path}")
        return None

    title = make_video_title(date_str)
    description = make_video_description(date_str)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": [
                "NASA", "Earth", "Space", "EPIC", "DSCOVR",
                "timelapse", "time-lapse", "satellite", "astronomy",
                "science", "nature", "planet", "shorts"
            ],
            "categoryId": "28",  # Science & Technology
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 5,  # 5MB chunks
    )

    print(f"[YOUTUBE] Uploading: {title}")
    print(f"[YOUTUBE] File: {video_path} ({video_path.stat().st_size / 1024 / 1024:.1f} MB)")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            request = service.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    print(f"[YOUTUBE]   Upload progress: {progress}%")

            video_id = response["id"]
            print(f"[YOUTUBE] Upload complete! Video ID: {video_id}")
            print(f"[YOUTUBE] URL: https://www.youtube.com/watch?v={video_id}")
            return video_id

        except HttpError as e:
            print(f"[YOUTUBE] HTTP error on attempt {attempt}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES:
                print(f"[YOUTUBE] Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"[YOUTUBE] Upload failed after {MAX_RETRIES} attempts.")
                return None

        except Exception as e:
            print(f"[YOUTUBE] Unexpected error on attempt {attempt}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES:
                print(f"[YOUTUBE] Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"[YOUTUBE] Upload failed after {MAX_RETRIES} attempts.")
                return None

    return None


def check_already_uploaded(service, date_str: str) -> str | None:
    """
    Check if a video for the given date has already been uploaded.

    Returns the YouTube video ID if found, None otherwise.
    """
    title = make_video_title(date_str)
    existing = get_uploaded_video_titles(service)
    return existing.get(title)


def delete_video(service, video_id: str) -> bool:
    """
    Delete a video from YouTube by its video ID.

    Returns True if successful, False otherwise.
    """
    try:
        print(f"[YOUTUBE] Deleting video {video_id}...")
        service.videos().delete(id=video_id).execute()
        print(f"[YOUTUBE] Successfully deleted video {video_id}")
        return True
    except HttpError as e:
        print(f"[YOUTUBE] Failed to delete video {video_id}: {e}")
        return False
    except Exception as e:
        print(f"[YOUTUBE] Unexpected error deleting {video_id}: {e}")
        return False


def update_video_metadata(
    service,
    video_id: str,
    title: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
) -> bool:
    """
    Update the metadata of an existing YouTube video.

    Only provided fields are updated; others remain unchanged.
    Returns True if successful, False otherwise.
    """
    try:
        # First fetch current snippet
        response = service.videos().list(
            part="snippet",
            id=video_id
        ).execute()

        if not response.get("items"):
            print(f"[YOUTUBE] Video {video_id} not found.")
            return False

        snippet = response["items"][0]["snippet"]

        if title is not None:
            snippet["title"] = title
        if description is not None:
            snippet["description"] = description
        if tags is not None:
            snippet["tags"] = tags

        # categoryId is required for update
        if "categoryId" not in snippet:
            snippet["categoryId"] = "28"

        service.videos().update(
            part="snippet",
            body={"id": video_id, "snippet": snippet}
        ).execute()

        print(f"[YOUTUBE] Updated metadata for video {video_id}")
        return True

    except HttpError as e:
        print(f"[YOUTUBE] Failed to update video {video_id}: {e}")
        return False
    except Exception as e:
        print(f"[YOUTUBE] Unexpected error updating {video_id}: {e}")
        return False
