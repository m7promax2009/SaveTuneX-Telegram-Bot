"""
Telegram Music & Video Downloader Bot
@SaveTuneX_bot
Features:
- YouTube Music & Song Search / MP3 Download (192kbps)
- Video Downloader (TikTok, Instagram Reels, YouTube Shorts, YouTube, Pinterest, Twitter/X)
- Video to Round Video Note (Dumaloq video) conversion with FFmpeg
- Shazam Voice & Audio Recognition
- Audio extraction from Videos and Video Notes
- Song Lyrics Fetcher
- Personal Playlist (Save / Play / Delete)
- Admin Panel & User Broadcast
"""

import os
import re
import sys
import time
import asyncio
import logging
import tempfile
import sqlite3
import subprocess
import urllib.parse
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from dotenv import load_dotenv

# Load .env file
load_dotenv()

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import yt_dlp

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("SaveTuneXBot")

# ---------------------------------------------------------------------------
# Configuration & Constants
# ---------------------------------------------------------------------------
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "48"))
SEARCH_RESULTS_COUNT = int(os.getenv("SEARCH_RESULTS_COUNT", "5"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@xam1du11ayev")
BOT_CAPTION = os.getenv("BOT_CAPTION", "👉 @SaveTuneX_bot")
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "6718166903")
ADMIN_IDS = [int(i.strip()) for i in ADMIN_ID_RAW.split(",") if i.strip().isdigit()]

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "users.db"))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# Database Management
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id   INTEGER PRIMARY KEY,
                username  TEXT,
                full_name TEXT,
                joined_at TEXT DEFAULT (datetime('now'))
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS searches (
                query TEXT PRIMARY KEY,
                count INTEGER NOT NULL DEFAULT 1
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS playlists (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id  INTEGER NOT NULL,
                title    TEXT NOT NULL,
                artist   TEXT DEFAULT '',
                yt_url   TEXT NOT NULL,
                added_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()


def register_user(user):
    if not user:
        return
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT OR IGNORE INTO users (user_id, username, full_name)
                VALUES (?, ?, ?)
            """, (user.id, user.username or "", user.full_name or ""))
            conn.commit()
    except Exception as e:
        logger.error(f"register_user error: {e}")


def get_all_user_ids() -> List[int]:
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT user_id FROM users")
            return [r[0] for r in c.fetchall()]
    except Exception as e:
        logger.error(f"get_all_user_ids error: {e}")
        return []


def get_user_count() -> int:
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users")
            row = c.fetchone()
            return row[0] if row else 0
    except Exception as e:
        logger.error(f"get_user_count error: {e}")
        return 0


def get_new_users_today() -> int:
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users WHERE DATE(joined_at) = DATE('now')")
            row = c.fetchone()
            return row[0] if row else 0
    except Exception as e:
        logger.error(f"get_new_users_today error: {e}")
        return 0


def record_search(query: str) -> None:
    q = query.lower().strip()
    if not q:
        return
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO searches (query, count)
                VALUES (?, 1)
                ON CONFLICT(query) DO UPDATE SET count = count + 1
            """, (q,))
            conn.commit()
    except Exception as e:
        logger.error(f"record_search error: {e}")


def get_top_searches(limit: int = 10) -> List[Tuple[str, int]]:
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT query, count FROM searches ORDER BY count DESC LIMIT ?", (limit,))
            return c.fetchall()
    except Exception as e:
        logger.error(f"get_top_searches error: {e}")
        return []


def get_search_count() -> int:
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT SUM(count) FROM searches")
            row = c.fetchone()
            return row[0] or 0 if row else 0
    except Exception as e:
        logger.error(f"get_search_count error: {e}")
        return 0


def add_to_playlist(user_id: int, title: str, artist: str, yt_url: str) -> int:
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO playlists (user_id, title, artist, yt_url) VALUES (?, ?, ?, ?)",
                (user_id, title, artist, yt_url),
            )
            entry_id = c.lastrowid
            conn.commit()
            return entry_id or 0
    except Exception as e:
        logger.error(f"add_to_playlist error: {e}")
        return 0


def remove_from_playlist(user_id: int, entry_id: int) -> None:
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM playlists WHERE id = ? AND user_id = ?", (entry_id, user_id))
            conn.commit()
    except Exception as e:
        logger.error(f"remove_from_playlist error: {e}")


def get_playlist(user_id: int) -> List[Dict]:
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT id, title, artist, yt_url FROM playlists WHERE user_id = ? ORDER BY added_at DESC",
                (user_id,),
            )
            rows = c.fetchall()
            return [{"id": r[0], "title": r[1], "artist": r[2], "url": r[3]} for r in rows]
    except Exception as e:
        logger.error(f"get_playlist error: {e}")
        return []


def playlist_count(user_id: int) -> int:
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM playlists WHERE user_id = ?", (user_id,))
            row = c.fetchone()
            return row[0] if row else 0
    except Exception as e:
        logger.error(f"playlist_count error: {e}")
        return 0


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def main_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("🎵 Musiqa izlash"), KeyboardButton("📱 Video yuklash")],
        [KeyboardButton("🎙 Ovozli qidirish"), KeyboardButton("🎧 Mening pleylistim")],
        [KeyboardButton("👨‍💻 Adminga bog'lanish")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, input_field_placeholder="Tanlang...")


def is_video_url(text: str) -> bool:
    lowered = text.lower().strip()
    domains = [
        "tiktok.com",
        "instagram.com",
        "youtu.be",
        "youtube.com",
        "pin.it",
        "pinterest.com",
        "twitter.com",
        "x.com",
        "facebook.com",
        "fb.watch",
        "threads.net",
    ]
    return any(d in lowered for d in domains)


