import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional

from bot.utils import log


class CarouselSlide:
    def __init__(self, slide_number: int, image_url: str, caption: str):
        self.slide_number = slide_number
        self.image_url = image_url
        self.caption = caption
        self.container_id: Optional[str] = None

    def to_dict(self):
        return {
            "slide_number": self.slide_number,
            "image_url": self.image_url,
            "caption": self.caption,
            "container_id": self.container_id,
        }


class CarouselSession:
    def __init__(self, user_number: str, topic: str):
        self.user_number = user_number
        self.topic = topic
        self.slides: list[CarouselSlide] = []
        self.main_caption: str = ""
        self.call_to_action: str = ""
        self.carousel_container_id: Optional[str] = None
        self.status: str = "generating"  # generating | ready | published | rejected
        self.created_at: datetime = datetime.utcnow()
        self.updated_at: datetime = datetime.utcnow()

    def to_dict(self):
        return {
            "user_number": self.user_number,
            "topic": self.topic,
            "slides": [s.to_dict() for s in self.slides],
            "main_caption": self.main_caption,
            "call_to_action": self.call_to_action,
            "carousel_container_id": self.carousel_container_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class SessionStore:
    def __init__(self, backup_path: Optional[Path] = None):
        self._lock = threading.Lock()
        self._sessions: dict[str, CarouselSession] = {}  # user_number -> session
        self._backup_path = backup_path

    def get_or_create(self, user_number: str, topic: str) -> CarouselSession:
        with self._lock:
            if user_number not in self._sessions:
                self._sessions[user_number] = CarouselSession(user_number, topic)
                log.info("session_created", user=user_number, topic=topic)
            return self._sessions[user_number]

    def get(self, user_number: str) -> Optional[CarouselSession]:
        with self._lock:
            return self._sessions.get(user_number)

    def get_latest(self) -> Optional[CarouselSession]:
        with self._lock:
            if not self._sessions:
                return None
            return max(self._sessions.values(), key=lambda s: s.updated_at)

    def update(self, session: CarouselSession):
        with self._lock:
            session.updated_at = datetime.utcnow()
            self._sessions[session.user_number] = session
            self._auto_backup()

    def remove(self, user_number: str):
        with self._lock:
            self._sessions.pop(user_number, None)

    def _auto_backup(self):
        if self._backup_path:
            try:
                data = {k: v.to_dict() for k, v in self._sessions.items()}
                self._backup_path.write_text(json.dumps(data, indent=2))
            except Exception as e:
                log.warning("session_backup_failed", error=str(e))


sessions = SessionStore()
