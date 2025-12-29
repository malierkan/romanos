from datetime import datetime
from zoneinfo import ZoneInfo

from telegram.ext import Application, ContextTypes
from telegram.error import RetryAfter, TimedOut, TelegramError

from mediaManager import MediaManager
from postRepository import PostRepository


MAX_RETRIES = 3
RETRY_DELAY = 60


class Scheduler:
    def __init__(self, app: Application, timezone: ZoneInfo, repo: PostRepository):
        self.app = app
        self.repo = repo
        self.timezone = timezone
        self.UTC = ZoneInfo("UTC")
        self.time_format = "%d.%m.%Y %H:%M"

        self.media = MediaManager(app.bot)

    # ---------- Job identity ----------

    def job_name(self, post_id: int) -> str:
        return f"post_{post_id}"

    def remove_existing_job(self, post_id: int):
        jobs = self.app.job_queue.get_jobs_by_name(self.job_name(post_id))
        for job in jobs:
            job.schedule_removal()

    def add_to_queue(self, delay: int, post: dict):
        post_id = post["id"]

        self.remove_existing_job(post_id)

        self.app.job_queue.run_once(
            self.publish_post, when=delay, data=post, name=self.job_name(post_id)
        )

    # ---------- Core ----------

    async def publish_post(self, context: ContextTypes.DEFAULT_TYPE):
        post = context.job.data
        post_id = post["id"]
        bot = context.bot

        print(f"[i] post_{post_id} is being published...")

        try:
            if post.get("image"):
                await self.media.send_photo(post["channel_id"], post)
            else:
                await bot.send_message(
                    chat_id=post["channel_id"], text=post.get("text", "")
                )

            self.repo.mark_posted(post, datetime.now(self.timezone).year)
            print(f"[+] post_{post_id} has been published.")

        except RetryAfter as e:
            print("[!] An error occured while publishing the post:")
            print(str(e))
            self.repo.increment_attempts(post_id, str(e))
            self.add_to_queue(e.retry_after, post)

        except (TimedOut, TelegramError) as e:
            print("[!] An error occured while publishing the post:")
            print(str(e))
            self.repo.increment_attempts(post_id, str(e))
            self.add_to_queue(RETRY_DELAY, post)

        except Exception as e:
            print("[!] An error occured while publishing the post:")
            print(str(e))
            self.repo.increment_attempts(post_id, f"Unhandled: {e}")

    # ---------- Core scheduling logic (single source of truth) ----------

    def _schedule_cycle(self, reload_repo: bool = False):
        print("[i] Scheduling posts...")

        if reload_repo:
            print("[i] Reloading repository...")
            self.repo.load()
            print("[+] repository has been reloaded.")

        now_local = datetime.now(self.timezone)
        now_utc = now_local.astimezone(self.UTC)

        for post, target_local in self.repo.get_schedulable_posts(
            now_local, self.time_format, self.timezone
        ):
            delay = max(
                (target_local.astimezone(self.UTC) - now_utc).total_seconds(),
                1,
            )
            self.add_to_queue(delay, post)

        print("[+] Posts scheduled.")

    # ---------- Initial scheduling ----------

    def schedule_posts(self):
        self._schedule_cycle(reload_repo=False)

    # ---------- Re-scheduler ----------

    def start_rescheduler(self):
        print("[i] Starting re-scheduler...")

        self.app.job_queue.run_repeating(
            self.reschedule,
            interval=60,  # 1 minute
            first=5,
            name="rescheduler",
        )

        print("[+] Re-scheduler started.")

    async def reschedule(self, context: ContextTypes.DEFAULT_TYPE):
        self._schedule_cycle(reload_repo=True)
