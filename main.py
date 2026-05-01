import asyncio
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import requests
import yt_dlp
from dotenv import load_dotenv
from mutagen.id3 import APIC, ID3, TALB, TIT2, TPE1
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from runtime_state import RuntimeState

# Ensure Deno is in PATH for yt-dlp
deno_path = os.path.expanduser("~/.deno/bin")
if deno_path not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{deno_path}:{os.environ.get('PATH', '')}"
    logging.info(f"Added Deno to PATH: {deno_path}")


# Find ffmpeg path
def find_ffmpeg_path():
    try:
        # For Windows, check common installation paths
        if os.name == "nt":
            common_paths = [
                r"C:\ffmpeg\bin\ffmpeg.exe",
                r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
                r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
            ]
            for path in common_paths:
                if os.path.exists(path):
                    return path

            # Try to get path from where command is found
            try:
                result = subprocess.run(
                    ["where", "ffmpeg"], capture_output=True, text=True, check=True
                )
                if result.stdout.strip():
                    return result.stdout.strip().split("\n")[0]
            except (subprocess.SubprocessError, FileNotFoundError):
                pass
        else:
            # For Unix-like systems
            try:
                result = subprocess.run(
                    ["which", "ffmpeg"], capture_output=True, text=True, check=True
                )
                if result.stdout.strip():
                    return result.stdout.strip()
            except (subprocess.SubprocessError, FileNotFoundError):
                pass

        return None
    except Exception as e:
        logging.error(f"Error finding ffmpeg: {e}")
        return None


# Get ffmpeg path
FFMPEG_PATH = find_ffmpeg_path()
if FFMPEG_PATH:
    print(f"FFmpeg found at: {FFMPEG_PATH}")
else:
    print("WARNING: FFmpeg not found. Some video formats may not download correctly.")
    FFMPEG_PATH = "ffmpeg"  # Fallback to just the command name

# Load environment variables from .env file
load_dotenv()

# Whitelist configuration (static config only)
# WHITELIST_ENABLED controls whether whitelist checking is active
# The actual whitelist is managed by RuntimeState in data/whitelist.json
WHITELIST_ENABLED = os.getenv("WHITELIST_ENABLED", "false").lower() in (
    "true",
    "1",
    "yes",
    "on",
)

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Ensure the data directory exists (persisted across redeployments)
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Initialize runtime state manager
# This handles the whitelist with persistence to data/whitelist.json
# On first run, it seeds from the WHITELIST env var (if present)
# On subsequent runs, it loads from the JSON file (env var is ignored)
runtime_state = RuntimeState(DATA_DIR)

# Get cookies path from environment and make it absolute based on script location
# Default is data/cookies.txt so it is covered by the persistent data directory
cookies_path_config = os.getenv("COOKIES_PATH", "data/cookies.txt")
# Join script directory with cookies path from config to make an absolute path
COOKIES_PATH = os.path.join(SCRIPT_DIR, cookies_path_config)

# Validate cookies path
if not os.path.exists(COOKIES_PATH):
    print(f"Warning: Cookie file not found at {COOKIES_PATH}")
else:
    print(f"Cookie file found at {COOKIES_PATH}")


def is_user_allowed(user_id: int) -> bool:
    """Check if user is allowed to use the bot."""
    # If whitelist is disabled, allow all users
    if not WHITELIST_ENABLED:
        return True
    # If whitelist is enabled, check if user is in the runtime state whitelist
    return runtime_state.is_user_whitelisted(user_id)


# Initialize the bot with increased connection resilience
# workdir=DATA_DIR stores the session file (youtube_quality_bot.session) inside /data
app = Client(
    "youtube_quality_bot",
    api_id=os.getenv("API_ID"),
    api_hash=os.getenv("API_HASH"),
    bot_token=os.getenv("BOT_TOKEN"),
    workdir=DATA_DIR,
    sleep_threshold=60,  # Increase sleep threshold to prevent disconnects during long operations
    max_concurrent_transmissions=1,  # Limit concurrent transmissions to reduce connection stress
)


# Error handling wrapper
def handle_yt_dlp_errors(func):
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except yt_dlp.utils.DownloadError as e:
            print(f"yt-dlp download error: {str(e)}")
            return None, f"Failed to process video: {str(e)}"
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            return None, f"An unexpected error occurred: {str(e)}"

    return wrapper


# Constants
MAX_FILE_SIZE = 2 * 1000 * 1000 * 1000
DOWNLOAD_PATH = "downloads/"
PROGRESS_BAR_LENGTH = 20  # Number of characters in progress bar


def sanitize_filename(filename):
    """Sanitize the filename by removing invalid characters."""
    # Replace invalid characters for Windows filenames
    return re.sub(r'[<>:"/\\|?*]', "_", filename)


# Create downloads directory if it doesn't exist
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

# Create a thread pool executor for running yt-dlp downloads
thread_pool = ThreadPoolExecutor(max_workers=4)

# Enable logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


# Global exception handler to catch uncaught exceptions
def handle_exception(exc_type, exc_value, exc_traceback):
    """Log uncaught exceptions before the application crashes."""
    if issubclass(exc_type, KeyboardInterrupt):
        # Allow KeyboardInterrupt to work normally
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logging.critical(
        "Uncaught exception!", exc_info=(exc_type, exc_value, exc_traceback)
    )


# Install the global exception handler
sys.excepthook = handle_exception

print("🤖 Starting...")

# Print whitelist status
if WHITELIST_ENABLED:
    print(
        f"🔒 Whitelist enabled: {runtime_state.get_whitelist_size()} authorized users"
    )
else:
    print("🌐 Public mode: Bot is open to all users")


