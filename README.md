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
- **FFmpeg** (automatically detected)

### Python dependencies
```
pyrogram          # User API client for large file uploads (up to 2GB)
yt-dlp           # YouTube video downloader
mutagen          # Audio metadata handling
requests         # HTTP requests for thumbnails
python-dotenv    # Environment variable management
```

## 📥 Getting the Repository

**Download ZIP or Git clone the repo:**
- **ZIP Download**: [https://github.com/LeeseTheFox/YouTubeBot](https://github.com/LeeseTheFox/YouTubeBot) → Code → Download ZIP
- **Git Clone**: `git clone https://github.com/LeeseTheFox/YouTubeBot.git`

## 🚀 Installation

### 1. Install dependencies
```bash
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

### 3. Set up the Telegram bot

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

### 4. Configure environment

Create a `.env` file in the project root:

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

### 5. User Access Control (Optional)

**By default, the bot is open to all users.** To restrict access:

1. **Enable the whitelist** by setting `WHITELIST_ENABLED=true` in `.env`
2. **Find user IDs** by messaging [@userinfobot](https://t.me/userinfobot)
3. **Add authorized user IDs** to the `WHITELIST` in `.env` (comma-separated)

### 6. Cookie Setup (Critical for reliability)

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

## 🔐 Access Control

### Public vs Private mode

**Public mode (default)**
- Anyone can use the bot
- No user restrictions
- Set `WHITELIST_ENABLED=false` in `.env`

**Private mode (whitelist)**
- Only authorized users can use the bot
- Set `WHITELIST_ENABLED=true` in `.env`
- Add user IDs to `WHITELIST` (comma-separated)
- Unauthorized users are silently ignored

### Enabling Private mode

1. **Set whitelist enabled:**
   ```env
   WHITELIST_ENABLED=true
   ```

2. **Add authorized users:**
   ```env
   WHITELIST=123456789,987654321,555666777
   ```

3. **Restart the bot** for changes to take effect

### Verifying configuration

When the bot starts, it will display the current access mode:
- **Public mode**: `🌐 Public mode: Bot is open to all users`
- **Private mode**: `🔒 Whitelist enabled: X authorized users`

## 📁 Project structure

```
YouTubeBot/
├── main.py                    # Main bot application
├── .env                       # Environment configuration
├── requirements.txt           # Python dependencies
├── cookies.txt               # Incognito browser cookies (critical for reliability)
├── downloads/                # Temporary download directory
├── youtube_quality_bot.session # Telegram session file
└── README.md                 # This file
```

## ⚙️ Configuration

### Environment variables

| Variable | Description | Example |
|----------|-------------|---------|
| `API_ID` | Telegram User API ID (enables 2GB uploads) | `12345678` |
| `API_HASH` | Telegram User API Hash (enables 2GB uploads) | `abcdef123456...` |
| `BOT_TOKEN` | Bot token from BotFather | `123456:ABC-DEF...` |
| `WHITELIST_ENABLED` | Enable user whitelist (true/false) | `false` |
| `WHITELIST` | Authorized user IDs (when enabled) | `123456789,987654321` |
| `COOKIES_PATH` | Path to incognito cookies file | `cookies.txt` |

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
   - If whitelist is enabled, add your user ID to the `WHITELIST` in `.env`
   - Restart the bot after changes

4. **Videos fail to download / "Sign in to confirm you're not a bot"**
   - **Most common cause**: Session behavior conflict from using shared cookies
   - **Solution**: Re-export cookies from an incognito tab using [cookies.txt](https://github.com/hrdl-github/cookies-txt)
   - Ensure `cookies.txt` file exists in the project directory

5. **Age-restricted videos fail**
   - Ensure you're logged into YouTube in the incognito tab before exporting cookies
   - Re-export cookies from an incognito session

6. **Bot works initially but stops after a few hours/days**
   - **Cause**: Session behavior analysis detected conflicting usage patterns
   - **Solution**: Use dedicated incognito cookies and avoid browsing YouTube with the same session

## 🔒 Security Notes

- **Keep your `.env` file secure** - it contains sensitive API credentials
- **Consider enabling whitelist** - for public instances, restrict access to trusted users
- **Monitor usage** - the bot can download large files that consume bandwidth
- **Regular updates** - keep yt-dlp updated for best compatibility
- **Cookie security** - protect your `cookies.txt` file as it contains login session data

---

**⚠️ Disclaimer**: This bot is for personal use only. Users are responsible for complying with YouTube's Terms of Service and applicable copyright laws.
