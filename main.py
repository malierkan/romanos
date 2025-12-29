import os
from telegramBot import TelegramBot
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

load_dotenv()


def main():
    print("[+] We're up!")
    print("[i] Getting environment variables...")
    
    token = os.getenv("TG_TOKEN")
    timezone = ZoneInfo(os.getenv("TIMEZONE", "Europe/Istanbul"))
    posts_file = os.getenv("POSTS_FILE", "/storage/posts.json")

    print("[+] We've got enought variables, ready to run bot.")

    bot = TelegramBot(token, timezone, posts_file)
    bot.run()


if __name__ == "__main__":
    main()