class Progress:
    def __init__(self, status_message, action="Downloading"):
        self.start_time = None
        self.status_message = status_message
        self.action = action
        self.last_update_time = 0
        self.last_percent = 0

    def make_progress_bar(self, current, total):
        progress = current / total
        filled_length = int(20 * progress)
        bar = "█" * filled_length + "░" * (20 - filled_length)
        percent = progress * 100
        speed = (
            current / (time.time() - self.start_time)
            if hasattr(self, "start_time")
            else 0
        )

        return (
            f"{self.action}...\n"
            f"{bar} {percent:.1f}%\n"
            f"Speed: {self.format_size(speed)}/s\n"
            f"{self.format_size(current)}/{self.format_size(total)}"
        )

    @staticmethod
    def format_size(size):
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    async def update(self, current, total):
        now = time.time()

        # Start time for speed calculation
        if not hasattr(self, "start_time"):
            self.start_time = now

        current_percent = int((current / total) * 100)

        # Update progress only if percentage changed by at least 5% or if download completed
        # This helps avoid flood wait limits
        if (current_percent - self.last_percent >= 5) or current == total:
            try:
                await self.status_message.edit_text(
                    self.make_progress_bar(current, total)
                )
                self.last_update_time = now
                self.last_percent = current_percent
            except Exception:
                pass


def should_include_quality(quality_info):
    """
    Determine if a quality should be included based on filtering rules.
    """
    height = quality_info.get("height")
    fps = quality_info.get("fps")
    quality_str = quality_info.get("quality", "").lower()
    vcodec = quality_info.get("vcodec", "").lower()

    # We must have height info for a video format
    if not height:
        logging.debug(f"Skipping format without height: {quality_info}")
        return False

    # Filter out image/storyboard codecs
    if vcodec in ["none", "images"] or "storyboard" in vcodec:
        logging.debug(f"Skipping storyboard/image format: {quality_info}")
        return False

    # Filter out HDR formats which may have color issues
    if "hdr" in quality_str or "hdr" in vcodec:
        logging.debug(f"Skipping HDR format: {quality_info}")
        return False

    # Filter out storyboards
    if "storyboard" in quality_str:
        logging.debug(f"Skipping storyboard: {quality_info}")
        return False

    # Filter out very low quality (below 144p)
    if height < 144:
        logging.debug(f"Skipping very low quality: {quality_info}")
        return False

    logging.debug(f"Including format: {quality_info}")
    return True


def create_quality_keyboard(qualities, video_url):
    """Create an inline keyboard with quality options."""
    buttons = []
    current_row = []

    # Extract video ID instead of using the full URL
    video_id = extract_video_id(video_url)
    logging.debug(f"Using video ID for callback data: {video_id}")

    if not video_id:
        logging.error(f"Could not extract video ID from {video_url}")
        # Use a shortened version of the URL if we can't extract the ID
        video_id = "unknown"

    for quality in qualities:
        # Create button text
        button_text = f"{quality['quality']} ({quality['ext']})"

        # Create callback data with format ID and video ID (not full URL)
        callback_data = f"dl_{quality['format_id']}_{video_id}"

        # Ensure callback data doesn't exceed Telegram's limit (64 bytes)
        if len(callback_data.encode()) > 64:
            callback_data = (
                f"dl_{quality['format_id']}"  # Just use format ID as last resort
            )
            logging.warning(
                f"Callback data too large, using shortened version: {callback_data}"
            )

        button = InlineKeyboardButton(text=button_text, callback_data=callback_data)

        current_row.append(button)

        # Create new row after every 2 buttons
        if len(current_row) == 2:
            buttons.append(current_row)
            current_row = []

    # Add any remaining buttons
    if current_row:
        buttons.append(current_row)

    # Add MP3 download button as the last row
    mp3_callback_data = f"mp3_{video_id}"
    if len(mp3_callback_data.encode()) > 64:
        mp3_callback_data = "mp3_audio"  # Fallback

    mp3_button = InlineKeyboardButton(
        text="🎵 Download MP3", callback_data=mp3_callback_data
    )
    buttons.append([mp3_button])

    return InlineKeyboardMarkup(buttons)


