# EPIC Earth Bot

Automatically creates and uploads daily NASA EPIC Earth time-lapse videos to YouTube. The bot fetches images from NASA's [EPIC camera](https://epic.gsfc.nasa.gov/) aboard the DSCOVR satellite (orbiting ~1.5 million km from Earth), stitches them into 9:16 vertical videos with date overlays, and uploads them as YouTube Shorts.

Designed to run once daily — either locally or via GitHub Actions. Tracks state in `data/tracking.json` to avoid duplicating work, even if runs are missed for several days.

---

## Running Locally

### Prerequisites

- **Python 3.11+**
- **FFmpeg** installed and on your PATH
- A **NASA API key** (free at <https://api.nasa.gov/>)
- **YouTube OAuth2 credentials** (see [YouTube Setup](#youtube-setup) below)

### Setup

```bash
# Clone the repo
git clone https://github.com/mitchyc24/EPIC_Earth_Bot.git
cd EPIC_Earth_Bot

# Create a virtual environment and install dependencies
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt

# Create a .env file with your NASA API key
echo NASA_API_KEY=your_key_here > .env
```

### YouTube Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project (or select an existing one).
3. Enable the **YouTube Data API v3**.
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
5. Choose **Desktop app** as the application type.
6. Download the JSON file and save it as `Youtube/client_secrets.json`.

### First Run

```bash
python main.py
```

On first run a browser window will open asking you to authorize YouTube access. After consenting, an OAuth token is saved to `Youtube/oauth_token.json` for future runs.

The interactive TUI lets you create videos, upload, manage tracking, and more. For a fully automated (non-interactive) run:

```bash
python main.py --auto
```

### Refreshing an Expired YouTube Token

The OAuth token automatically refreshes itself using its refresh token. However, **if the refresh token is revoked or expires** (e.g. the Google Cloud project is in "Testing" mode — see [Getting Permanent Credentials](#getting-permanent-credentials-youtube-api-verification)), you need to re-authorize manually:

1. **Delete the old token:**
   ```bash
   del Youtube\oauth_token.json        # Windows
   # rm Youtube/oauth_token.json       # macOS / Linux
   ```
2. **Run the bot locally:**
   ```bash
   python main.py
   ```
3. A browser window will open — sign in and grant access again.
4. A new `Youtube/oauth_token.json` will be created automatically.
5. If you're using GitHub Actions, **update the `YOUTUBE_OAUTH_TOKEN` secret** with the contents of the new token file (see below).

---

## Running with GitHub Actions (Daily Automation)

The included workflow at `.github/workflows/daily.yml` runs the bot every day at 06:00 UTC and can also be triggered manually from the **Actions** tab.

### Required GitHub Secrets

Add these three secrets under **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|---|---|
| `NASA_API_KEY` | Your NASA API key |
| `YOUTUBE_CLIENT_SECRETS` | Full JSON contents of `Youtube/client_secrets.json` |
| `YOUTUBE_OAUTH_TOKEN` | Full JSON contents of `Youtube/oauth_token.json` (generated after first local run) |

### How It Works

1. The workflow checks out the repo, installs Python 3.11, FFmpeg, and pip dependencies.
2. It writes `client_secrets.json` and `oauth_token.json` from the GitHub Secrets into the `Youtube/` directory.
3. Runs `python main.py --auto` to create and upload any missing videos.
4. The `data/`, `output/`, and `Youtube/oauth_token.json` directories are **cached** between runs so tracking state, videos, and refreshed tokens persist.

### Updating the Token After Re-authorization

If the OAuth token expires and you re-authorize locally (see above), copy the new token into the GitHub secret:

```bash
# Print the token contents
type Youtube\oauth_token.json        # Windows
# cat Youtube/oauth_token.json       # macOS / Linux
```

Paste the output into the `YOUTUBE_OAUTH_TOKEN` secret in your repo settings.

---

## Getting Permanent Credentials (YouTube API Verification)

By default, Google Cloud projects in **"Testing"** status issue OAuth refresh tokens that expire after **7 days**. This means you'd need to re-authorize weekly. To get long-lived credentials:

1. **Add your Google account as a test user** under **APIs & Services → OAuth consent screen → Test users** — this can extend the token lifetime while still in testing mode.
2. **Submit your app for verification** by switching the publishing status from "Testing" to "In production" on the OAuth consent screen. This removes the 7-day expiry on refresh tokens.
   - Google will review the app's requested scopes (`youtube.upload`, `youtube.readonly`, `youtube`).
   - You may need to provide a privacy policy URL and a homepage for the app.
   - Review can take several days to a few weeks.
3. Once verified (or set to "In production" for internal/personal use), refresh tokens will not expire unless explicitly revoked, and the GitHub Actions workflow will run indefinitely without manual intervention.

> **Tip:** For a personal project that only accesses your own YouTube channel, switching to "In production" typically goes through quickly. Google may not require a full review if the app has a small number of users.

---

## Project Structure

```
├── main.py                    # Orchestrator — runs the full pipeline
├── requirements.txt           # Python dependencies
├── .env                       # NASA_API_KEY (gitignored)
├── .github/workflows/
│   └── daily.yml              # GitHub Actions daily workflow
├── data/
│   └── tracking.json          # Per-date state tracking (gitignored)
├── output/                    # Generated MP4 videos (gitignored)
├── utils/
│   ├── nasa_api.py            # NASA EPIC API client
│   ├── video_engine.py        # FFmpeg 9:16 video creation with date overlay
│   ├── tracking.py            # JSON-based state tracking
│   ├── youtube_upload.py      # YouTube Data API v3 OAuth2 + upload
│   └── tui.py                 # Interactive terminal UI
└── Youtube/
    ├── client_secrets.json    # OAuth2 client credentials (gitignored)
    └── oauth_token.json       # OAuth token with refresh token (gitignored)
```

## License

This project is for personal/educational use. NASA EPIC imagery is public domain.
