import os
import subprocess
import shutil
import tempfile
from typing import Tuple

from PIL import Image


def convert_image_to_webp_square(input_path: str) -> str:
    with Image.open(input_path) as img:
        img = img.convert("RGBA")
        max_size = 512
        img.thumbnail((max_size, max_size), Image.LANCZOS)

        # pad to square with transparent background
        width, height = img.size
        size = max(width, height)
        background = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        offset = ((size - width) // 2, (size - height) // 2)
        background.paste(img, offset)

        fd, out_path = tempfile.mkstemp(suffix=".webp")
        os.close(fd)
        background.save(out_path, format="WEBP", lossless=True)
        return out_path


def convert_video_to_webm_sticker(input_path: str) -> str:
    # Telegram doc: max 3 sec, 512x512, no audio, VP9
    fd, out_path = tempfile.mkstemp(suffix=".webm")
    os.close(fd)
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise FileNotFoundError("ffmpeg")
    cmd = [
        ffmpeg_path,
        "-y",
        "-i",
        input_path,
        "-t",
        "3",
        "-vf",
        "scale='min(512,iw)':'min(512,ih)':force_original_aspect_ratio=decrease, pad=512:512:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p",
        "-an",
        "-c:v",
        "libvpx-vp9",
        "-b:v",
        "0",
        "-crf",
        "35",
        "-deadline",
        "realtime",
        out_path,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_path