async def download_and_send_audio(client, callback_query, video_url):
    """Download audio (MP3) and send it to the user."""
    status_message = None
    temp_filepath = None
    loop = asyncio.get_running_loop()

    try:
        # Send initial status message
        status_message = await callback_query.message.reply_text(
            "⬇️ Preparing download..."
        )

        # Progress handler for download status updates
        async def update_status(current, total):
            progress = current / total
            filled_length = int(PROGRESS_BAR_LENGTH * progress)
            bar = "█" * filled_length + "░" * (PROGRESS_BAR_LENGTH - filled_length)
            percent = progress * 100

            try:
                await status_message.edit_text(
                    f"⬇️ Downloading...\n{bar} {percent:.1f}%"
                )
            except Exception:
                pass

        # Add download progress callback
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [DownloadProgress(loop, update_status)],
            "cookiefile": COOKIES_PATH,
            "outtmpl": temp_filepath,
            "filesize_limit": MAX_FILE_SIZE,
            "ffmpeg_location": FFMPEG_PATH,
            "prefer_ffmpeg": True,
            "remote_components": "ejs:github",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }

        # Extract audio information
        await status_message.edit_text("🔄 Retrieving audio information...")
        info = await extract_info_async(loop, ydl_opts, video_url)

        # Check file size
        filesize = info.get("filesize", 0)
        if filesize and filesize > MAX_FILE_SIZE:
            await status_message.edit_text(
                "❌ Error: Audio file size exceeds 3.9GB limit!"
            )
            return

        # Get video metadata
        title = info.get("title", "audio")
        channel_name = info.get("channel", info.get("uploader", "Unknown Artist"))

        # Use sanitized video title for filename
        sanitized_title = sanitize_filename(title)
        random_code = uuid.uuid4().hex[:3]  # Generate a short random code
        temp_filename = (
            f"{sanitized_title}_{random_code}.%(ext)s"  # Use dynamic extension
        )
        temp_filepath = os.path.join(DOWNLOAD_PATH, temp_filename)

        # Update yt-dlp output template
        ydl_opts["outtmpl"] = temp_filepath

        # Start the download
        await status_message.edit_text("⬇️ Starting download...")
        await download_video_async(loop, ydl_opts, video_url)

        # Get the actual downloaded file path with mp3 extension
        temp_filepath = os.path.join(
            DOWNLOAD_PATH, f"{sanitized_title}_{random_code}.mp3"
        )

        # Download thumbnail once and reuse it
        thumbnail_path = None
        try:
            thumbnail_path = download_thumbnail(video_url)
        except Exception as e:
            logging.error(f"Error downloading thumbnail: {str(e)}")
            # Continue without thumbnail if there's an error

        # Add metadata to the MP3 file
        await status_message.edit_text("🎵 Adding metadata...")

        try:
            # First check if file exists
            if not os.path.exists(temp_filepath):
                logging.error(
                    f"Cannot add metadata: file {temp_filepath} does not exist"
                )
            else:
                # Add ID3 tags - first try to load existing tags or create a new one
                try:
                    audio = ID3(temp_filepath)
                except:
                    # If no ID3 tag exists, create a new one and save it to the file
                    audio = ID3()
                    audio.save(temp_filepath)

                # Update the tags
                audio["TIT2"] = TIT2(encoding=3, text=title)  # Song title
                audio["TPE1"] = TPE1(encoding=3, text=channel_name)  # Artist
                audio["TALB"] = TALB(encoding=3, text=f"From YouTube")  # Album

                # Try to add album art if available
                if thumbnail_path and os.path.exists(thumbnail_path):
                    with open(thumbnail_path, "rb") as albumart:
                        audio["APIC"] = APIC(
                            encoding=3,
                            mime="image/jpeg",
                            type=3,  # Cover image
                            desc="Cover",
                            data=albumart.read(),
                        )

                # Save the ID3 tags to the file
                audio.save(temp_filepath)

                logging.info(f"Added metadata: Title={title}, Artist={channel_name}")

        except Exception as e:
            logging.error(f"Error adding metadata: {str(e)}")
            # Continue even if metadata addition fails

        # Update status for upload
        await status_message.edit_text("⬆️ Uploading audio to Telegram...")

        # Send the MP3 file to the user with appropriate metadata
        await client.send_audio(
            chat_id=callback_query.message.chat.id,
            audio=temp_filepath,
            title=title,
            performer=channel_name,
            thumb=thumbnail_path,  # Use the already downloaded thumbnail
            caption=f"🎶 {title} - {channel_name}",
        )

        # Clean up the downloaded file and thumbnail
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)

        # Clean up thumbnail file
        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                os.remove(thumbnail_path)
                logging.debug(f"Removed thumbnail: {thumbnail_path}")
            except Exception as e:
                logging.error(f"Error removing thumbnail: {str(e)}")

        # Delete the status message
        await status_message.delete()

    except ConnectionResetError as e:
        logging.error(
            f"Connection reset during audio download: {str(e)}", exc_info=True
        )
        error_message = "❌ Connection lost during download. The audio is still being downloaded in the background."
        try:
            if status_message:
                await status_message.edit_text(error_message)
        except Exception:
            logging.error("Could not send error message due to connection loss")
        # Don't clean up files - download might still be in progress

    except ConnectionError as e:
        logging.error(
            f"Connection error during audio download: {str(e)}", exc_info=True
        )
        error_message = "❌ Network connection error. Please try again."
        try:
            if status_message:
                await status_message.edit_text(error_message)
        except Exception:
            logging.error("Could not send error message due to connection loss")
        # Clean up in case of error
        if temp_filepath and os.path.exists(temp_filepath):
            os.remove(temp_filepath)

    except Exception as e:
        logging.error(f"Error in download_and_send_audio: {str(e)}", exc_info=True)
        error_message = f"❌ Error: {str(e)}"
        try:
            if status_message:
                await status_message.edit_text(error_message)
        except Exception as send_error:
            logging.error(f"Could not send error message: {str(send_error)}")

        # Clean up in case of error
        if temp_filepath and os.path.exists(temp_filepath):
            os.remove(temp_filepath)


def clear_downloads_folder():
    """Clear the downloads folder at startup."""
    downloads_folder = "downloads"
    if os.path.exists(downloads_folder):
        shutil.rmtree(downloads_folder)
    os.makedirs(downloads_folder, exist_ok=True)


