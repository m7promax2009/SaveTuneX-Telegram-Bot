#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "=== SaveTuneX Bot ishga tushirilmoqda ==="

if [ ! -d ".venv" ]; then
    echo "Virtual environment yaratilmoqda..."
    python3 -m venv .venv
fi

source .venv/bin/activate
echo "Kutubxonalar tekshirilmoqda..."
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "DIQQAT: .env fayl topilmadi! .env.example asosida .env yaratildi."
        cp .env.example .env
        echo "Iltimos, .env faylni ochib TELEGRAM_BOT_TOKEN ni kiriting!"
        exit 1
    fi
fi

echo "Bot ishga tushdi..."
python3 bot.py
