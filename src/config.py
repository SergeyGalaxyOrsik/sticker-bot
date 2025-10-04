import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class Config:
    bot_token: str
    database_path: str


def load_config() -> Config:
    load_dotenv()
    bot_token = os.getenv("BOT_TOKEN")
    database_path = os.getenv("DATABASE_PATH", "./data/bot.db")

    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set in environment")

    os.makedirs(os.path.dirname(database_path), exist_ok=True)
    return Config(bot_token=bot_token, database_path=database_path)