def get_video_qualities(url):
    """Extract available video qualities from YouTube URL."""
    logging.info(f"Starting quality extraction for URL: {url}")

    # Try up to 3 times in case of network errors
    max_retries = 3
    retry_delay = 2  # seconds

    for attempt in range(max_retries):
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
                "cookiefile": COOKIES_PATH if os.path.exists(COOKIES_PATH) else None,
                "nocheckcertificate": True,
                "socket_timeout": 30,
                "remote_components": "ejs:github",
                "skip_download": True,
                "ignoreerrors": False,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "extractor_retries": 3,
                "fragment_retries": 3,
                "file_access_retries": 3,
            }

            logging.debug(f"YDL options: {ydl_opts}")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logging.info(
                    f"Starting info extraction (attempt {attempt + 1}/{max_retries})"
                )
                try:
                    info = ydl.extract_info(url, download=False)

                    # If info is None or empty, retry
                    if not info:
                        logging.error("No info returned from yt-dlp")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                        return None, "Could not extract video information"

                    logging.debug(
                        f"Successfully extracted info for: {info.get('title', 'Unknown')}"
                    )
                except yt_dlp.utils.DownloadError as e:
                    error_msg = str(e)
                    if (
                        "getaddrinfo failed" in error_msg
                        or "Unable to download webpage" in error_msg
                    ):
                        if attempt < max_retries - 1:
                            logging.warning(
                                f"Network error on attempt {attempt + 1}, retrying in {retry_delay} seconds: {error_msg}"
                            )
                            time.sleep(retry_delay)
                            continue
                    logging.error(
                        f"Error during info extraction: {error_msg}", exc_info=True
                    )
                    return None, f"Info extraction failed: {error_msg}"
                except Exception as e:
                    logging.error(
                        f"Error during info extraction: {str(e)}", exc_info=True
                    )
                    return None, f"Info extraction failed: {str(e)}"

                if not info:
                    logging.error("No info returned from yt-dlp")
                    return None, "Could not extract video information"

                formats = info.get("formats", [])
                logging.info(f"Found {len(formats)} formats")

                if not formats:
                    logging.error("No formats found in video info")
                    return None, "No available formats found"

                # Find the best audio stream to estimate combined file sizes
                audio_formats = [
                    f
                    for f in formats
                    if f.get("acodec") != "none" and f.get("vcodec") == "none"
                ]
                best_audio = None
                if audio_formats:
                    best_audio = max(
                        audio_formats, key=lambda f: f.get("abr") or 0, default=None
                    )

                best_audio_size = 0
                if best_audio:
                    best_audio_size = (
                        best_audio.get("filesize")
                        or best_audio.get("filesize_approx")
                        or 0
                    )

                qualities = []
                seen_qualities = {}  # Changed to dict to track best format per quality

                for f in formats:
                    logging.debug(f"Processing format: {f}")
                    # Only include video formats with video codec
                    if f.get("vcodec") != "none" and f.get("vcodec") != "images":
                        quality = f.get("format_note", f.get("height", "N/A"))

                        # Use height to create a cleaner quality label
                        height = f.get("height")
                        if height:
                            quality = f"{height}p"
                            # Add FPS if it's high
                            fps = f.get("fps", 0)
                            if fps and fps > 30:
                                quality += f"{int(fps)}"

                        # Check if format has audio
                        has_audio = f.get("acodec") != "none"

                        # Estimate total filesize
                        video_filesize = f.get("filesize") or f.get("filesize_approx")

                        total_filesize = video_filesize
                        if not has_audio and video_filesize is not None:
                            total_filesize += best_audio_size

                        quality_info = {
                            "quality": quality,
                            "ext": f.get("ext", "N/A"),
                            "filesize": total_filesize,
                            "format_id": f.get("format_id", "N/A"),
                            "has_audio": has_audio,
                            "height": f.get("height"),
                            "fps": f.get("fps"),
                            "vcodec": f.get("vcodec", "unknown"),
                            "tbr": f.get(
                                "tbr", 0
                            ),  # Total bitrate for quality comparison
                            "protocol": f.get(
                                "protocol", "unknown"
                            ),  # Track protocol for HLS vs HTTPS preference
                        }

                        logging.debug(f"Quality info: {quality_info}")

                        if should_include_quality(quality_info):
                            # Keep the best format for each quality
                            # Prefer HTTPS (direct download) over HLS (m3u8) to avoid empty file errors
                            if quality not in seen_qualities:
                                seen_qualities[quality] = quality_info
                            else:
                                existing = seen_qualities[quality]
                                existing_is_https = existing.get("protocol") in (
                                    "https",
                                    "http",
                                )
                                new_is_https = quality_info.get("protocol") in (
                                    "https",
                                    "http",
                                )

                                # Check codecs
                                existing_is_h264 = existing.get(
                                    "vcodec", ""
                                ).startswith("avc1")
                                new_is_h264 = quality_info.get("vcodec", "").startswith(
                                    "avc1"
                                )

                                # Decision logic for "Best" format for this quality:
                                # 1. Codec: H.264 (avc1) > Others (Critical for macOS/iOS compatibility)
                                # 2. Protocol: HTTPS > HLS (Better reliability, though HLS is now improved)
                                # 3. Bitrate: Higher > Lower

                                use_new = False

                                if new_is_h264 and not existing_is_h264:
                                    use_new = True
                                elif new_is_h264 == existing_is_h264:
                                    # Codecs priority is same, check protocol
                                    if new_is_https and not existing_is_https:
                                        use_new = True
                                    elif new_is_https == existing_is_https:
                                        # Protocols are same, check bitrate
                                        if quality_info["tbr"] > existing["tbr"]:
                                            use_new = True

                                if use_new:
                                    seen_qualities[quality] = quality_info

                # Convert dict values to list and sort by height
                qualities = sorted(
                    seen_qualities.values(),
                    key=lambda x: x.get("height", 0),
                    reverse=True,
                )

                if not qualities:
                    logging.error("No suitable qualities found after filtering")
                    logging.info(f"Total formats found: {len(formats)}")
                    logging.info(
                        f"Video formats (vcodec != 'none'): {len([f for f in formats if f.get('vcodec') != 'none'])}"
                    )
                    # Return a more helpful error message
                    return (
                        None,
                        "No suitable video qualities found. The video might be unavailable, age-restricted, or in an unsupported format.",
                    )

                logging.info(
                    f"Successfully extracted {len(qualities)} qualities: {[q['quality'] for q in qualities]}"
                )
                return qualities, info.get("title", "Unknown Title")

            # If we get here without returning, we need to retry
            logging.warning(
                f"Extraction attempt {attempt + 1} failed without specific error, retrying..."
            )

        except Exception as e:
            if attempt < max_retries - 1 and (
                "getaddrinfo failed" in str(e) or "Unable to download webpage" in str(e)
            ):
                logging.warning(
                    f"Network error on attempt {attempt + 1}, retrying in {retry_delay} seconds: {str(e)}"
                )
                time.sleep(retry_delay)
            else:
                logging.error(
                    f"Unexpected error in get_video_qualities: {str(e)}", exc_info=True
                )
                return None, str(e)

    # If we've exhausted all retries
    return (
        None,
        "Failed to extract video info after multiple attempts. Please check your internet connection and try again.",
    )


