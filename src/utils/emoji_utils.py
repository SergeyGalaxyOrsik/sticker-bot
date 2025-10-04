from typing import Optional
import emoji


def extract_emoji(text: Optional[str]) -> str:
    if not text:
        return ""
    # Return first emoji found, or empty string
    for ch in text:
        if ch in emoji.EMOJI_DATA:
            return ch
    return ""