# ---------------------------------------------------------------------------
# Media Processing (yt-dlp, FFmpeg, Shazam)
# ---------------------------------------------------------------------------

def search_music(query: str, max_results: int = SEARCH_RESULTS_COUNT) -> List[Dict]:
    """Search YouTube for songs with high reliability."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "socket_timeout": 15,
        "http_headers": {"User-Agent": USER_AGENT},
    }
    
    # 1. Primary: YouTube Search
    search_query = f"ytsearch{max_results}:{query}"
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(search_query, download=False)
            if result and "entries" in result:
                entries = []
                for entry in result["entries"]:
                    if not entry:
                        continue
                    duration = entry.get("duration", 0) or 0
                    minutes = int(duration // 60)
                    seconds = int(duration % 60)
                    url = entry.get("url")
                    if not url or not url.startswith("http"):
                        v_id = entry.get("id", "")
                        url = f"https://www.youtube.com/watch?v={v_id}" if v_id else ""
                    
                    entries.append({
                        "id": entry.get("id", ""),
                        "title": entry.get("title", "Noma'lum"),
                        "uploader": entry.get("uploader") or entry.get("channel", "Noma'lum"),
                        "duration": f"{minutes}:{seconds:02d}",
                        "url": url,
                    })
                if entries:
                    return entries
    except Exception as e:
        logger.warning(f"YouTube search failed for '{query}': {e}")

    # 2. Fallback: SoundCloud Search
    try:
        sc_query = f"scsearch{max_results}:{query}"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(sc_query, download=False)
            if result and "entries" in result:
                entries = []
                for entry in result["entries"]:
                    if not entry:
                        continue
                    duration = entry.get("duration", 0) or 0
                    minutes = int(duration // 60)
                    seconds = int(duration % 60)
                    sc_url = entry.get("webpage_url") or entry.get("url", "")
                    entries.append({
                        "id": entry.get("id", ""),
                        "title": entry.get("title", "Noma'lum"),
                        "uploader": entry.get("uploader", "Noma'lum"),
                        "duration": f"{minutes}:{seconds:02d}",
                        "url": sc_url,
                    })
                if entries:
                    return entries
    except Exception as e:
        logger.warning(f"SoundCloud fallback search failed for '{query}': {e}")

    return []


def download_audio(url: str, output_dir: str, fallback_query: str = "") -> Optional[str]:
    """Download audio and convert to 192kbps MP3 with metadata."""
    base_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(output_dir, "%(title).80s.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            },
            {
                "key": "FFmpegMetadata",
                "add_metadata": True,
            },
        ],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "socket_timeout": 25,
        "retries": 3,
        "http_headers": {"User-Agent": USER_AGENT},
    }

    attempts = []
    if url:
        attempts.append(("direct_url", url))
    if fallback_query:
        attempts.append(("yt_search", f"ytsearch1:{fallback_query}"))

    for label, attempt in attempts:
        logger.info(f"Download attempt [{label}]: {attempt[:80]}")
        try:
            with yt_dlp.YoutubeDL(base_opts) as ydl:
                ydl.extract_info(attempt, download=True)
            mp3_files = list(Path(output_dir).glob("*.mp3"))
            if mp3_files:
                logger.info(f"Download succeeded [{label}]: {mp3_files[0].name}")
                return str(mp3_files[0])
        except Exception as e:
            logger.error(f"Download failed [{label}]: {e}")
            continue

    return None


def download_video(url: str, output_dir: str) -> Optional[str]:
    """Download video from Instagram, TikTok, YouTube, etc."""
    ydl_opts = {
        "format": "bestvideo[ext=mp4][filesize<45M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<45M]/best[filesize<45M]/best",
        "outtmpl": os.path.join(output_dir, "video.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "socket_timeout": 30,
        "retries": 3,
        "http_headers": {"User-Agent": USER_AGENT},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
    except Exception as e:
        logger.error(f"yt_dlp download_video failed: {e}")
        return None

    # Check for downloaded video files
    for ext in ("mp4", "mov", "webm", "mkv"):
        p = os.path.join(output_dir, f"video.{ext}")
        if os.path.exists(p):
            # If webm or mkv, convert to standard fast-start mp4 for Telegram
            if ext in ("webm", "mkv"):
                converted_mp4 = os.path.join(output_dir, "video_converted.mp4")
                cmd = [
                    "ffmpeg", "-y", "-i", p,
                    "-c:v", "libx264", "-c:a", "aac",
                    "-movflags", "+faststart", converted_mp4
                ]
                res = subprocess.run(cmd, capture_output=True)
                if res.returncode == 0 and os.path.exists(converted_mp4):
                    return converted_mp4
            return p

    for f in Path(output_dir).iterdir():
        if f.suffix.lower() in (".mp4", ".mov", ".webm", ".mkv"):
            return str(f)

    return None


def get_video_song_info(url: str) -> Dict[str, str]:
    """Extract song/artist metadata from a video URL without downloading."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "nocheckcertificate": True,
        "socket_timeout": 15,
        "http_headers": {"User-Agent": USER_AGENT},
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False) or {}
            track = info.get("track") or info.get("music_track") or ""
            artist = info.get("artist") or info.get("music_artist") or info.get("channel") or info.get("uploader") or ""
            title = info.get("title") or ""

            if track and artist:
                song_query = f"{artist} - {track}"
            elif track:
                song_query = track
            else:
                song_query = title

            return {
                "song_query": song_query.strip(),
                "track": track.strip(),
                "artist": artist.strip(),
            }
    except Exception:
        return {"song_query": "", "track": "", "artist": ""}


