import logging
import os
from threading import Thread
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from database import init_db, save_user, save_dream, get_dreams, clear_dreams, get_all_dreams_text, user_exists
from llm import analyze_dream, is_dream_related

# Flask-сервер для health-check (нужен Render и аналогичным платформам)
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Бот 'Карта сновидений' работает!"

@flask_app.route("/health")
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)

flask_thread = Thread(target=run_flask, daemon=True)
flask_thread.start()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton("💭 Рассказать сон"), KeyboardButton("📜 История снов")],
     [KeyboardButton("🗑 Очистить историю"), KeyboardButton("❓ Помощь")]],
    resize_keyboard=True
)

CLEAR_INLINE = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("✅ Да, удалить", callback_data="clear_confirm"),
        InlineKeyboardButton("❌ Отмена", callback_data="clear_cancel"),
    ]
])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    save_user(user.id, user.username or "", user.first_name or "")
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "Я — *Психолог подсознания*. Я анализирую ваши сны в традиции юнгианской психологии "
        "и строю карту вашего подсознания, отслеживая динамику образов со временем.\n\n"
        "🌙 *Как использовать:*\n"
        "Просто напишите мне описание своего сна — и я дам вам глубокий анализ.\n\n"
        "📋 *Команды:*\n"
        "/history — история ваших снов\n"
        "/clear — очистить историю\n"
        "/export — скачать всю историю\n"
        "/help — помощь\n\n"
        "✨ Расскажите мне свой первый сон...",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🔮 *Психолог подсознания — Справка*\n\n"
        "Просто напишите описание сна — бот сохранит его и даст психологический анализ.\n\n"
        "📋 *Команды:*\n"
        "• /start — начало работы\n"
        "• /history — список ваших снов\n"
        "• /clear — очистить историю снов\n"
        "• /export — скачать всю историю в .txt\n"
        "• /help — эта справка\n\n"
        "🧠 *Как работает анализ:*\n"
        "Каждый новый сон анализируется с учётом всей вашей истории. "
        "Бот отслеживает повторяющиеся символы, динамику страхов и желаний, "
        "и обновляет карту вашего подсознания.",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD
    )

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    dreams = get_dreams(user_id, limit=20)
    if not dreams:
        await update.message.reply_text(
            "📭 У вас ещё нет записанных снов.\n\nПросто напишите описание своего сна!",
            reply_markup=MAIN_KEYBOARD
        )
        return

    lines = ["📜 *Ваши сны:*\n"]
    for i, dream in enumerate(dreams, 1):
        preview = dream["dream_text"][:50] + ("..." if len(dream["dream_text"]) > 50 else "")
        lines.append(f"{i}. [{dream['timestamp']}]\n   {preview}")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD
    )

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "⚠️ *Вы уверены?*\n\nВся история снов будет удалена безвозвратно.",
        parse_mode="Markdown",
        reply_markup=CLEAR_INLINE
    )

async def clear_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "clear_confirm":
        clear_dreams(query.from_user.id)
        await query.edit_message_text("🗑 История снов очищена.")
    elif query.data == "clear_cancel":
        await query.edit_message_text("❌ Отменено. История сохранена.")
    elif query.data == "do_start":
        user = query.from_user
        await query.edit_message_text(
            f"🚀 Отлично, {user.first_name}! Добро пожаловать.\n\n"
            "Просто напишите мне описание своего сна — и я начну анализ."
        )
        save_user(user.id, user.username or "", user.first_name or "")
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=(
                f"👋 Привет, {user.first_name}!\n\n"
                "Я — *Психолог подсознания*. Я анализирую ваши сны в традиции юнгианской психологии "
                "и строю карту вашего подсознания, отслеживая динамику образов со временем.\n\n"
                "🌙 *Как использовать:*\n"
                "Просто напишите мне описание своего сна — и я дам вам глубокий анализ.\n\n"
                "📋 *Команды:*\n"
                "/history — история ваших снов\n"
                "/clear — очистить историю\n"
                "/export — скачать всю историю\n"
                "/help — помощь\n\n"
                "✨ Расскажите мне свой первый сон..."
            ),
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD
        )

async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = get_all_dreams_text(user_id)
    if not text:
        await update.message.reply_text(
            "📭 У вас ещё нет записанных снов.",
            reply_markup=MAIN_KEYBOARD
        )
        return

    filename = f"dreams_{user_id}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(text)

    with open(filename, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename="мои_сны.txt",
            caption="📄 Ваша история снов"
        )

    os.remove(filename)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user = update.effective_user

    if text == "💭 Рассказать сон":
        await update.message.reply_text(
            "🌙 Опишите ваш сон — я готов слушать...",
            reply_markup=MAIN_KEYBOARD
        )
        return
    elif text == "📜 История снов":
        await history(update, context)
        return
    elif text == "❓ Помощь":
        await help_command(update, context)
        return
    elif text == "🗑 Очистить историю":
        await clear_command(update, context)
        return

    if not user_exists(user.id):
        await update.message.reply_text(
            "👋 Привет! Я — бот «Психолог подсознания».\n\n"
            "Я толкую сны в традиции юнгианской психологии и строю карту вашего подсознания.\n\n"
            "Чтобы начать, нажмите кнопку ниже 👇",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Начать", callback_data="do_start")]
            ])
        )
        return

    save_user(user.id, user.username or "", user.first_name or "")

    if not await is_dream_related(text):
        await update.message.reply_text(
            "🌙 Я специализируюсь только на толковании снов и построении карты подсознания.\n\n"
            "Расскажите мне о своём сне — и я помогу разобраться в его значении.",
            reply_markup=MAIN_KEYBOARD
        )
        return

    thinking_msg = await update.message.reply_text(
        "🔮 Анализирую ваш сон...",
    )

    dream_id = save_dream(user.id, text, "")

    previous_dreams = get_dreams(user.id, limit=10)
    previous_dreams = [d for d in previous_dreams if d["id"] != dream_id]

    try:
        interpretation = await analyze_dream(text, previous_dreams)
        save_dream(user.id, text, interpretation, dream_id=dream_id)

        try:
            await thinking_msg.delete()
        except Exception:
            pass

        chunks = split_message(interpretation)
        for i, chunk in enumerate(chunks):
            kb = MAIN_KEYBOARD if i == len(chunks) - 1 else None
            await update.message.reply_text(chunk, reply_markup=kb)

        logger.info(f"Dream analyzed for user {user.id}, dream_id={dream_id}")

    except Exception as e:
        logger.error(f"Error analyzing dream for user {user.id}: {e}")
        try:
            await thinking_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(
            "❗ Не удалось получить анализ. Попробуйте ещё раз через минуту.",
            reply_markup=MAIN_KEYBOARD
        )

def split_message(text: str, max_len: int = 4000) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks

def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    init_db()
    logger.info("Database initialized")

    async def post_init(app: Application) -> None:
        await app.bot.set_my_description(
            "🌙 Психолог подсознания\n\n"
            "Я анализирую ваши сны в традиции юнгианской психологии и строю карту вашего подсознания. "
            "Нажмите «Начать», чтобы приступить."
        )
        await app.bot.set_my_short_description(
            "Толкователь снов. Юнгианский анализ. Карта подсознания."
        )

    app = Application.builder().token(token).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("export", export_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CallbackQueryHandler(clear_callback, pattern="^(clear_|do_start)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot started — polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
