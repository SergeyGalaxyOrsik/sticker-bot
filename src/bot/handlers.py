from __future__ import annotations

import os
import re
import tempfile
from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.methods import (
    CreateNewStickerSet,
    AddStickerToSet,
    UploadStickerFile,
    GetStickerSet,
    DeleteStickerFromSet,
    SetStickerSetTitle,
    SetStickerEmojiList,
    SetStickerPositionInSet,
)
from aiogram.types.input_sticker import InputSticker

from ..storage import Storage
from ..utils.slug import slugify
from ..utils.emoji_utils import extract_emoji
from ..utils.converters import convert_image_to_webp_square, convert_video_to_webm_sticker


router = Router()
router.storage = None  # type: ignore[attr-defined]
router.bot_username = ""  # type: ignore[attr-defined]


def build_short_name(title: str) -> str:
    base = slugify(title)
    return base


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.reply(
        "Привет! Я помогу создать стикерпак из фото и видео.\n"
        "Команды:\n"
        "/newpack &lt;название&gt; — создать/выбрать пак (формат по первой медиа)\n"
        "/usepack &lt;название или short_name&gt; — выбрать активный пак\n"
        "Отправь фото/видео с эмодзи в подписи — добавлю в активный пак\n"
        "/listpacks — список твоих паков\n"
        "/list — список стикеров в активном паке\n"
        "/renamepack &lt;новое имя&gt; — переименовать активный пак\n"
        "/delete (в ответ на стикер) — удалить стикер из пака",
    )


@router.message(Command("newpack"))
async def cmd_newpack(message: Message) -> None:
    assert router.storage is not None
    user_id = message.from_user.id if message.from_user else 0
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Укажи название: /newpack МойПак")
        return
    title = args[1].strip()
    # Telegram requires short name to end with _by_<botusername>
    short_base = build_short_name(title)
    # Telegram requires short name to end with _by_<botusername>
    suffix = f"_by_{router.bot_username}"
    short_name = (short_base[:64 - len(suffix)] + suffix) if len(short_base) + len(suffix) > 64 else short_base + suffix
    pack = router.storage.ensure_pack_record(user_id, title, short_name, fmt="static")
    router.storage.set_active_pack(user_id, pack["id"]) 
    await message.reply(
        f"Активный пак: <b>{pack['title']}</b>\n"
        f"short_name: <code>{pack['short_name']}</code>\n"
        "Отправь фото или видео с эмодзи в подписи, чтобы добавить первый стикер",
    )


@router.message(Command("usepack"))
async def cmd_usepack(message: Message) -> None:
    assert router.storage is not None
    user_id = message.from_user.id if message.from_user else 0
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Укажи название или short_name: /usepack МойПак")
        return
    query = args[1].strip()
    pack = router.storage.find_pack_by_title_or_short(user_id, query)
    if not pack:
        await message.reply("Пак не найден")
        return
    router.storage.set_active_pack(user_id, pack["id"]) 
    await message.reply(f"Выбран пак: <b>{pack['title']}</b>\nshort_name: <code>{pack['short_name']}</code>")


@router.message(Command("listpacks"))
async def cmd_listpacks(message: Message) -> None:
    assert router.storage is not None
    user_id = message.from_user.id if message.from_user else 0
    packs = router.storage.list_packs(user_id)
    if not packs:
        await message.reply("У тебя пока нет паков. Создай /newpack")
        return
    lines = [f"• {p['title']} — <code>{p['short_name']}</code> ({p['format']})" for p in packs]
    await message.reply("\n".join(lines))


@router.message(Command("renamepack"))
async def cmd_renamepack(message: Message) -> None:
    assert router.storage is not None
    user_id = message.from_user.id if message.from_user else 0
    pack = router.storage.get_active_pack(user_id)
    if not pack:
        await message.reply("Сначала выбери пак: /newpack или /usepack")
        return
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Укажи новое название: /renamepack НовоеИмя")
        return
    new_title = args[1].strip()
    short_name = pack["short_name"]
    ok = False
    try:
        ok = await SetStickerSetTitle(name=short_name, title=new_title).as_(message.bot)
    except Exception:
        ok = False
    if ok:
        router.storage.update_title(pack["id"], new_title)
        await message.reply(f"Переименовано: <b>{new_title}</b>")
    else:
        await message.reply("Не удалось переименовать набор на стороне Telegram")


@router.message(Command("delete"))
async def cmd_delete(message: Message) -> None:
    if not message.reply_to_message or not message.reply_to_message.sticker:
        await message.reply("Нужно ответить на стикер командой /delete")
        return
    st = message.reply_to_message.sticker
    try:
        ok = await DeleteStickerFromSet(sticker=st.file_id).as_(message.bot)
    except Exception:
        ok = False
    await message.reply("Удалено" if ok else "Не удалось удалить (нужны права владельца)")