def convert_to_round_video(input_path: str, output_path: str) -> bool:
    """Convert input video into Telegram round video note (1:1 aspect ratio, max 60s)."""
    # First check if video has an audio stream
    has_audio = False
    try:
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0", input_path
        ]
        probe_res = subprocess.run(probe_cmd, capture_output=True, text=True)
        has_audio = "audio" in probe_res.stdout
    except Exception:
        has_audio = True

    if has_audio:
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", r"crop=min(iw\,ih):min(iw\,ih),scale=384:384",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "26",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100",
            "-t", "60",
            "-movflags", "+faststart",
            output_path,
        ]
    else:
        # Add silent audio stream to prevent Telegram playback glitches
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-vf", r"crop=min(iw\,ih):min(iw\,ih),scale=384:384",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "26",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            "-t", "60",
            "-movflags", "+faststart",
            output_path,
        ]

    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0 and os.path.exists(output_path)


def extract_audio_from_file(input_path: str, output_path: str) -> bool:
    """Extract MP3 audio from any video/audio container using FFmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vn",
        "-acodec", "libmp3lame",
        "-q:a", "2",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0 and os.path.exists(output_path)


def extract_short_clip(input_path: str, output_path: str, duration: int = 25) -> bool:
    """Extract a short clip for Shazam audio fingerprinting."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-t", str(duration),
        "-vn",
        "-acodec", "mp3",
        "-q:a", "4",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0 and os.path.exists(output_path)


async def recognize_with_shazam(audio_path: str) -> Dict[str, str]:
    """Recognize music track using Shazam."""
    try:
        from shazamio import Shazam
        shazam = Shazam()
        result = await asyncio.wait_for(shazam.recognize(audio_path), timeout=12.0)
        track_data = result.get("track", {})
        title = track_data.get("title", "").strip()
        artist = track_data.get("subtitle", "").strip()
        return {"track": title, "artist": artist}
    except Exception as e:
        logger.warning(f"Shazam recognition error: {e}")
        return {"track": "", "artist": ""}


def store_video_cache(context: ContextTypes.DEFAULT_TYPE, data: dict) -> str:
    key = str(int(time.time() * 1000))[-9:]
    if "video_cache" not in context.bot_data:
        context.bot_data["video_cache"] = {}
    context.bot_data["video_cache"][key] = data
    return key


def fetch_lyrics(artist: str, title: str) -> Optional[str]:
    """Search for song lyrics from online API."""
    import requests as req
    clean_title = re.sub(r"[\(\[][^)\]]*[\)\]]", "", title).strip()
    for t in (clean_title, title):
        for a in (artist, ""):
            try:
                a_enc = urllib.parse.quote(a) if a else "_"
                t_enc = urllib.parse.quote(t)
                url = f"https://api.lyrics.ovh/v1/{a_enc}/{t_enc}"
                resp = req.get(url, timeout=7)
                if resp.ok:
                    data = resp.json()
                    lyrics = data.get("lyrics", "").strip()
                    if lyrics:
                        return lyrics
            except Exception:
                continue
    return None


