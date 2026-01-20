import threading
import logging
from typing import Set
from enum import Enum, auto

class AccessResult(Enum):
    ALLOWED = auto()
    DENIED_PRIVATE = auto()
    DENIED_INACTIVE = auto()

class SessionController:
    def __init__(self, owner_id: int, private_mode_default: bool):
        self.owner_id = owner_id
        self.private_mode_enabled = private_mode_default
        self.active_chats: Set[int] = set()
        self.lock = threading.Lock()
        logging.info(f"[SessionController] Initialized with Owner ID: {self.owner_id}, Private Mode: {self.private_mode_enabled}")

    def can_start_session(self, user_id: int) -> bool:
        if self.private_mode_enabled and user_id != self.owner_id:
            return False
        return True

    def can_continue_session(self, user_id: int) -> AccessResult:
        if self.private_mode_enabled and user_id != self.owner_id:
            return AccessResult.DENIED_PRIVATE
        if user_id not in self.active_chats:
            return AccessResult.DENIED_INACTIVE
        return AccessResult.ALLOWED

    def start_session(self, user_id: int) -> bool:
        """
        Attempt to start a session for a user.
        Returns True if successful, False if permission denied.
        """
        if not self.can_start_session(user_id):
            logging.warning(f"[Session] Start denied for {user_id} (Private Mode)")
            return False
            
        with self.lock:
            self.active_chats.add(user_id)
            logging.info(f"[Session] Started session for {user_id}")
            return True

    def stop_session(self, user_id: int):
        """Stop a user's session."""
        with self.lock:
            self.active_chats.discard(user_id)
            logging.info(f"[Session] Stopped session for {user_id}")

    def is_session_active(self, user_id: int) -> bool:
        """Check if a user has an active session."""
        with self.lock:
            return user_id in self.active_chats