@router.message(F.photo | F.video)
async def on_media(message: Message) -> None:
    assert router.storage is not None
    user_id = message.from_user.id if message.from_user else 0
    pack = router.storage.get_active_pack(user_id)
    if not pack:
        await message.reply("Сначала выбери пак: /newpack или /usepack")
        return

    emoji_char = extract_emoji(message.caption)
    if not emoji_char:
        await message.reply("Добавь эмодзи в подписи — оно будет связано со стикером")
        return

    is_video = message.video is not None
    if is_video and pack["format"] == "static":
        router.storage.update_format(pack["id"], "video")
        pack = router.storage.get_active_pack(user_id) or pack
    if not is_video and pack["format"] == "video":
        await message.reply("Этот пак — видео-стикеры. Отправь видео.")
        return

    file = message.video or (message.photo[-1] if message.photo else None)
    if not file:
        await message.reply("Не получилось получить файл")
        return

    file_info = await message.bot.get_file(file.file_id)  # type: ignore[arg-type]
    tmp_fd, tmp_in = tempfile.mkstemp()
    os.close(tmp_fd)
    await message.bot.download_file(file_info.file_path, destination=tmp_in)

    try:
        try:
            if is_video:
                out_path = convert_video_to_webm_sticker(tmp_in)
            else:
                out_path = convert_image_to_webp_square(tmp_in)
        except FileNotFoundError:
            await message.reply("Не найден ffmpeg. Установи: macOS — brew install ffmpeg, Linux — apt/yum install ffmpeg")
            return

        # Ensure pack exists on Telegram or create
        title = pack["title"]
        short_name = pack["short_name"]
        # ensure suffix compliance before creation
        if not short_name.endswith(f"_by_{router.bot_username}"):
            suffix = f"_by_{router.bot_username}"
            base = short_name
            short_name_new = (base[:64 - len(suffix)] + suffix) if len(base) + len(suffix) > 64 else base + suffix
            if short_name_new != short_name:
                router.storage.update_short_name(pack["id"], short_name_new)
                short_name = short_name_new

        # Upload sticker file first
        uploaded = await UploadStickerFile(
            user_id=user_id,
            sticker=FSInputFile(out_path),
            sticker_format=("video" if is_video else "static"),
        ).as_(message.bot)

        input_sticker = InputSticker(
            sticker=uploaded.file_id,
            emoji_list=[emoji_char],
            format="video" if is_video else "static",
        )

        if not pack["created_on_telegram"]:
            created = await CreateNewStickerSet(
                user_id=user_id,
                name=short_name,
                title=title,
                stickers=[input_sticker],
                sticker_type="regular",
            ).as_(message.bot)
            if created:
                router.storage.mark_created_on_telegram(pack["id"]) 
                await message.reply(
                    f"Пак создан и первый стикер добавлен!\nОткрыть: https://t.me/addstickers/{short_name}"
                )
            else:
                await message.reply("Не удалось создать пак. Возможно, короткое имя занято.")
                return
        else:
            ok = await AddStickerToSet(user_id=user_id, name=short_name, sticker=input_sticker).as_(message.bot)
            if ok:
                await message.reply("Стикер добавлен!")
            else:
                await message.reply("Не удалось добавить стикер.")
    finally:
        try:
            os.remove(tmp_in)
        except Exception:
            pass
        try:
            if 'out_path' in locals():
                os.remove(out_path)
        except Exception:
            pass


@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    assert router.storage is not None
    user_id = message.from_user.id if message.from_user else 0
    pack = router.storage.get_active_pack(user_id)
    if not pack:
        await message.reply("Сначала выбери пак: /newpack или /usepack")
        return
    short_name = pack["short_name"]
    try:
        st_set = await GetStickerSet(name=short_name).as_(message.bot)
    except Exception:
        await message.reply("Не удалось получить список стикеров. Возможно, пак ещё не создан.")
        return
    await message.reply(f"В паке {pack['title']}: {len(st_set.stickers)} стикеров")