# ---------------------------------------------------------------------------
# Bot Command & Callback Handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update.effective_user)
    user = update.effective_user
    first_name = user.first_name if user else "Foydalanuvchi"
    await update.message.reply_text(
        f"👋 Salom, <b>{first_name}</b>!\n\n"
        "🎵 <b>SaveTuneX Bot</b>ga xush kelibsiz!\n\n"
        "<b>Nima qila olaman?</b>\n"
        "• 🎵 Qo'shiq nomi yozib yuboring — yuqori sifatli MP3 yuklab beraman\n"
        "• 📱 Instagram Reels / TikTok / YouTube Shorts havolasini yuboring — videoni yuklab beraman\n"
        "• 🔵 Video yuborsangiz — dumaloq video notega aylantiraman\n"
        "• 🎙 Ovozli xabar yuborsangiz — Shazam orqali qo'shiqni topib beraman\n\n"
        "Quyidagi menyudan kerakli bo'limni tanlang 👇",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update.effective_user)
    await update.message.reply_text(
        "ℹ️ <b>Foydalanish bo'yicha yo'riqnoma:</b>\n\n"
        "🎵 <b>Musiqa yuklash:</b>\n"
        "Qo'shiq nomini yozing → topilgan natijalardan kerakli raqamni bosing.\n\n"
        "📱 <b>Video yuklash:</b>\n"
        "Instagram, TikTok yoki YouTube havolasini botga yuboring.\n\n"
        "🔵 <b>Dumaloq video:</b>\n"
        "Istalgan videoni botga yuboring — doira shaklidagi video xabarga aylantiriladi.\n\n"
        "🎙 <b>Ovozli qidiruv:</b>\n"
        "Qo'shiq eshitilayotgan ovozli xabar yuboring, Shazam aniqlaydi.\n\n"
        "<b>Asosiy buyruqlar:</b>\n"
        "/start — Botni ishga tushirish\n"
        "/playlist — Saqlangan qo'shiqlarim\n"
        "/top — Eng ko'p qidirilgan taronalar\n"
        "/help — Qo'llanma",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update.effective_user)
    rows = get_top_searches(10)
    if not rows:
        await update.message.reply_text("📭 Hali qidiruvlar amalga oshirilmagan.")
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>Eng ko'p qidirilgan taronalar:</b>\n"]
    for i, (query, count) in enumerate(rows):
        prefix = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{prefix} <b>{query.title()}</b> — {count} marta")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def playlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update.effective_user)
    user_id = update.effective_user.id
    songs = get_playlist(user_id)

    if not songs:
        await update.message.reply_text(
            "📭 <b>Pleylistingiz hali bo'sh.</b>\n\n"
            "Qo'shiq yuklaganingizda <b>💾 Pleylistga saqlash</b> tugmasini bossangiz, bu yerga qo'shiladi.",
            parse_mode="HTML",
        )
        return

    keyboard = []
    for song in songs[:20]:
        artist_part = f" — {song['artist']}" if song["artist"] else ""
        label = f"🎵 {song['title']}{artist_part}"
        keyboard.append([
            InlineKeyboardButton(label[:50], callback_data=f"plplay:{song['id']}"),
            InlineKeyboardButton("🗑", callback_data=f"pldel:{song['id']}"),
        ])

    await update.message.reply_text(
        f"🎧 <b>Mening pleylistim</b> ({len(songs)} ta qo'shiq)\n\n"
        "▶️ Yuklab olish uchun qo'shiq ustiga bosing, o'chirish uchun 🗑 tugmasini bosing:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Bu buyruq faqat bot admini uchun.")
        return
    keyboard = [
        [InlineKeyboardButton("📊 Statistika", callback_data="adm:stats")],
        [InlineKeyboardButton("📢 Xabar yuborish (Broadcast)", callback_data="adm:broadcast")],
    ]
    await update.message.reply_text(
        "🔐 <b>Admin boshqaruv paneli</b>\n\nKerakli amalni tanlang:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_admin_panel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("❌ Ruxsat berilmagan.", show_alert=True)
        return
    await query.answer()

    action = query.data.split(":", 1)[1]

    if action == "stats":
        user_count = get_user_count()
        new_today = get_new_users_today()
        search_total = get_search_count()
        top = get_top_searches(5)
        top_lines = "\n".join(
            f"  {i}. <b>{q}</b> — {c} marta"
            for i, (q, c) in enumerate(top, 1)
        ) or "  —"
        await query.edit_message_text(
            f"📊 <b>Bot statistikasi</b>\n\n"
            f"👥 Jami foydalanuvchilar: <b>{user_count}</b>\n"
            f"🆕 Bugungi yangilar: <b>{new_today}</b>\n"
            f"🔍 Jami qidiruvlar: <b>{search_total}</b>\n\n"
            f"🏆 <b>Top 5 qidiruv:</b>\n{top_lines}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Yangilash", callback_data="adm:stats"),
                 InlineKeyboardButton("🔙 Orqaga", callback_data="adm:back")],
            ]),
        )

    elif action == "broadcast":
        context.user_data["admin_mode"] = "broadcast"
        await query.edit_message_text(
            "📢 <b>Foydalanuvchilarga xabar yuborish (Broadcast)</b>\n\n"
            "Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yozing yoki rasm yuboring:\n\n"
            "❌ Bekor qilish: <code>/cancel</code>",
            parse_mode="HTML",
        )

    elif action == "back":
        keyboard = [
            [InlineKeyboardButton("📊 Statistika", callback_data="adm:stats")],
            [InlineKeyboardButton("📢 Xabar yuborish (Broadcast)", callback_data="adm:broadcast")],
        ]
        await query.edit_message_text(
            "🔐 <b>Admin boshqaruv paneli</b>\n\nKerakli amalni tanlang:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update.effective_user)
    text = update.message.text.strip()

    # Admin broadcast mode handling
    if is_admin(update.effective_user.id) and context.user_data.get("admin_mode") == "broadcast":
        context.user_data.pop("admin_mode", None)
        if text.lower() == "/cancel":
            await update.message.reply_text("❌ Xabar yuborish bekor qilindi.")
            return

        user_ids = get_all_user_ids()
        sent = 0
        failed = 0
        status_msg = await update.message.reply_text(f"📤 Yuborilmoqda... (0/{len(user_ids)})")
        for i, uid in enumerate(user_ids):
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"📢 <b>Admin xabari:</b>\n\n{text}",
                    parse_mode="HTML",
                )
                sent += 1
            except Exception:
                failed += 1
            if (i + 1) % 25 == 0:
                try:
                    await status_msg.edit_text(f"📤 Yuborilmoqda... ({i+1}/{len(user_ids)})")
                except Exception:
                    pass
            await asyncio.sleep(0.04)

        await status_msg.edit_text(
            f"✅ Xabar yuborildi!\n\n✔️ Yetkazildi: {sent}\n❌ Yetib bormadi: {failed}"
        )
        return

    # Menu Buttons
    if text == "🎵 Musiqa izlash":
        await update.message.reply_text(
            "🎵 Qo'shiq nomi yoki ijrochini yozing:\n\n"
            "<i>Masalan: Tohir Sodiqov Kerak emas</i>",
            parse_mode="HTML",
        )
        return

    if text == "📱 Video yuklash":
        await update.message.reply_text(
            "📱 Instagram Reels, TikTok yoki YouTube Shorts havolasini yuboring:",
        )
        return

    if text == "🎙 Ovozli qidirish":
        await update.message.reply_text(
            "🎙 <b>Ovozli qidiruv</b>\n\n"
            "Qo'shiq ijro etilayotgan ovozli xabarni yuboring — Shazam orqali aniqlab beraman.",
            parse_mode="HTML",
        )
        return

    if text == "🎧 Mening pleylistim":
        await playlist_command(update, context)
        return

    if text == "👨‍💻 Adminga bog'lanish":
        await update.message.reply_text(
            f"👨‍💻 Admin bilan bog'lanish:\n\n{ADMIN_USERNAME}",
        )
        return

    if is_video_url(text):
        await handle_video_url(update, context, text)
        return

    await handle_music_search(update, context, text)


