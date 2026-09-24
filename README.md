# 🎵 SaveTuneX Telegram Bot (Python)

Telegram orqali musiqa qidirish, MP3 yuklab olish, ijtimoiy tarmoqlardan (Instagram Reels, TikTok, YouTube Shorts) video yuklash, doira shaklidagi video xabarlarga aylantirish va Shazam orqali ovozdan musiqa topish boti.

---

## 🚀 Asosiy imkoniyatlar:
- 🎶 **Musiqa qidirish va yuklash:** YouTube va SoundCloud orqali qidiradi, 192kbps MP3 formatida metadata bilan yuboradi.
- 📱 **Video yuklovchi:** Instagram Reels, TikTok, YouTube Shorts, YouTube, Pinterest, Twitter/X havolalaridan video yuklaydi.
- 🔵 **Dumaloq video (Video Note):** Har qanday video yoki faylni 1:1 o'lchamdagi Telegram doira videosiga aylantiradi. Ovoz bo'lmagan videolarda ham xatosiz ishlaydi.
- 🎙 **Shazam ovozli qidiruv:** Ovozli xabar (voice message) yuborilsa, Shazam orqali musiqa va ijrochini aniqlab, to'liq versiyasini topadi.
- 📥 **Videodan audio ajratish:** Har bir yuklangan video ostida bitta tugma bilan musiqasini MP3 qilib ajratib beradi.
- 💾 **Shaxsiy pleylist:** Yoqtirgan qo'shiqlarni pleylistga saqlash, qayta eshitish va o'chirish.
- 📝 **Qo'shiq so'zlari (Lyrics):** Qo'shiq so'zlarini API orqali topib, xabar qilib berish.
- 📊 **Admin panel:** Foydalanuvchilar statistikasi, top qidiruvlar va barcha a'zolarga xabar (Broadcast - matn va rasm) yuborish.

---

## 🛠 O'rnatish va Ishga tushirish

### 1. Talablar:
- **Python:** 3.11+
- **FFmpeg:** Tizimda o'rnatilgan bo'lishi shart (audio va video konvertatsiya uchun).

#### FFmpeg o'rnatish:
- **Ubuntu / Debian:** `sudo apt update && sudo apt install -y ffmpeg`
- **macOS:** `brew install ffmpeg`
- **Windows:** [gyan.dev/ffmpeg](https://www.gyan.dev/ffmpeg/builds/) orqali yuklab olib, PATH ga qo'shing.

---

### 2. Sozlash (.env):
Papka ichidagi `.env.example` dan `.env` fayl nusxasini oling:
```bash
cp .env.example .env
```

`.env` faylini ochib, o'z ma'lumotlaringizni kiriting:
```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
ADMIN_ID=6718166903
ADMIN_USERNAME=@xam1du11ayev
BOT_CAPTION=👉 @SaveTuneX_bot
```

---

### 3. Ishga tushirish:

#### Linux / macOS:
```bash
bash start.sh
```

yoki qo'lda:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 bot.py
```

#### Windows:
```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python bot.py
```

---

## ⚡ Serverda (VPS) 24/7 ishlatish (Systemd)

`/etc/systemd/system/savetunex.service` faylini yarating:
```ini
[Unit]
Description=SaveTuneX Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/Telegram-Python-Bot
ExecStart=/path/to/Telegram-Python-Bot/.venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Faollashtirish:
```bash
sudo systemctl daemon-reload
sudo systemctl enable savetunex
sudo systemctl start savetunex
sudo systemctl status savetunex
```