@router.message(F.text, F.reply_to_message.as_("orig"))
async def on_emoji_reply(message: Message, orig: Message) -> None:
    # Handle case: user sent media without caption, then replies with an emoji
    if not (orig.photo or orig.video):
        return
    emoji_char = extract_emoji(message.text or "")
    if not emoji_char:
        return

    assert router.storage is not None
    user_id = message.from_user.id if message.from_user else 0
    pack = router.storage.get_active_pack(user_id)
    if not pack:
        await message.reply("Сначала выбери пак: /newpack или /usepack")
        return

    is_video = orig.video is not None
    if is_video and pack["format"] == "static":
        router.storage.update_format(pack["id"], "video")
        pack = router.storage.get_active_pack(user_id) or pack
    if not is_video and pack["format"] == "video":
        await message.reply("Этот пак — видео-стикеры. Отправь видео.")
        return

    file = orig.video or (orig.photo[-1] if orig.photo else None)
    if not file:
        await message.reply("Не получилось получить файл")
        return

    file_info = await message.bot.get_file(file.file_id)  # type: ignore[arg-type]
    tmp_fd, tmp_in = tempfile.mkstemp()
    os.close(tmp_fd)
    await message.bot.download_file(file_info.file_path, destination=tmp_in)

    try:
        try:
            if is_video:
                out_path = convert_video_to_webm_sticker(tmp_in)
            else:
                out_path = convert_image_to_webp_square(tmp_in)
        except FileNotFoundError:
            await message.reply("Не найден ffmpeg. Установи: macOS — brew install ffmpeg, Linux — apt/yum install ffmpeg")
            return

        title = pack["title"]
        short_name = pack["short_name"]
        if not short_name.endswith(f"_by_{router.bot_username}"):
            suffix = f"_by_{router.bot_username}"
            base = short_name
            short_name_new = (base[:64 - len(suffix)] + suffix) if len(base) + len(suffix) > 64 else base + suffix
            if short_name_new != short_name:
                router.storage.update_short_name(pack["id"], short_name_new)
                short_name = short_name_new

        uploaded = await UploadStickerFile(
            user_id=user_id,
            sticker=FSInputFile(out_path),
            sticker_format=("video" if is_video else "static"),
        ).as_(message.bot)
        input_sticker = InputSticker(
            sticker=uploaded.file_id,
            emoji_list=[emoji_char],
            format="video" if is_video else "static",
        )

        if not pack["created_on_telegram"]:
            created = await CreateNewStickerSet(
                user_id=user_id,
                name=short_name,
                title=title,
                stickers=[input_sticker],
                sticker_type="regular",
            ).as_(message.bot)
            if created:
                router.storage.mark_created_on_telegram(pack["id"]) 
                await message.reply(
                    f"Пак создан и первый стикер добавлен!\nОткрыть: https://t.me/addstickers/{short_name}"
                )
            else:
                await message.reply("Не удалось создать пак. Возможно, короткое имя занято.")
                return
        else:
            ok = await AddStickerToSet(user_id=user_id, name=short_name, sticker=input_sticker).as_(message.bot)
            if ok:
                await message.reply("Стикер добавлен!")
            else:
                await message.reply("Не удалось добавить стикер.")
    finally:
        try:
            os.remove(tmp_in)
        except Exception:
            pass
        try:
            if 'out_path' in locals():
                os.remove(out_path)
        except Exception:
            pass


@router.message(Command("retitle"))
async def cmd_retitle(message: Message) -> None:
    assert router.storage is not None
    user_id = message.from_user.id if message.from_user else 0
    pack = router.storage.get_active_pack(user_id)
    if not pack:
        await message.reply("Сначала выбери пак: /newpack или /usepack")
        return
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Укажи новое имя набора: /retitle НовоеИмя")
        return
    new_title = args[1].strip()
    short_name = pack["short_name"]
    try:
        ok = await SetStickerSetTitle(name=short_name, title=new_title).as_(message.bot)
    except Exception:
        ok = False
    if ok:
        router.storage.update_title(pack["id"], new_title)
        await message.reply("Название набора обновлено")
    else:
        await message.reply("Не удалось сменить название набора")


@router.message(Command("reemoji"))
async def cmd_reemoji(message: Message) -> None:
    if not message.reply_to_message or not message.reply_to_message.sticker:
        await message.reply("Ответь на стикер командой /reemoji 😀")
        return
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Укажи хотя бы один эмодзи после команды")
        return
    emojis = [ch for ch in args[1] if ch.strip()]
    try:
        ok = await SetStickerEmojiList(sticker=message.reply_to_message.sticker.file_id, emoji_list=emojis).as_(message.bot)
    except Exception:
        ok = False
    await message.reply("Эмодзи обновлены" if ok else "Не удалось обновить эмодзи")


@router.message(Command("move"))
async def cmd_move(message: Message) -> None:
    if not message.reply_to_message or not message.reply_to_message.sticker:
        await message.reply("Ответь на стикер командой /move <позиция>")
        return
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.reply("Укажи число позиции: /move 1")
        return
    position = int(args[1].strip())
    try:
        ok = await SetStickerPositionInSet(sticker=message.reply_to_message.sticker.file_id, position=position).as_(message.bot)
    except Exception:
        ok = False
    await message.reply("Перемещено" if ok else "Не удалось переместить")