def extract_video_id(url: str) -> str:
    """Extract video ID from both youtube.com and youtu.be URLs."""
    # Normalize the URL to handle URLs without "www."
    url = url.strip()
    logging.debug(f"Extracting video ID from URL: {url}")

    if "youtu.be" in url:
        # Handle youtu.be/VIDEO_ID format
        video_id = url.split("youtu.be/")[-1].split("?")[0].split("&")[0]
        logging.debug(f"Extracted video ID from youtu.be URL: {video_id}")
    else:
        # Handle YouTube Shorts format
        if "/shorts/" in url:
            video_id = url.split("/shorts/")[-1].split("?")[0].split("&")[0]
            logging.debug(f"Extracted video ID from YouTube Shorts URL: {video_id}")
        # Handle music.youtube.com format
        elif "music.youtube.com" in url:
            if "v=" in url:
                video_id = url.split("v=")[-1].split("&")[0]
                logging.debug(
                    f"Extracted video ID from music.youtube.com URL with v= parameter: {video_id}"
                )
            elif "watch/" in url:
                video_id = url.split("watch/")[-1].split("?")[0].split("&")[0]
                logging.debug(
                    f"Extracted video ID from music.youtube.com/watch/ format: {video_id}"
                )
            else:
                # Try to find videoId in other formats
                match = re.search(r'videoId[=:]["\']?([^"\'&]+)', url)
                if match:
                    video_id = match.group(1)
                    logging.debug(
                        f"Extracted video ID using regex from music.youtube.com: {video_id}"
                    )
                else:
                    video_id = ""
                    logging.warning(
                        f"Could not extract video ID from music.youtube.com URL: {url}"
                    )
        # Handle regular youtube.com format
        elif "v=" in url:
            video_id = url.split("v=")[-1].split("&")[0]
            logging.debug(
                f"Extracted video ID from youtube.com URL with v= parameter: {video_id}"
            )
        else:
            # Handle other potential youtube.com formats
            # First, normalize the URL to ensure consistent handling
            if "youtube.com" in url:
                path_part = url.split("youtube.com/")[-1]
                logging.debug(f"Path part after youtube.com/: {path_part}")
                path = path_part.split("?")[0].split("&")[0]
                if path.startswith("watch/"):
                    video_id = path.split("watch/")[-1]
                    logging.debug(
                        f"Extracted video ID from youtube.com/watch/ format: {video_id}"
                    )
                elif path.startswith("embed/"):
                    video_id = path.split("embed/")[-1]
                    logging.debug(
                        f"Extracted video ID from youtube.com/embed/ format: {video_id}"
                    )
                else:
                    video_id = path
                    logging.debug(f"Using path as video ID: {video_id}")
            else:
                # Fallback for unexpected URL formats
                video_id = ""
                logging.warning(f"Could not extract video ID from URL: {url}")

    return video_id.strip()


def download_thumbnail(video_url: str) -> str:
    """Download the thumbnail of a YouTube video with fallbacks."""
    # Extract video ID using the helper function
    try:
        video_id = extract_video_id(video_url)
        logging.info(f"Extracted video ID: {video_id}")

        # If video_id is empty, return None
        if not video_id:
            logging.error(f"Failed to extract video ID from URL: {video_url}")
            return None

        # Try different thumbnail qualities in order
        thumbnail_qualities = [
            "maxresdefault.jpg",  # 1920x1080
            "sddefault.jpg",  # 640x480
            "hqdefault.jpg",  # 480x360
            "mqdefault.jpg",  # 320x180
            "default.jpg",  # 120x90
        ]

        for quality in thumbnail_qualities:
            thumbnail_url = f"https://img.youtube.com/vi/{video_id}/{quality}"
            try:
                response = requests.get(thumbnail_url, stream=True, timeout=10)
                if (
                    response.status_code == 200
                    and int(response.headers.get("content-length", 0)) > 1000
                ):
                    thumbnail_path = f"thumbnail_{video_id}.jpg"
                    with open(thumbnail_path, "wb") as file:
                        for chunk in response.iter_content(1024):
                            file.write(chunk)
                    logging.info(f"Successfully downloaded thumbnail: {quality}")
                    return thumbnail_path
            except Exception as e:
                logging.debug(f"Failed to download {quality} thumbnail: {str(e)}")
                continue

        logging.warning("All thumbnail download attempts failed")
        return None

    except Exception as e:
        logging.error(f"Error in download_thumbnail: {str(e)}")
        return None


class DownloadProgress:
    def __init__(self, loop, progress_callback):
        self.loop = loop
        self.progress_callback = progress_callback
        self.last_update_time = 0

    def __call__(self, d):
        if d["status"] == "downloading":
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded_bytes = d.get("downloaded_bytes", 0)

            if total_bytes:
                now = time.time()

                # Update every 1 second
                if now - self.last_update_time >= 1:
                    future = asyncio.run_coroutine_threadsafe(
                        self.progress_callback(downloaded_bytes, total_bytes), self.loop
                    )
                    # Wait for the future to complete to ensure the message is sent
                    try:
                        future.result(timeout=5)
                    except Exception:
                        pass
                    self.last_update_time = now


async def download_video_async(loop, ydl_opts, url):
    """Run yt-dlp download in a separate thread"""

    def download():
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.download([url])
        except Exception as e:
            logging.error(
                f"Error in download thread for {url}: {str(e)}", exc_info=True
            )
            raise  # Re-raise to propagate to caller

    try:
        return await loop.run_in_executor(thread_pool, download)
    except Exception as e:
        logging.error(
            f"Exception caught from executor during download: {str(e)}", exc_info=True
        )
        raise


