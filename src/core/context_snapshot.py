from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import uuid
import time
import json

@dataclass
class SnapshotMeta:
    """
    Metadata for the context snapshot.
    
    Attributes:
        snapshot_id (str): Unique identifier for this snapshot (UUID v4).
        timestamp (float): Unix timestamp when the snapshot was generated.
        version (str): Schema version of the snapshot structure.
    """
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    version: str = "1.0"

@dataclass
class SessionInfo:
    """
    Session information for the current user interaction.
    
    Attributes:
        user_id (int): The unique identifier of the user.
        active_session_id (str): The unique identifier of the current active session.
        is_private_mode (bool): Whether the session is in private mode (Owner only).
    """
    user_id: int
    active_session_id: str
    is_private_mode: bool

@dataclass
class InteractionState:
    """
    Current state of the interaction.
    
    Attributes:
        current_mood (str): The current emotional state of the AI (e.g., "happy", "curious").
                            Derived from LLM analysis or rule-based inference.
        interaction_depth (int): The number of turns in the current session.
        last_active_component (str): The component that triggered the last update (e.g., "telegram", "live2d").
    """
    current_mood: str
    interaction_depth: int
    last_active_component: str

@dataclass
class ShortTermMessage:
    """
    A single message in the short-term context window.
    
    Attributes:
        role (str): The role of the message sender ("user", "assistant", "system").
        content (str): The text content of the message.
        timestamp (float): Unix timestamp of the message.
        source (Optional[str]): The source platform of the message (e.g., "live2d", "telegram").
        mood_tag (Optional[str]): The mood associated with this message (for assistant messages).
    """
    role: str
    content: str
    timestamp: float
    source: Optional[str] = None
    mood_tag: Optional[str] = None

@dataclass
class ContextSnapshot:
    """
    A read-only snapshot of the current context state.
    
    This object represents a point-in-time view of the conversation, suitable for
    external clients (like Live2D) to render UI or determine animation logic.
    It is immutable and does not expose internal implementation details of the Core.
    """
    meta: SnapshotMeta
    session: SessionInfo
    state: InteractionState
    short_term_context: List[ShortTermMessage]

    def to_json(self) -> str:
        """
        Serialize the snapshot to a JSON string.
        """
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContextSnapshot':
        """
        Deserialize a dictionary into a ContextSnapshot object.
        """
        # Note: In a real implementation, this would need robust error handling and type conversion.
        # This is a simplified structural representation.
        meta = SnapshotMeta(**data.get('meta', {}))
        session = SessionInfo(**data.get('session', {}))
        state = InteractionState(**data.get('state', {}))
        
        context_data = data.get('short_term_context', [])
        short_term_context = [ShortTermMessage(**msg) for msg in context_data]
        
        return cls(
            meta=meta,
            session=session,
            state=state,
            short_term_context=short_term_context
        )

class SnapshotService:
    """
    Service responsible for generating ContextSnapshots.
    
    This service resides within the Core and has access to the internal ContextManager.
    It acts as a factory for Snapshots.
    """
    
    def generate_snapshot(self, user_id: int) -> ContextSnapshot:
        """
        Generate a new snapshot for the given user.
        
        Lifecycle:
            - Should be called after every Core interaction cycle (User Input -> LLM -> Update).
            - Should reflect the latest committed state.
        
        Args:
            user_id (int): The user ID to generate the snapshot for.
            
        Returns:
            ContextSnapshot: The fresh snapshot object.
        """
        raise NotImplementedError("This method should be implemented by the concrete Core service.")
