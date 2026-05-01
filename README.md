# 🎥 Telegram YouTube downloader

A powerful Telegram bot that downloads YouTube videos and audio with multiple quality options, built with Python, yt-dlp, and Pyrogram.

**⚠️ Important:** This bot requires incognito browser cookies to prevent session conflicts with regular YouTube browsing and maintain reliability.

**🔧 Pyrogram-based:** This bot uses Telegram's User API (via Pyrogram) instead of the Bot API to bypass the strict 50MB file size limit, allowing downloads up to 2GB.

## ✨ Features

### 🎬 Video downloads
- **Multiple Quality Options**: Choose from available video resolutions (144p to 4K+)
- **Format Support**: Automatic MP4 conversion with audio merging
- **Progress Tracking**: Real-time download and upload progress bars

### 🎵 Audio downloads
- **MP3 Extraction**: High-quality MP3 audio extraction
- **Metadata Integration**: Automatic ID3 tags with title, artist, and album art
- **Thumbnail Support**: Downloads and embeds video thumbnails as album art

### 🛡️ Security & control
- **Optional User Whitelist**: Toggleable user authorization (disabled by default)
- **Large File Support**: Up to 2GB file uploads (vs 50MB limit for regular bots)
- **Error Handling**: Comprehensive error handling with user-friendly messages

### 🔧 Technical features
- **Async Processing**: Non-blocking downloads with threading
- **FFmpeg Integration**: Automatic FFmpeg detection for video processing
- **Session Isolation**: Uses dedicated incognito cookies to prevent behavioral conflicts
- **Clean Downloads**: Automatic cleanup of temporary files

## 📋 Requirements

### System dependencies
- **Python 3.7+**
- **FFmpeg**
- **Deno** (required for YouTube JavaScript challenge solving)

### Python dependencies
```
pyrogram          # User API client for large file uploads (up to 2GB)
tgcrypto          # Cryptography speedup for Pyrogram
yt-dlp            # YouTube video downloader
yt-dlp-ejs        # JavaScript challenge solver for yt-dlp
mutagen           # Audio metadata handling
requests          # HTTP requests for thumbnails
python-dotenv     # Environment variable management
```

## 📥 Getting the Repository

