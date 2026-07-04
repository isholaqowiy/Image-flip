import os
import io
import logging
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

user_images: dict[int, bytes] = {}


def build_action_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("↔ Flip Horizontal", callback_data="flip_h"),
            InlineKeyboardButton("↕ Flip Vertical",   callback_data="flip_v"),
        ],
        [
            InlineKeyboardButton("↺ Rotate 90°",  callback_data="rot_90"),
            InlineKeyboardButton("↻ Rotate 180°", callback_data="rot_180"),
            InlineKeyboardButton("↺ Rotate 270°", callback_data="rot_270"),
        ],
    ])


def process_image(image_bytes: bytes, action: str) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))

    if action == "flip_h":
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    elif action == "flip_v":
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    elif action == "rot_90":
        img = img.rotate(90, expand=True)
    elif action == "rot_180":
        img = img.rotate(180, expand=True)
    elif action == "rot_270":
        img = img.rotate(270, expand=True)

    buf = io.BytesIO()
    fmt = img.format or "PNG"
    if fmt == "JPEG" and img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf.read()


ACTION_LABELS = {
    "flip_h":  "Flipped Horizontally ↔",
    "flip_v":  "Flipped Vertically ↕",
    "rot_90":  "Rotated 90° ↺",
    "rot_180": "Rotated 180° ↻",
    "rot_270": "Rotated 270° ↺",
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 *Image Flip & Rotate Bot*\n\n"
        "Send me any photo and I'll let you flip or rotate it instantly.\n\n"
        "📤 Just send an image to get started!",
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🛠 *How to use*\n\n"
        "1. Send a photo to the bot\n"
        "2. Choose an action from the buttons:\n"
        "   • ↔ Flip Horizontal\n"
        "   • ↕ Flip Vertical\n"
        "   • ↺ Rotate 90° / 180° / 270°\n"
        "3. Receive the processed image\n\n"
        "You can apply multiple actions one after another!",
        parse_mode="Markdown",
    )


async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    buf = io.BytesIO()
    await file.download_to_memory(buf)
    user_images[user_id] = buf.getvalue()

    await update.message.reply_text(
        "✅ Image received! Choose an action:",
        reply_markup=build_action_keyboard(),
    )


async def receive_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    doc = update.message.document
    if not doc.mime_type or not doc.mime_type.startswith("image/"):
        await update.message.reply_text("⚠️ Please send an image file.")
        return

    user_id = update.effective_user.id
    file = await context.bot.get_file(doc.file_id)

    buf = io.BytesIO()
    await file.download_to_memory(buf)
    user_images[user_id] = buf.getvalue()

    await update.message.reply_text(
        "✅ Image received! Choose an action:",
        reply_markup=build_action_keyboard(),
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    action = query.data

    if user_id not in user_images:
        await query.message.reply_text("⚠️ No image found. Please send a photo first.")
        return

    try:
        result_bytes = process_image(user_images[user_id], action)
        user_images[user_id] = result_bytes

        await query.message.reply_photo(
            photo=io.BytesIO(result_bytes),
