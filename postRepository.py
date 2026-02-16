import json
import threading

from datetime import datetime
from pathlib import Path
from typing import List, Optional


GRACE_SECONDS = 1800  # 30 mins


class PostRepository:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self._lock = threading.Lock()
        self.posts: List[dict] = []

        self.load()

    # ---------- Core I/O ----------

    def load(self):
        if not self.file_path.exists():
            self.posts = []
            return

        with self._lock, open(self.file_path, "r", encoding="utf-8") as f:
            self.posts = json.load(f)

    def save(self):
        with self._lock, open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.posts, f, indent=2, ensure_ascii=False)

    # ---------- Read ----------

    def get_all(self) -> List[dict]:
        return self.posts

    def get_by_id(self, post_id: int) -> Optional[dict]:
        return next((p for p in self.posts if p.get("id") == post_id), None)

    # -------------------------
    # PUBLIC API
    # -------------------------

    def get_schedulable_posts(self, now_local: datetime, time_format: str, timezone):
        result = []

        for post in self.posts:
            target_dt = self._get_target_datetime(
                post, now_local, time_format, timezone
            )

            if not target_dt:
                continue

            result.append((post, target_dt))

        return result

    def mark_posted(self, post: dict, year: int):
        if post.get("repeat"):
            post["last_posted_year"] = year
        else:
            post["posted"] = True

        post["last_error"] = None
        self.save()

    def increment_attempts(self, post_id: int, error: str):
        post = self.get_by_id(post_id)
        if not post:
            return

        post["attempts"] = post.get("attempts", 0) + 1
        post["last_error"] = error

        if post["attempts"] > 3:
            post["failed"] = True

        self.save()

    # -------------------------
    # INTERNAL LOGIC
    # -------------------------

    def _get_target_datetime(
        self, post: dict, now_local: datetime, time_format: str, timezone
    ):
        repeat = post.get("repeat", False)

        if not repeat and post.get("posted"):
            return None

        # Check for leap year or invalid datetime
        try:
            local_dt = datetime.strptime(post["datetime"], time_format).replace(
                tzinfo=timezone
            )
            print(local_dt)
        except ValueError as e:
            print(f"[!] Error: {str(e)}")
            return None

        if repeat:
            # if this post is already posted this year
            if post.get("last_posted_year") == now_local.year:
                return None

            try:
                local_dt = local_dt.replace(year=now_local.year)

            except ValueError as e:
                print(f"[!] Error: {str(e)}")
                return None

            delta_seconds = (now_local - local_dt).total_seconds()

            # ❌ if we are too late pass it
            if delta_seconds > GRACE_SECONDS:
                return None

            # ✅ if we still have time to post go ahead
            if delta_seconds >= 0:
                return local_dt

        # if the time did not come yet pass it
        if local_dt < now_local:
            return None

        return local_dt