async def handle_music_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    searching_msg = await update.message.reply_text(
        f"🔍 <b>\"{query}\"</b> qidirilmoqda...",
        parse_mode="HTML",
    )

    loop = asyncio.get_running_loop()
    try:
        results = await loop.run_in_executor(None, search_music, query, SEARCH_RESULTS_COUNT)
    except Exception as e:
        logger.error(f"Search execution error: {e}")
        await searching_msg.edit_text("❌ Qidirishda xatolik yuz berdi. Qaytadan urinib ko'ring.")
        return

    if not results:
        await searching_msg.edit_text("😕 Hech qanday natija topilmadi. Boshqa nom bilan qidirib ko'ring.")
        return

    record_search(query)
    context.user_data["search_results"] = results
    context.user_data["last_query"] = query

    lines = []
    for i, track in enumerate(results, 1):
        dur = track.get("duration", "")
        dur_str = f"[{dur}]" if dur else ""
        lines.append(f"{i}. <b>{track['uploader']}</b> — {track['title']} {dur_str}")

    text = (
        f"🎶 <b>\"{query}\"</b> bo'yicha natijalar:\n\n"
        + "\n".join(lines)
        + "\n\n👇 Yuklab olish uchun raqamni bosing:"
    )

    keyboard = [
        [InlineKeyboardButton("📝 Qo'shiq so'zlari", callback_data="lyr:")],
        [InlineKeyboardButton("📹 Video havolasi", callback_data="vids:")],
        [InlineKeyboardButton(str(i + 1), callback_data=f"dl:{i}") for i in range(len(results))],
    ]

    await searching_msg.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_video_url(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
    msg = await update.message.reply_text("⬇️ Video yuklanmoqda, iltimos kuting...")

    loop = asyncio.get_running_loop()
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            output_path = await loop.run_in_executor(None, download_video, url, tmpdir)
        except Exception as e:
            logger.error(f"Video download error: {e}")
            await msg.edit_text("❌ Videoni yuklab bo'lmadi. Havola ochiq va to'g'ri ekanligini tekshiring.")
            return

        if not output_path or not os.path.exists(output_path):
            await msg.edit_text("❌ Video topilmadi yoki yuklash cheklangan.")
            return

        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            await msg.edit_text(
                f"❌ Fayl hajmi juda katta ({file_size_mb:.1f} MB).\n"
                f"Telegram botlar {MAX_FILE_SIZE_MB} MB gacha fayl qabul qiladi."
            )
            return

        await msg.edit_text("🎵 Qo'shiq ma'lumotlari aniqlanmoqda...")
        clip_path = os.path.join(tmpdir, "shazam_clip.mp3")
        clip_ok = await loop.run_in_executor(None, extract_short_clip, output_path, clip_path)

        async def _empty_shazam():
            return {"track": "", "artist": ""}

        shazam_info, ytdl_info = await asyncio.gather(
            recognize_with_shazam(clip_path) if clip_ok else _empty_shazam(),
            loop.run_in_executor(None, get_video_song_info, url),
        )

        track = shazam_info.get("track") or ytdl_info.get("track", "")
        artist = shazam_info.get("artist") or ytdl_info.get("artist", "")
        if track and artist:
            song_query = f"{artist} - {track}"
        elif track:
            song_query = track
        else:
            song_query = ytdl_info.get("song_query", "")

        await msg.edit_text("📤 Video yuborilmoqda...")
        try:
            key = store_video_cache(context, {
                "type": "url",
                "url": url,
                "song_query": song_query,
                "track": track,
                "artist": artist,
            })
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Musiqasini yuklab olish", callback_data=f"extract:{key}")]
            ])
            with open(output_path, "rb") as vf:
                await update.message.reply_video(
                    video=vf,
                    caption=BOT_CAPTION,
                    reply_markup=markup,
                )
            await msg.delete()
        except Exception as e:
            logger.error(f"Video dispatch error: {e}")
            await msg.edit_text("❌ Videoni jo'natishda xatolik yuz berdi.")


async def handle_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("dl:"):
        return

    try:
        idx = int(data.split(":")[1])
    except (IndexError, ValueError):
        return

    results = context.user_data.get("search_results", [])
    if idx < 0 or idx >= len(results):
        await query.answer("Natija topilmadi.", show_alert=True)
        return

    track = results[idx]
    try:
        await query.edit_message_text(
            f"⬇️ <b>{track['title']}</b> yuklanmoqda...\n\nIltimos kuting ⏳",
            parse_mode="HTML",
        )
    except Exception:
        pass

    loop = asyncio.get_running_loop()
    with tempfile.TemporaryDirectory() as tmpdir:
        fallback = f"{track['uploader']} {track['title']}"
        try:
            output_path = await loop.run_in_executor(
                None, download_audio, track["url"], tmpdir, fallback
            )
        except Exception as e:
            logger.error(f"Audio download error: {e}")
            await query.edit_message_text("❌ Qo'shiqni yuklab bo'lmadi. Boshqa variantni tanlang.")
            return

        if not output_path or not os.path.exists(output_path):
            await query.edit_message_text("❌ Fayl topilmadi. Qaytadan urinib ko'ring.")
            return

        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            await query.edit_message_text(f"❌ Fayl hajmi juda katta ({file_size_mb:.1f} MB).")
            return

        try:
            await query.edit_message_text(
                f"📤 <b>{track['title']}</b> yuborilmoqda...",
                parse_mode="HTML",
            )
        except Exception:
            pass

        try:
            track_name = Path(output_path).stem
            save_key = store_video_cache(context, {
                "type": "track",
                "title": track["title"],
                "artist": track["uploader"],
                "url": track["url"],
            })
            audio_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("💾 Pleylistga saqlash", callback_data=f"save:{save_key}")]
            ])
            with open(output_path, "rb") as af:
                await query.message.reply_audio(
                    audio=af,
                    title=track["title"],
                    performer=track["uploader"],
                    caption=BOT_CAPTION,
                    reply_markup=audio_markup,
                )
            await query.edit_message_text(
                f"✅ <b>{track['title']}</b> jo'natildi!\n\nYana musiqa nomi yozishingiz mumkin 🎶",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Audio upload error: {e}")
            await query.edit_message_text("❌ Musiqani jo'natishda xatolik yuz berdi.")


async def handle_video_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update.effective_user)
    video = update.message.video or update.message.document
    if not video:
        return

    msg = await update.message.reply_text("🔄 Video dumaloq video xabarga aylantirilmoqda... ⏳")

    loop = asyncio.get_running_loop()
    with tempfile.TemporaryDirectory() as tmpdir:
        tg_file = await context.bot.get_file(video.file_id)
        input_path = os.path.join(tmpdir, "input_video.mp4")
        await tg_file.download_to_drive(input_path)

        output_path = os.path.join(tmpdir, "round_video.mp4")
        success = await loop.run_in_executor(
            None, convert_to_round_video, input_path, output_path
        )

        if not success or not os.path.exists(output_path):
            await msg.edit_text("❌ Videoni aylantirishda xatolik yuz berdi.")
            return

        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            await msg.edit_text(f"❌ Video hajmi juda katta ({file_size_mb:.1f} MB).")
            return

        await msg.edit_text("📤 Dumaloq video jo'natilmoqda...")
        try:
            key = store_video_cache(context, {"type": "file", "file_id": video.file_id})
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Musiqasini yuklab olish", callback_data=f"extract:{key}")]
            ])
            with open(output_path, "rb") as vf:
                await update.message.reply_video_note(video_note=vf, reply_markup=markup)
            await msg.delete()
        except Exception as e:
            logger.error(f"Video note dispatch error: {e}")
            await msg.edit_text("❌ Dumaloq videoni jo'natishda xatolik yuz berdi.")


