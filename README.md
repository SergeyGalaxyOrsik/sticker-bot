## Telegram Sticker Pack Bot (photo + video)

Requirements:
- Python 3.10+
- FFmpeg installed and available in PATH

Setup:
1. Create and fill `.env` from `.env.example` with your bot token.
2. Install dependencies:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Run the bot:
   ```bash
   python -m src.main
   ```

Usage (basic):
- /start — help
- /newpack <title> — create/select a pack (first media adds & creates on Telegram)
- /usepack <title or short_name> — select active pack
- Send photo/video with an emoji in caption to add to active pack
- Reply to a sticker with /delete to remove it from the set
- /listpacks — list your packs
- /list — list stickers in active pack
- /renamepack <new title> — rename active pack (applies on Telegram)
- Reply to a sticker with /reemoji 😀 — change sticker emoji list
- Reply to a sticker with /move <pos> — change sticker order

Notes:
- For photos, the bot converts to WEBP 512×512.
- For videos, converts to WEBM (VP9), max ~3s, 512×512, no audio.
- FFmpeg must be installed (e.g., `brew install ffmpeg`).
- Packs are created under your account via this bot; the bot can then edit them.

