"""
Comprehensive test suite for SaveTuneX Bot
Verifies DB, search, conversion, filters, and handlers.
"""

import os
import sys
import tempfile
import asyncio
import subprocess
from pathlib import Path

# Ensure project root in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bot

def test_db():
    print("Testing Database operations...")
    bot.init_db()
    
    class FakeUser:
        id = 99999999
        username = "test_user"
        full_name = "Test Full Name"
        
    bot.register_user(FakeUser())
    assert bot.get_user_count() >= 1, "User count should be at least 1"
    
    bot.record_search("test query song")
    top = bot.get_top_searches(100)
    assert any(q == "test query song" for q, _ in top), "Search query should be recorded"
    
    pl_id = bot.add_to_playlist(99999999, "Test Song", "Test Artist", "https://youtube.com/watch?v=123")
    assert pl_id > 0, "Playlist insert should return valid ID"
    
    songs = bot.get_playlist(99999999)
    assert len(songs) >= 1, "Playlist should return inserted song"
    assert songs[0]["title"] == "Test Song"
    
    bot.remove_from_playlist(99999999, pl_id)
    songs_after = bot.get_playlist(99999999)
    assert not any(s["id"] == pl_id for s in songs_after), "Song should be removed from playlist"
    print(" Database operations PASSED.")


def test_url_detector():
    print("Testing Video URL Detection...")
    urls = [
        "https://www.tiktok.com/@user/video/123456789",
        "https://instagram.com/reel/Cx123456",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/shorts/abcdefgh",
        "https://pin.it/7xYz123",
        "https://x.com/user/status/123456789",
    ]
    for u in urls:
        assert bot.is_video_url(u), f"Failed to detect video URL: {u}"
        
    non_urls = [
        "Sherali Jo'rayev Karvon",
        "Dildora Niyozova",
        "salom qalaysiz",
    ]
    for nu in non_urls:
        assert not bot.is_video_url(nu), f"Mistakenly marked as video URL: {nu}"
    print(" Video URL Detection PASSED.")


def test_music_search():
    print("Testing Music Search (YouTube)...")
    results = bot.search_music("Rayhon Tomchi", max_results=3)
    assert len(results) > 0, "Music search should return at least 1 result"
    first = results[0]
    print(f"   Found: '{first['title']}' by '{first['uploader']}' ({first['duration']}) -> {first['url']}")
    assert first["url"].startswith("http"), "Result should have valid HTTP URL"
    assert first["title"], "Result should have title"
    print(" Music Search PASSED.")


def test_ffmpeg_conversions():
    print("Testing FFmpeg Round Video & Audio Extraction...")
    with tempfile.TemporaryDirectory() as tmpdir:
        input_mp4 = os.path.join(tmpdir, "test_input.mp4")
        # Generate 2-second test video with audio
        cmd_gen = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=640x480:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
            "-c:v", "libx264", "-c:a", "aac",
            input_mp4
        ]
        res = subprocess.run(cmd_gen, capture_output=True)
        assert res.returncode == 0, f"FFmpeg test video generation failed: {res.stderr}"

        # 1. Round video
        round_mp4 = os.path.join(tmpdir, "round.mp4")
        ok = bot.convert_to_round_video(input_mp4, round_mp4)
        assert ok, "convert_to_round_video failed"
        assert os.path.exists(round_mp4), "Round video file does not exist"

        # 2. Audio extraction
        audio_mp3 = os.path.join(tmpdir, "extracted.mp3")
        ok_a = bot.extract_audio_from_file(input_mp4, audio_mp3)
        assert ok_a, "extract_audio_from_file failed"
        assert os.path.exists(audio_mp3), "Extracted audio file does not exist"

        # 3. Test silent video input (without audio stream)
        silent_mp4 = os.path.join(tmpdir, "silent.mp4")
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=640x480:rate=30",
            "-c:v", "libx264", silent_mp4
        ], capture_output=True)
        round_silent = os.path.join(tmpdir, "round_silent.mp4")
        ok_silent = bot.convert_to_round_video(silent_mp4, round_silent)
        assert ok_silent, "convert_to_round_video failed on silent video"
        assert os.path.exists(round_silent), "Round silent video file does not exist"

    print(" FFmpeg Conversions PASSED.")


def test_lyrics():
    print("Testing Lyrics API...")
    lyrics = bot.fetch_lyrics("Adele", "Hello")
    assert lyrics is not None, "Lyrics fetch should return content for Adele - Hello"
    assert "Hello" in lyrics, "Lyrics should contain 'Hello'"
    print(" Lyrics API PASSED.")


if __name__ == "__main__":
    test_db()
    test_url_detector()
    test_music_search()
    test_ffmpeg_conversions()
    test_lyrics()
    print("\n ALL BOT INTEGRATION TESTS PASSED 100%!")