async def handle_extract_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("⏳ Audio ajratilmoqda...")

    key = query.data.split(":", 1)[1]
    cache = context.bot_data.get("video_cache", {})
    data = cache.get(key)

    if not data:
        await query.answer("❌ Video ma'lumotlari topilmadi. Yangitdan yuboring.", show_alert=True)
        return

    proc_msg = await query.message.reply_text("🔍 Tarona ma'lumotlari aniqlanmoqda...")
    loop = asyncio.get_running_loop()

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            if data["type"] == "url":
                song_query = data.get("song_query", "").strip()
                track = data.get("track", "").strip()
                artist = data.get("artist", "").strip()

                if not song_query:
                    await proc_msg.edit_text("❌ Videodan musiqa aniqlanmadi.")
                    return

                # Clean query noise
                noise = [
                    "video by", "original audio", "original sound", "sound by",
                    "#", "fyp", "foryou", "foryoupage", "shorts", "reels"
                ]
                clean_query = song_query
                for p in noise:
                    clean_query = re.sub(re.escape(p), "", clean_query, flags=re.IGNORECASE)
                clean_query = re.sub(r"\s+", " ", clean_query).strip()

                display = f"<b>{artist} — {track}</b>" if track and artist else f"<b>{clean_query}</b>"
                await proc_msg.edit_text(
                    f"🎵 Aniqlangan qo'shiq: {display}\n\n⬇️ To'liq MP3 varianti yuklanmoqda...",
                    parse_mode="HTML",
                )

                results = await loop.run_in_executor(None, search_music, clean_query, 1)
                if not results and " - " in clean_query:
                    fallback = clean_query.split(" - ", 1)[1].strip()
                    results = await loop.run_in_executor(None, search_music, fallback, 1)

                if not results:
                    await proc_msg.edit_text(
                        f"😕 <b>{clean_query}</b> bo'yicha to'liq qo'shiq topilmadi.\n"
                        "Qo'shiq nomini matn shaklida yozib ko'ring.",
                        parse_mode="HTML",
                    )
                    return

                yt_url = results[0]["url"]
                yt_title = results[0]["title"]
                yt_artist = results[0]["uploader"]
                output_path = await loop.run_in_executor(None, download_audio, yt_url, tmpdir, clean_query)

            else:
                await proc_msg.edit_text("🎵 Video fayldan to'g'ridan-to'g'ri audio ajratilmoqda...")
                input_path = os.path.join(tmpdir, "video_input.mp4")
                tg_file = await context.bot.get_file(data["file_id"])
                await tg_file.download_to_drive(input_path)

                output_path = os.path.join(tmpdir, "audio.mp3")
                clip_ok = await loop.run_in_executor(None, extract_audio_from_file, input_path, output_path)
                if not clip_ok or not os.path.exists(output_path):
                    await proc_msg.edit_text("❌ Audio ajratib bo'lmadi.")
                    return

                shazam_res = await recognize_with_shazam(output_path)
                yt_title = shazam_res.get("track") or "Videodagi musiqa"
                yt_artist = shazam_res.get("artist") or ""

        except Exception as e:
            logger.error(f"handle_extract_audio error: {e}")
            await proc_msg.edit_text("❌ Musiqani olishda xatolik yuz berdi.")
            return

        if not output_path or not os.path.exists(output_path):
            await proc_msg.edit_text("❌ Audio fayl topilmadi.")
            return

        try:
            with open(output_path, "rb") as af:
                await query.message.reply_audio(
                    audio=af,
                    title=yt_title,
                    performer=yt_artist,
                    caption=BOT_CAPTION,
                )
            await proc_msg.delete()
        except Exception as e:
            logger.error(f"Send audio error: {e}")
            await proc_msg.edit_text("❌ Audioni jo'natishda xatolik yuz berdi.")


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update.effective_user)
    voice = update.message.voice or update.message.audio
    if not voice:
        return

    msg = await update.message.reply_text(
        "🎙 Ovoz tahlil qilinmoqda... ⏳\n<i>Shazam orqali musiqa aniqlanmoqda</i>",
        parse_mode="HTML",
    )

    loop = asyncio.get_running_loop()
    with tempfile.TemporaryDirectory() as tmpdir:
        tg_file = await context.bot.get_file(voice.file_id)
        raw_path = os.path.join(tmpdir, "voice.ogg")
        await tg_file.download_to_drive(raw_path)

        clip_path = os.path.join(tmpdir, "clip.mp3")
        clip_ok = await loop.run_in_executor(None, extract_short_clip, raw_path, clip_path)
        if not clip_ok:
            await msg.edit_text("❌ Ovoz faylini qayta ishlab bo'lmadi.")
            return

        shazam_res = await recognize_with_shazam(clip_path)

    track_title = shazam_res.get("track", "")
    artist = shazam_res.get("artist", "")

    if not track_title:
        await msg.edit_text(
            "😕 <b>Qo'shiqni aniqlab bo'lmadi.</b>\n\n"
            "Ovoz aniqroq bo'lishi yoki musiqani balandroq ijro etishingiz kerak.",
            parse_mode="HTML",
        )
        return

    display = f"🎵 <b>{artist} — {track_title}</b>" if artist else f"🎵 <b>{track_title}</b>"
    search_q = f"{artist} {track_title}".strip()

    await msg.edit_text(
        f"✅ Qo'shiq aniqlandi!\n\n{display}\n\n🔍 Natijalar qidirilmoqda...",
        parse_mode="HTML",
    )

    try:
        results = await loop.run_in_executor(None, search_music, search_q, SEARCH_RESULTS_COUNT)
    except Exception as e:
        logger.error(f"Voice search error: {e}")
        await msg.edit_text(f"✅ Topildi: {display}\n\n❌ Qidirishda xatolik yuz berdi.")
        return

    if not results:
        await msg.edit_text(f"✅ Topildi: {display}\n\n😕 Lekin to'liq audio topilmadi.")
        return

    record_search(search_q)
    context.user_data["search_results"] = results
    context.user_data["last_query"] = search_q

    lines = []
    for i, t in enumerate(results, 1):
        dur = t.get("duration", "")
        dur_str = f"[{dur}]" if dur else ""
        lines.append(f"{i}. <b>{t['uploader']}</b> — {t['title']} {dur_str}")

    text = (
        f"✅ Topildi: {display}\n\n"
        "🎶 Natijalar:\n\n"
        + "\n".join(lines)
        + "\n\n👇 Yuklab olish uchun raqamni bosing:"
    )

    keyboard = [
        [InlineKeyboardButton("📝 Qo'shiq so'zlari", callback_data="lyr:")],
        [InlineKeyboardButton("📹 Video havolasi", callback_data="vids:")],
        [InlineKeyboardButton(str(i + 1), callback_data=f"dl:{i}") for i in range(len(results))],
    ]

    await msg.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_lyrics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    results = context.user_data.get("search_results", [])
    if not results:
        await query.message.reply_text("❌ Avval qo'shiq qidiring.")
        return

    track = results[0]
    artist = track.get("uploader", "")
    title = track.get("title", "")

    msg = await query.message.reply_text(
        f"📝 <b>{artist} — {title}</b> matni qidirilmoqda...",
        parse_mode="HTML",
    )

    loop = asyncio.get_running_loop()
    lyrics = await loop.run_in_executor(None, fetch_lyrics, artist, title)

    if not lyrics:
        await msg.edit_text(
            f"😕 <b>{artist} — {title}</b> uchun matn topilmadi.",
            parse_mode="HTML",
        )
        return

    header = f"📝 <b>{artist} — {title}</b>\n\n"
    max_len = 4000 - len(header)
    if len(lyrics) <= max_len:
        await msg.edit_text(header + lyrics, parse_mode="HTML")
    else:
        await msg.edit_text(header + lyrics[:max_len], parse_mode="HTML")
        remainder = lyrics[max_len:]
        while remainder:
            chunk = remainder[:4000]
            await query.message.reply_text(chunk)
            remainder = remainder[4000:]