async def extract_info_async(loop, ydl_opts, url):
    """Extract video info in a separate thread"""

    def extract():
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as e:
            logging.error(
                f"Error in extraction thread for {url}: {str(e)}", exc_info=True
            )
            raise  # Re-raise to propagate to caller

    try:
        return await loop.run_in_executor(thread_pool, extract)
    except Exception as e:
        logging.error(
            f"Exception caught from executor during extraction: {str(e)}", exc_info=True
        )
        raise


async def download_and_send_video(client, callback_query, format_id, video_url):
    """Download video and send it to user."""
    status_message = None
    temp_filepath = None
    final_filepath = None
    loop = asyncio.get_running_loop()

    try:
        # Send initial status message
        status_message = await callback_query.message.reply_text(
            "⬇️ Preparing download..."
        )

        # Progress handler for download status updates
        async def update_status(current, total):
            progress = current / total if total else 0
            filled_length = int(20 * progress)
            bar = "█" * filled_length + "░" * (20 - filled_length)
            percent = progress * 100

            try:
                await status_message.edit_text(
                    f"⬇️ Downloading...\n{bar} {percent:.1f}%"
                )
            except Exception:
                pass

        # Step 1: Extract video metadata for pre-check and accurate file size
        # Use format selection that strictly prefers H.264 (avc1) for compatibility
        # Then prefers HTTPS over HLS, and AAC audio
        format_selector = f"({format_id}[vcodec^=avc1]+bestaudio[acodec^=mp4a]/({format_id})[vcodec^=avc1]+bestaudio/({format_id})+bestaudio[acodec^=mp4a]/({format_id})+bestaudio/best)"

        ydl_opts_info = {
            "format": format_selector,
            "quiet": True,
            "no_warnings": True,
            "cookiefile": COOKIES_PATH,
            "remote_components": "ejs:github",
        }

        info = await extract_info_async(loop, ydl_opts_info, video_url)

        # Step 2: Check file size before downloading
        filesize = info.get("filesize") or info.get("filesize_approx", 0)

        if filesize and filesize > MAX_FILE_SIZE:
            await status_message.edit_text(
                f"❌ Error: Video file size exceeds the limit! (Size: {format_size(filesize)})"
            )
            return

        # Step 3: Prepare filenames and paths
        title = info.get("title", "video")
        sanitized_title = sanitize_filename(title)
        unique_id = uuid.uuid4().hex
        temp_filename = f"{unique_id}.mp4"
        final_filename = f"{sanitized_title}_{unique_id}.mp4"
        temp_filepath = os.path.join(DOWNLOAD_PATH, temp_filename)
        final_filepath = os.path.join(DOWNLOAD_PATH, final_filename)

        # Step 4: Configure yt-dlp for downloading
        # Enhanced settings to handle HLS streams more reliably and ensure compatibility
        ydl_opts = {
            "format": format_selector,  # Prefer direct HTTPS over HLS
            "outtmpl": temp_filepath,
            "overwrites": True,  # Overwrite leftover files from failed attempts
            "quiet": True,
            "no_warnings": True,
            "no_progress": True,
            "progress_hooks": [DownloadProgress(loop, update_status)],
            "cookiefile": COOKIES_PATH,
            "ffmpeg_location": FFMPEG_PATH,
            "prefer_ffmpeg": True,
            "merge_output_format": "mp4",  # Force output as MP4
            # Compatibility improvements
            "writethumbnail": True,  # Download thumbnail for embedding
            "postprocessors": [
                {"key": "FFmpegMetadata", "add_chapters": True, "add_metadata": True},
                {
                    "key": "FFmpegThumbnailsConvertor",
                    "format": "jpg",
                },  # Convert thumbnail to JPG for Apple compatibility
                {"key": "EmbedThumbnail"},  # Embed thumbnail as cover art
            ],
            "remote_components": "ejs:github",
            # HLS/fragment download reliability improvements
            "hls_prefer_native": False,  # Use ffmpeg for HLS (more reliable)
            "fragment_retries": 10,  # Retry failed fragments more times
            "retries": 10,  # Overall download retries
            "file_access_retries": 5,  # Retry file access issues
            "extractor_retries": 5,  # Retry extractor issues
            "socket_timeout": 30,  # Timeout for network operations
            "http_chunk_size": 10485760,  # 10MB chunks for better reliability
        }

        def cleanup_temp_files(base_path):
            """Remove all intermediate files ffmpeg might leave behind for a given base path.

            ffmpeg exits with code 183 ('file already exists') if any output file from a
            previous attempt is still on disk. We delete all files sharing the same stem.
            """
            import glob as _glob

            # Derive the stem without the .mp4 extension (e.g. downloads/abc123)
            stem = os.path.splitext(base_path)[0]
            # Match everything that starts with this stem (covers .webm, .mkv, .m4a, .jpg, .part, etc.)
            for leftover in _glob.glob(f"{_glob.escape(stem)}*"):
                try:
                    os.remove(leftover)
                    logging.debug(f"Cleaned up temp file: {leftover}")
                except OSError as e:
                    logging.warning(f"Could not remove temp file {leftover}: {e}")

        # Step 5: Start the download (with retry on failure)
        # Clean up any orphaned temp files from prior crashed downloads before starting
        cleanup_temp_files(temp_filepath)

        max_download_attempts = 2
        for download_attempt in range(max_download_attempts):
            try:
                await status_message.edit_text(
                    f"⬇️ {'Retrying' if download_attempt > 0 else 'Starting'} download..."
                )
                await download_video_async(loop, ydl_opts, video_url)
                break  # Download succeeded
            except yt_dlp.utils.DownloadError as dl_err:
                logging.warning(
                    f"Download attempt {download_attempt + 1}/{max_download_attempts} "
                    f"failed: {str(dl_err)}"
                )
                # Clean up ALL intermediate files ffmpeg may have created before retry
                # (ffmpeg exits with code 183 "file already exists" if these are left behind)
                cleanup_temp_files(temp_filepath)
                if download_attempt >= max_download_attempts - 1:
                    raise  # Re-raise on final attempt
                # Try without thumbnail embedding on retry (it can cause ffmpeg failures)
                ydl_opts_retry = ydl_opts.copy()
                ydl_opts_retry["writethumbnail"] = False
                ydl_opts_retry["postprocessors"] = [
                    {
                        "key": "FFmpegMetadata",
                        "add_chapters": True,
                        "add_metadata": True,
                    },
                ]
                ydl_opts = ydl_opts_retry

        # Rename the downloaded file to the final filename
        if os.path.exists(temp_filepath):
            os.rename(temp_filepath, final_filepath)

        # Step 6: Prepare for upload
        await status_message.edit_text("⬆️ Uploading to Telegram...")

        last_upload_update = time.time()

        async def upload_progress(current, total):
            nonlocal last_upload_update
            now = time.time()

            if now - last_upload_update >= 1:
                progress = current / total if total else 0
                filled_length = int(20 * progress)
                bar = "█" * filled_length + "░" * (20 - filled_length)
                percent = progress * 100

                size_current = format_size(current)
                size_total = format_size(total)

                try:
                    await status_message.edit_text(
                        f"⬆️ Uploading to Telegram...\n"
                        f"{bar} {percent:.1f}%\n"
                        f"{size_current}/{size_total}"
                    )
                    last_upload_update = now
                except Exception:
                    pass

        # Step 7: Upload video to Telegram

        # Locate the thumbnail file (yt-dlp saves it with the same basename as temp file but .jpg extension)
        thumb_path = None
        if temp_filepath:
            base_name = os.path.splitext(temp_filepath)[0]
            possible_thumb = f"{base_name}.jpg"
            if os.path.exists(possible_thumb):
                thumb_path = possible_thumb

        await client.send_video(
            chat_id=callback_query.message.chat.id,
            video=final_filepath,
            caption=f"📹 {title}",
            duration=info.get("duration"),
            width=info.get("width"),
            height=info.get("height"),
            thumb=thumb_path,
            supports_streaming=True,
            progress=upload_progress,
        )

        # Step 8: Clean up
        if os.path.exists(final_filepath):
            os.remove(final_filepath)

        if thumb_path and os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except Exception:
                pass

        await status_message.delete()

    except ConnectionResetError as e:
        logging.error(f"Connection reset during download: {str(e)}", exc_info=True)
        error_message = "❌ Connection lost during download. The video is still being downloaded in the background."
        try:
            if status_message:
                await status_message.edit_text(error_message)
        except Exception:
            # If we can't edit the message, the connection is really gone
            logging.error("Could not send error message due to connection loss")

        # Don't clean up files - download might still be in progress

    except ConnectionError as e:
        logging.error(f"Connection error during download: {str(e)}", exc_info=True)
        error_message = "❌ Network connection error. Please try again."
        try:
            if status_message:
                await status_message.edit_text(error_message)
        except Exception:
            logging.error("Could not send error message due to connection loss")

        # Clean up in case of error
        if temp_filepath and os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        if final_filepath and os.path.exists(final_filepath):
            os.remove(final_filepath)

    except Exception as e:
        logging.error(f"Error in download_and_send_video: {str(e)}", exc_info=True)
        error_message = f"❌ Error: {str(e)}"
        try:
            if status_message:
                await status_message.edit_text(error_message)
            else:
                await callback_query.message.reply_text(error_message)
        except Exception as send_error:
            logging.error(f"Could not send error message: {str(send_error)}")

        # Clean up in case of error
        if temp_filepath and os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        if final_filepath and os.path.exists(final_filepath):
            os.remove(final_filepath)


