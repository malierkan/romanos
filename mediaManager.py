from telegram.error import TelegramError


class MediaManager:
    def __init__(self, bot):
        self.bot = bot

    async def send_photo(self, chat_id: str, post: dict):
        text = post.get("text", "")
        file_id = post.get("file_id")
        image = post.get("image")

        if file_id:
            try:
                return await self.bot.send_photo(
                    chat_id=chat_id,
                    photo=file_id,
                    caption=text
                )
            except TelegramError:
                post["file_id"] = None

        with open(image, "rb") as img:
            msg = await self.bot.send_photo(
                chat_id=chat_id,
                photo=img,
                caption=text
            )

        post["file_id"] = msg.photo[-1].file_id
        return msg