async def handle_video_links(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    results = context.user_data.get("search_results", [])
    if not results:
        await query.answer("❌ Natijalar topilmadi.", show_alert=True)
        return

    lines = []
    for i, track in enumerate(results, 1):
        url = track.get("url", "")
        lines.append(f"{i}. <a href=\"{url}\">{track['title']}</a>")

    await query.message.reply_text(
        "📹 <b>Video havolalar:</b>\n\n" + "\n".join(lines),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def handle_save_playlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    key = query.data.split(":", 1)[1]
    cache = context.bot_data.get("video_cache", {})
    data = cache.get(key)

    if not data:
        await query.answer("❌ Ma'lumot topilmadi.", show_alert=True)
        return

    user_id = query.from_user.id
    title = data.get("title", "Noma'lum")
    artist = data.get("artist", "")
    url = data.get("url", "")

    add_to_playlist(user_id, title, artist, url)
    count = playlist_count(user_id)

    await query.answer(f"✅ Saqlandi! Pleylistingizda {count} ta tarona bor.", show_alert=False)
    try:
        new_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Pleylistda saqlangan", callback_data="noop")]
        ])
        await query.edit_message_reply_markup(reply_markup=new_markup)
    except Exception:
        pass


async def handle_playlist_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query.data == "noop":
        await query.answer()
        return

    await query.answer()
    user_id = query.from_user.id

    action, entry_id_str = query.data.split(":", 1)
    entry_id = int(entry_id_str)

    if action == "pldel":
        remove_from_playlist(user_id, entry_id)
        songs = get_playlist(user_id)
        if not songs:
            await query.edit_message_text("📭 Pleylistingiz bo'shatildi.")
            return

        keyboard = []
        for song in songs[:20]:
            artist_part = f" — {song['artist']}" if song["artist"] else ""
            label = f"🎵 {song['title']}{artist_part}"
            keyboard.append([
                InlineKeyboardButton(label[:50], callback_data=f"plplay:{song['id']}"),
                InlineKeyboardButton("🗑", callback_data=f"pldel:{song['id']}"),
            ])

        await query.edit_message_text(
            f"🎧 <b>Mening pleylistim</b> ({len(songs)} ta qo'shiq)\n\n"
            "▶️ Yuklab olish uchun qo'shiq ustiga bosing, o'chirish uchun 🗑 tugmasini bosing:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif action == "plplay":
        songs = get_playlist(user_id)
        song = next((s for s in songs if s["id"] == entry_id), None)
        if not song:
            await query.answer("❌ Qo'shiq topilmadi.", show_alert=True)
            return

        msg = await query.message.reply_text(
            f"⬇️ <b>{song['title']}</b> yuklanmoqda...",
            parse_mode="HTML",
        )
        loop = asyncio.get_running_loop()
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                output_path = await loop.run_in_executor(
                    None, download_audio, song["url"], tmpdir, f"{song['artist']} {song['title']}"
                )
            except Exception as e:
                logger.error(f"Playlist download error: {e}")
                await msg.edit_text("❌ Yuklab bo'lmadi. Qaytadan urinib ko'ring.")
                return

            if not output_path or not os.path.exists(output_path):
                await msg.edit_text("❌ Fayl topilmadi.")
                return

            try:
                with open(output_path, "rb") as af:
                    await query.message.reply_audio(
                        audio=af,
                        title=song["title"],
                        performer=song["artist"],
                        caption=BOT_CAPTION,
                    )
                await msg.delete()
            except Exception as e:
                logger.error(f"Playlist send error: {e}")
                await msg.edit_text("❌ Faylni jo'natishda xatolik yuz berdi.")


async def handle_admin_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return
    if context.user_data.get("admin_mode") != "broadcast":
        return
    context.user_data.pop("admin_mode", None)

    photo = update.message.photo[-1]
    caption = update.message.caption or ""

    user_ids = get_all_user_ids()
    sent = 0
    failed = 0
    status_msg = await update.message.reply_text(f"📤 Rasm yuborilmoqda... (0/{len(user_ids)})")

    for i, uid in enumerate(user_ids):
        try:
            await context.bot.send_photo(
                chat_id=uid,
                photo=photo.file_id,
                caption=f"📢 <b>Admin xabari:</b>\n\n{caption}" if caption else "📢 <b>Admin xabari:</b>",
                parse_mode="HTML",
            )
            sent += 1
        except Exception:
            failed += 1
        if (i + 1) % 20 == 0:
            try:
                await status_msg.edit_text(f"📤 Rasm yuborilmoqda... ({i+1}/{len(user_ids)})")
            except Exception:
                pass
        await asyncio.sleep(0.04)

    await status_msg.edit_text(
        f"✅ Rasm yuborildi!\n\n✔️ Yetkazildi: {sent}\n❌ Yetib bormadi: {failed}"
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates to prevent silent failures."""
    logger.error(f"Exception while handling an update: {context.error}")


# ---------------------------------------------------------------------------
# Application Initialization
# ---------------------------------------------------------------------------

def start_health_server(port: int) -> None:
    """Start lightweight HTTP health server for cloud hosting (Render, Railway, etc.)."""
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","service":"SaveTuneX_bot"}')

        def log_message(self, format, *args):
            pass  # Suppress noisy health check logs

    try:
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f"Health check HTTP server faol: port {port}")
    except Exception as e:
        logger.warning(f"Health server failed to start on port {port}: {e}")


def main() -> None:
    init_db()

    # If PORT env is present (Render, Railway, Heroku), start background health check server
    port_env = os.getenv("PORT")
    if port_env and port_env.isdigit():
        start_health_server(int(port_env))

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN muhit o'zgaruvchisi topilmadi!")
        print("\n[XATOLIK] TELEGRAM_BOT_TOKEN muhit o'zgaruvchisi o'rnatilmagan.")
        print("Iltimos, .env fayl yarating va quyidagicha to'ldiring:")
        print("TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ")
        print("ADMIN_ID=6718166903\n")
        sys.exit(1)

    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CommandHandler("playlist", playlist_command))
    app.add_handler(CommandHandler("admin", admin_command))

    # Callbacks
    app.add_handler(CallbackQueryHandler(handle_admin_panel_cb, pattern=r"^adm:"))
    app.add_handler(CallbackQueryHandler(handle_download_callback, pattern=r"^dl:"))
    app.add_handler(CallbackQueryHandler(handle_extract_audio, pattern=r"^extract:"))
    app.add_handler(CallbackQueryHandler(handle_save_playlist, pattern=r"^save:"))
    app.add_handler(CallbackQueryHandler(handle_lyrics, pattern=r"^lyr:"))
    app.add_handler(CallbackQueryHandler(handle_video_links, pattern=r"^vids:"))
    app.add_handler(CallbackQueryHandler(handle_playlist_action, pattern=r"^(plplay|pldel|noop)"))

    # Media & Messages
    app.add_handler(MessageHandler(filters.PHOTO, handle_admin_photo))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice_message))
    app.add_handler(MessageHandler(
        filters.VIDEO | (filters.Document.VIDEO) | (filters.Document.MimeType("video/mp4")),
        handle_video_file,
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Error handling
    app.add_error_handler(error_handler)

    logger.info("Bot muvaffaqiyatli ishga tushdi va xabarlarni kutmoqda...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