def format_size(size):
    """Format size in bytes to human-readable format"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


@app.on_message(filters.command("start"))
async def start_command(client, message):
    """Handle /start command."""
    if not is_user_allowed(message.from_user.id):
        return  # Silently ignore non-whitelisted users

    welcome_text = (
        "👋 Welcome to YouTube downloader!\n\n"
        "Send me a YouTube link, and I'll download the video for you."
    )
    await message.reply_text(welcome_text)


def normalize_youtube_url(url: str) -> str:
    """Normalize YouTube URL to ensure consistent processing."""
    url = url.strip()

    # If URL already has a protocol, don't modify it
    if url.startswith("http://") or url.startswith("https://"):
        pass
    else:
        # Add https:// if missing
        url = "https://" + url

    # Add www. if it's youtube.com without www.
    if (
        "youtube.com" in url
        and "www.youtube.com" not in url
        and "music.youtube.com" not in url
    ):
        url = url.replace("youtube.com", "www.youtube.com")

    # Convert YouTube Shorts URL to regular watch URL
    if "/shorts/" in url:
        video_id = url.split("/shorts/")[1].split("?")[0]
        url = f"https://www.youtube.com/watch?v={video_id}"

    logging.info(f"Normalized URL: {url}")
    return url


@app.on_message(
    filters.regex(
        r"(https?://)?(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/.*"
    )
)
async def handle_youtube_link(client, message):
    """Handle YouTube link messages."""
    logging.info(f"Received YouTube link: {message.text}")

    if not is_user_allowed(message.from_user.id):
        logging.warning(f"Unauthorized access attempt from user {message.from_user.id}")
        return

    try:
        # Normalize the YouTube URL
        normalized_url = normalize_youtube_url(message.text)
        logging.info(f"Normalized URL: {normalized_url}")

        # Send "processing" message
        logging.debug("Sending processing message")
        processing_msg = await message.reply_text("🔄 Processing video information...")

        # Extract video qualities with timeout
        logging.info(f"Attempting extraction with 30s timeout")

        try:
            # Run extraction in thread pool with timeout
            loop = asyncio.get_running_loop()

            async def extract_with_timeout():
                return await loop.run_in_executor(
                    thread_pool, get_video_qualities, normalized_url
                )

            qualities, title = await asyncio.wait_for(
                extract_with_timeout(), timeout=30.0
            )

        except asyncio.TimeoutError:
            error_msg = "❌ Error: Request timed out. The video might be unavailable or the server is slow. Please try again."
            logging.error(f"Extraction timed out after 30s")
            await processing_msg.edit_text(error_msg)
            return
        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            logging.error(f"Extraction failed: {str(e)}", exc_info=True)
            await processing_msg.edit_text(error_msg)
            return

        if qualities is None:
            error_msg = (
                f"❌ Error: {title if title else 'Failed to extract video information'}"
            )
            logging.error(f"Extraction returned None: {error_msg}")
            await processing_msg.edit_text(error_msg)
            return

        logging.info(f"Successfully extracted video info: {title}")

        # Download the thumbnail
        logging.debug("Attempting to download thumbnail")
        thumbnail_path = download_thumbnail(normalized_url)
        if thumbnail_path:
            logging.debug(f"Thumbnail downloaded to: {thumbnail_path}")
        else:
            logging.warning("Failed to download thumbnail")

        # Create response message
        response = f"📹 **{title}**\n\nSelect video quality:"

        # Create and attach inline keyboard
        logging.debug("Creating quality selection keyboard")
        keyboard = create_quality_keyboard(qualities, normalized_url)

        if thumbnail_path and os.path.exists(thumbnail_path):
            # Send the thumbnail with the response message and buttons
            try:
                logging.debug("Sending response with thumbnail")
                await client.send_photo(
                    chat_id=message.chat.id,
                    photo=thumbnail_path,
                    caption=response,
                    reply_markup=keyboard,
                )
                logging.info("Successfully sent response with thumbnail")
            except Exception as e:
                logging.error(f"Error sending photo: {str(e)}")
                # Fallback to text-only message
                logging.debug("Falling back to text-only message")
                await processing_msg.edit_text(response, reply_markup=keyboard)
            finally:
                # Clean up thumbnail file
                try:
                    if os.path.exists(thumbnail_path):
                        os.remove(thumbnail_path)
                        logging.debug("Thumbnail file cleaned up")
                except Exception as e:
                    logging.error(f"Error cleaning up thumbnail: {str(e)}")
        else:
            # Fallback to sending the response without a thumbnail
            logging.debug("Sending text-only response (no thumbnail)")
            await processing_msg.edit_text(response, reply_markup=keyboard)

        # Delete the processing message
        try:
            await processing_msg.delete()
            logging.debug("Deleted processing message")
        except Exception as e:
            logging.error(f"Error deleting processing message: {str(e)}")

    except Exception as e:
        logging.error(f"Unexpected error in handle_youtube_link: {str(e)}")
        error_message = f"❌ Error processing video: {str(e)}"
        try:
            if "processing_msg" in locals():
                await processing_msg.edit_text(error_message)
            else:
                await message.reply_text(error_message)
        except Exception as send_error:
            logging.error(f"Error sending error message: {str(send_error)}")


@app.on_message(
    filters.text
    & ~filters.command("start")
    & ~filters.regex(
        r"(https?://)?(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/.*"
    )
)
async def handle_invalid_input(message):
    """Handle invalid input."""
    if not is_user_allowed(message.from_user.id):
        return  # Silently ignore non-whitelisted users

    await message.reply_text(
        "❌ Please send a valid YouTube video link.\n"
        "The link should start with youtube.com or youtu.be"
    )


@app.on_callback_query()
async def handle_quality_selection(client, callback_query):
    """Handle quality selection button presses."""
    try:
        # Acknowledge the callback query to prevent "Bot is not responding" message
        await callback_query.answer()

        # Extract format ID and video ID from callback data
        data_parts = callback_query.data.split("_")

        if data_parts[0] == "dl":
            format_id = data_parts[1]
            if len(data_parts) > 2:
                video_id = "_".join(data_parts[2:])

                # Handle "unknown" video ID case
                if video_id == "unknown":
                    await callback_query.message.reply_text(
                        "⚠️ Cannot download video: Unable to extract video ID from the original URL. "
                        "Please try sharing the video using a standard YouTube URL format."
                    )
                    return

                # Reconstruct the YouTube URL from the video ID
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                logging.info(f"Reconstructed URL from video ID: {video_url}")

                await download_and_send_video(
                    client, callback_query, format_id, video_url
                )
            else:
                # We only have the format ID, tell user to resend the link
                await callback_query.message.reply_text(
                    "⚠️ Video URL information missing. Please send the YouTube link again."
                )
        elif data_parts[0] == "mp3":
            if len(data_parts) > 1:
                video_id = "_".join(data_parts[1:])

                # Handle special fallback cases
                if video_id == "audio" or video_id == "unknown":
                    await callback_query.message.reply_text(
                        "⚠️ Cannot download audio: missing video URL information. "
                        "Please try sharing the video using a standard YouTube URL format."
                    )
                    return

                # Reconstruct the YouTube URL from the video ID
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                logging.info(f"Reconstructed URL from video ID for audio: {video_url}")

                await download_and_send_audio(client, callback_query, video_url)
            else:
                # We don't have the video ID, tell user to resend the link
                await callback_query.message.reply_text(
                    "⚠️ Video URL information missing. Please send the YouTube link again."
                )

    except Exception as e:
        try:
            error_message = f"❌ Error: {str(e)}"
            logging.error(f"Error in callback handler: {str(e)}", exc_info=True)
            await callback_query.message.reply_text(error_message)
        except Exception as send_error:
            logging.error(f"Error sending error message: {str(send_error)}")
            pass


# Run the bot
if __name__ == "__main__":
    clear_downloads_folder()  # Clear downloads folder on startup
    print("✅ Bot is ready! Send me a YouTube link to get started.")
    app.run()