**Download ZIP or Git clone the repo:**
- **ZIP Download**: [https://github.com/LeeseTheFox/YouTubeBot](https://github.com/LeeseTheFox/YouTubeBot) → Code → Download ZIP
- **Git Clone**: `git clone https://github.com/LeeseTheFox/YouTubeBot.git`

## 🚀 Installation

### 1. Install dependencies
```bash
# Install the latest nightly version of yt-dlp (recommended)
pip install --upgrade --pre yt-dlp

# Install other dependencies
pip install -r requirements.txt
```

### 2. Install FFmpeg
**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH.

### 3. Install Deno (required for YouTube challenge solving)
**Linux/macOS:**
```bash
curl -fsSL https://deno.land/install.sh | sh
```

Then add Deno to your PATH by adding these lines to your `~/.bashrc` or `~/.zshrc`:
```bash
export DENO_INSTALL="$HOME/.deno"
export PATH="$DENO_INSTALL/bin:$PATH"
```

Reload your shell:
```bash
source ~/.bashrc  # or source ~/.zshrc
```

**Windows:**
```powershell
irm https://deno.land/install.ps1 | iex
```

Verify installation:
```bash
deno --version
```

### 4. Set up the Telegram bot

**Why both bot token and API credentials?**
This bot uses Pyrogram (Telegram User API) instead of the standard Bot API to bypass the 50MB file size limit. Regular bots can only send files up to 50MB, but User API allows up to 2GB uploads.

1. **Create a bot:**
   - Message [@BotFather](https://t.me/BotFather) on Telegram
   - Use `/newbot` command
   - Follow the prompts to get your bot token

2. **Get user API credentials (required for large files):**
   - Visit [my.telegram.org](https://my.telegram.org)
   - Log in with your Telegram account
   - Go to "API Development Tools"
   - Create a new application to get `api_id` and `api_hash`
   - **These credentials allow the bot to upload files up to 2GB**

### 5. Configure environment

Create a `.env` file in the project root (you can copy from `.env.example`):

```bash
cp .env.example .env
```

Then edit `.env` with your values:

```env
# Telegram Bot Configuration
API_ID=your_api_id_here
API_HASH=your_api_hash_here
BOT_TOKEN=your_bot_token_here

# User Access Control
WHITELIST_ENABLED=false
WHITELIST=123456789,987654321

# File Paths
COOKIES_PATH=cookies.txt
```

### 6. User Access Control (Optional)

**By default, the bot is open to all users.** To restrict access:

1. **Enable the whitelist** by setting `WHITELIST_ENABLED=true` in `.env`
2. **Find user IDs** by messaging [@userinfobot](https://t.me/userinfobot)
3. **Add authorized user IDs** to the `WHITELIST` in `.env` (comma-separated) - this is used only for initial seeding on first run
4. **After first run**, the whitelist is stored in `data/whitelist.json` and persists across restarts

**Important**: The `WHITELIST` environment variable is only used to seed the whitelist on the first run. After that, the bot reads from `data/whitelist.json`. To add or remove users after first run, edit `data/whitelist.json` directly or use admin commands (if implemented).

### 7. Cookie Setup (Critical for reliability)

**⚠️ IMPORTANT: Cookies must be exported from an incognito/private browsing tab to prevent session conflicts!**

YouTube analyzes session behavior patterns to detect automation. When you use cookies from your regular browsing session in the bot while simultaneously browsing YouTube in your browser, it creates conflicting behavioral signatures that trigger bot detection systems. Follow these steps:

1. **Open YouTube in incognito/private mode and log into your account**
2. **Install the [cookies.txt browser extension](https://github.com/hrdl-github/cookies-txt)**
3. **Navigate to any YouTube video in the incognito tab**
4. **Export cookies using the extension** - save as `cookies.txt` in the project directory

**Why incognito is required:**
- Prevents session behavior conflicts between browser and bot usage
- Isolates automated requests from human browsing patterns  
- Avoids triggering YouTube's session analysis algorithms that detect mixed usage patterns
- Using shared sessions will cause the bot to fail when you browse YouTube normally

## 🎮 Usage

### Starting the bot
```bash
python main.py
```

### Using the bot

1. **Start the bot:**
   ```
   /start
   ```

2. **Send a YouTube URL:**
   - Paste any supported YouTube URL
   - The bot will analyze and show available qualities

3. **Choose quality:**
   - Click on your preferred video quality
   - Or click "🎵 Download MP3" for audio only

4. **Download:**
   - The bot will download and send your file
   - Progress is shown in real-time

### Supported URL formats
```
https://www.youtube.com/watch?v=VIDEO_ID
https://youtu.be/VIDEO_ID
https://www.youtube.com/shorts/VIDEO_ID
https://music.youtube.com/watch?v=VIDEO_ID
https://www.youtube.com/embed/VIDEO_ID
```

## 🐳 Docker Deployment

**Important**: Mount the `data/` directory as a persistent volume to preserve runtime state (whitelist, session, cookies) across container restarts.

### Docker Run

```bash
docker build -t youtube-bot .

docker run -d \
  --name youtube-bot \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  -e API_ID=your_api_id \
  -e API_HASH=your_api_hash \
  -e BOT_TOKEN=your_bot_token \
  -e WHITELIST_ENABLED=false \
  -e COOKIES_PATH=data/cookies.txt \
  youtube-bot
```

### Docker Compose

```yaml
version: '3.8'

services:
  youtube-bot:
    build: .
    restart: unless-stopped
    volumes:
      - ./data:/app/data
    environment:
      - API_ID=${API_ID}
      - API_HASH=${API_HASH}
      - BOT_TOKEN=${BOT_TOKEN}
      - WHITELIST_ENABLED=${WHITELIST_ENABLED:-false}
      - COOKIES_PATH=data/cookies.txt
```

**Note**: The `WHITELIST` env var is only used on first run to seed `data/whitelist.json`. After that, edit the JSON file directly.

## 🔐 Access Control

### Public vs Private mode

**Public mode (default)**
- Anyone can use the bot
- No user restrictions
- Set `WHITELIST_ENABLED=false` in `.env`

**Private mode (whitelist)**
- Only authorized users can use the bot
- Set `WHITELIST_ENABLED=true` in `.env`
- Whitelist is stored in `data/whitelist.json` (persists across restarts)
- Unauthorized users are silently ignored

### Enabling Private mode

1. **Set whitelist enabled:**
   ```env
   WHITELIST_ENABLED=true
   ```

2. **Add authorized users (initial seed only):**
   ```env
   WHITELIST=123456789,987654321,555666777
   ```
   
   **Note**: This environment variable is only used to seed the whitelist on the **first run**. After that, the bot uses `data/whitelist.json`.

3. **Start the bot** - it will create `data/whitelist.json` with the users from the env var

### Managing the whitelist after first run

After the initial setup, the whitelist is stored in `data/whitelist.json`. To add or remove users:

**Option 1: Edit the JSON file directly**

The file has this structure:
```json
{
  "user_ids": [123456789, 987654321, 555666777],
  "version": 1
}
```

Simply add or remove user IDs from the `user_ids` array and restart the bot.

**Option 2: Delete and reseed (not recommended for production)**

If you want to completely reset the whitelist:
1. Stop the bot
2. Delete `data/whitelist.json`
3. Update the `WHITELIST` env var with new user IDs
4. Start the bot - it will recreate the file from the env var

**Important for Docker/Kubernetes deployments**: The `data/` directory must be mounted as a persistent volume. Otherwise, `whitelist.json` will be lost on container restart, and the bot will reseed from the env var each time.

### Verifying configuration

When the bot starts, it will display the current access mode:
- **Public mode**: `🌐 Public mode: Bot is open to all users`
- **Private mode**: `🔒 Whitelist enabled: X authorized users`

## 📁 Project structure

```
YouTubeBot/
├── main.py                    # Main bot application
├── runtime_state.py           # Runtime state management (whitelist persistence)
├── .env                       # Environment configuration (static config only)
├── requirements.txt           # Python dependencies
├── data/                      # Persistent data directory (mount as volume in Docker)
│   ├── whitelist.json        # User whitelist (runtime-mutable state)
│   ├── cookies.txt           # Incognito browser cookies (critical for reliability)
│   └── youtube_quality_bot.session # Telegram session file
├── downloads/                # Temporary download directory
└── README.md                 # This file
```

**Important**: The `data/` directory contains runtime-mutable state and should be mounted as a persistent volume in containerized deployments. This ensures that the whitelist, session, and cookies persist across container restarts.

## ⚙️ Configuration

### Environment variables

| Variable | Description | Example |
|----------|-------------|---------|
| `API_ID` | Telegram User API ID (enables 2GB uploads) | `12345678` |
| `API_HASH` | Telegram User API Hash (enables 2GB uploads) | `abcdef123456...` |
| `BOT_TOKEN` | Bot token from BotFather | `123456:ABC-DEF...` |
| `WHITELIST_ENABLED` | Enable user whitelist (true/false) | `false` |
| `WHITELIST` | Initial seed for authorized user IDs (first run only, then stored in `data/whitelist.json`) | `123456789,987654321` |
| `COOKIES_PATH` | Path to incognito cookies file | `data/cookies.txt` |

## 🛠️ Troubleshooting

### Common issues

1. **"FFmpeg not found"**
   - Install FFmpeg and ensure it's in your PATH
   - The bot will show a warning but continue working

2. **"Bot is not responding"**
   - Check your bot token in `.env`
   - Verify `API_ID` and `API_HASH` are correctly set (required for Pyrogram)
   - Ensure the bot is started with BotFather

3. **"User not authorized"**
   - Check if `WHITELIST_ENABLED=true` in `.env`
   - If whitelist is enabled, check `data/whitelist.json` to see if your user ID is in the list
   - To add your user ID:
     - **If first run**: Add it to the `WHITELIST` env var in `.env` before starting the bot
     - **After first run**: Edit `data/whitelist.json` directly and add your user ID to the `user_ids` array
   - Restart the bot after making changes to `data/whitelist.json`

4. **Videos fail to download / "Sign in to confirm you're not a bot"**
   - **Most common cause**: Missing Deno or yt-dlp-ejs package
   - **Solution**: 
     - Install Deno: `curl -fsSL https://deno.land/install.sh | sh`
     - Install yt-dlp-ejs: `pip install yt-dlp-ejs`
     - Ensure Deno is in your PATH
   - **Alternative cause**: Session behavior conflict from using shared cookies
   - **Solution**: Re-export cookies from an incognito tab using [cookies.txt](https://github.com/hrdl-github/cookies-txt)
   - Ensure `cookies.txt` file exists in the project directory

5. **Age-restricted videos fail**
   - Ensure you're logged into YouTube in the incognito tab before exporting cookies
   - Re-export cookies from an incognito session

6. **Bot works initially but stops after a few hours/days**
   - **Cause**: Session behavior analysis detected conflicting usage patterns or Deno/yt-dlp-ejs missing
   - **Solution**: 
     - Verify Deno is installed and in PATH: `deno --version`
     - Verify yt-dlp-ejs is installed: `pip list | grep yt-dlp-ejs`
     - Use dedicated incognito cookies and avoid browsing YouTube with the same session

## 🔒 Security Notes

- **Keep your `.env` file secure** - it contains sensitive API credentials
- **Consider enabling whitelist** - for public instances, restrict access to trusted users
- **Monitor usage** - the bot can download large files that consume bandwidth
- **Regular updates** - keep yt-dlp updated for best compatibility
- **Cookie security** - protect your `cookies.txt` file as it contains login session data

---

**⚠️ Disclaimer**: This bot is for personal use only. Users are responsible for complying with YouTube's Terms of Service and applicable copyright laws.
