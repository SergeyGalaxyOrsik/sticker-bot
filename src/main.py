import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from .config import load_config
from .storage import Storage
from .bot.handlers import router as bot_router


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = load_config()

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    storage = Storage(config.database_path)
    storage.initialize()

    # Provide shared objects via context
    dp.include_router(bot_router)
    bot_router.storage = storage  # type: ignore[attr-defined]

    me = await bot.get_me()
    bot_router.bot_username = me.username or ""  # type: ignore[attr-defined]

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass

