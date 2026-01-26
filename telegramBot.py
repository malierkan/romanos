from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ConversationHandler,
)

from scheduler import Scheduler
from postRepository import PostRepository
from zoneinfo import ZoneInfo
from datetime import datetime
from pathlib import Path


ASK_TEXT, ASK_IMAGE = range(2)

CATEGORY_HISTORY_TODAY = "category_history_today"
CATEGORY_QUOTE = "category_quote"
CATEGORY_QUESTION = "category_question"

CATEGORY_HISTORY_DEFAULT_IMG = Path("./images/history.jpg")


class TelegramBot:
    def __init__(self, token: str, timezone: ZoneInfo, posts_file: str):
        self.application = Application.builder().token(token).build()
        self.timezone = timezone
        self.posts_file = posts_file
        self.current_category = None

    # Category handler

    async def category_selected(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        query = update.callback_query
        await query.answer()

        category = query.data

        if category == CATEGORY_HISTORY_TODAY:
            self.current_category = CATEGORY_HISTORY_TODAY
            await query.edit_message_text(
                "📜 Lütfen paylaşmak istediğiniz yazıyı gönderin:"
            )
            return ASK_TEXT

        elif category == CATEGORY_QUOTE:
            await query.edit_message_text("Günün Sözü seçildi!")

        elif category == CATEGORY_QUESTION:
            await query.edit_message_text("Sorular seçildi!")

    # Data fetchers

    async def receive_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["new_post_text"] = update.message.text

        # if this category has a photo already pass it
        if self.current_category == CATEGORY_HISTORY_TODAY:
            if CATEGORY_HISTORY_DEFAULT_IMG.exists():
                context.user_data["image"] = CATEGORY_HISTORY_DEFAULT_IMG
                return await self.create_post(update, context)

        else:
            await update.message.reply_text(
                "📸 Eğer bir fotoğraf eklemek istiyorsanız gönderin, yoksa /skip yazabilirsiniz."
            )
            return ASK_IMAGE

    async def receive_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        photo = update.message.photo[-1] if update.message.photo else None
        file_id = photo.file_id if photo else None

        context.user_data["new_post_file_id"] = file_id

        await update.message.reply_text(
            "✅ Fotoğraf kaydedildi. Postu oluşturuyorum..."
        )
        return await self.create_post(update, context)

    async def skip_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await self.receive_image(update, context)

    # Post builders

    async def create_post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        new_post = self.build_post(context.user_data, True)
        await self.save_and_schedule_post(new_post, update)
        return ConversationHandler.END

    def build_post(
        self, context_user_data: dict, yearly_repeated: bool = False
    ) -> dict:
        now = datetime.now(self.timezone)
        new_post = {
            "id": max([p.get("id", 0) for p in self.postRepository.get_all()] + [0])
            + 1,
            "channel_id": "@test_channelforromanos",
            "text": context_user_data.get("new_post_text", ""),
            "image": None,
            "file_id": context_user_data.get("new_post_file_id"),
            "datetime": now.strftime(self.scheduler.time_format),
            "repeat": yearly_repeated,
            "last_posted_year": None,
            "posted": False,
            "attempts": 0,
            "last_error": None,
        }
        return new_post

    async def save_and_schedule_post(self, post: dict, update: Update):
        # JSON’a ekle
        self.postRepository.posts.append(post)
        self.postRepository.save()

        # Scheduler’ı yeniden çalıştır
        self.scheduler._schedule_cycle(reload_repo=True)

        await update.message.reply_text("Yeni paylaşım eklendi ve zamanlandı!")

    # Default commands

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [
                InlineKeyboardButton(
                    "📜 Tarihte Bugün", callback_data=CATEGORY_HISTORY_TODAY
                )
            ],
            [InlineKeyboardButton("💬 Günün Sözü", callback_data=CATEGORY_QUOTE)],
            [InlineKeyboardButton("Soru...", callback_data=CATEGORY_QUESTION)],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("Kategori seçiniz:", reply_markup=reply_markup)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Available commands:\n"
            "/start - Start the bot\n"
            "/help - Show help\n"
            "Any text message will be echoed back."
        )

    async def echo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(update.message.text)

    def run(self):
        print("[i] Starting app...")
        print("[i] Adding handlers...")

        conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.category_selected)],
            states={
                ASK_TEXT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_text)
                ],
                ASK_IMAGE: [
                    MessageHandler(filters.PHOTO, self.receive_image),
                    CommandHandler("skip", self.skip_image),
                ],
            },
            fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        )

        # self.application.add_handler(conv_handler)

        # self.application.add_handler(CommandHandler("start", self.start))
        # self.application.add_handler(CommandHandler("help", self.help_command))
        # self.application.add_handler(
        #     MessageHandler(filters.TEXT & ~filters.COMMAND, self.echo)
        # )

        print("[+] Handlers have been added.")
        print("[i] Schedulers are being run...")

        self.postRepository = PostRepository(self.posts_file)
        self.scheduler = Scheduler(self.application, self.timezone, self.postRepository)

        print("[+] Schedulers are up.")

        self.scheduler.schedule_posts()
        self.scheduler.start_rescheduler()  # 🔁 live watcher

        print("[+] Ready to keep moving!")

        self.application.run_polling()
