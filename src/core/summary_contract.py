from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any
import time

# Import dependencies
# Ensure these modules exist or are created. 
# Based on previous context, they should be in src.core.
from src.core.memory_ingest import MemorySource
from src.core.context_snapshot import ContextSnapshot

class SummaryTriggerReason(Enum):
    """
    The semantic reason why a summary generation is requested or considered.
    """
    SESSION_END = "session_end"          # Explicit session end (e.g. user closed app)
    USER_IDLE = "user_idle"              # User inactive for threshold time
    CONTEXT_LIMIT = "context_limit"      # Short-term context is full
    TOPIC_CHANGE = "topic_change"        # Detected a shift in topic (Advanced)
    PERIODIC = "periodic"                # Routine check (e.g. every N turns)
    MANUAL = "manual"                    # Admin or debug force trigger

@dataclass
class SummaryHint:
    """
    A suggestion signal sent from Satellites (e.g., Live2D Client) or Internal Monitors to the Core.
    
    This object encapsulates the "Intent" to summarize, but does not guarantee execution.
    The Core uses this hint as one input to the ISummaryTriggerPolicy.
    
    Attributes:
        user_id (int): The ID of the user.
        source (MemorySource): The origin of this hint (e.g., MemorySource.LIVE2D).
        reason (SummaryTriggerReason): Why the client thinks we should summarize.
        timestamp (float): When the hint was generated.
        payload (Dict[str, Any]): Optional context data (e.g., {"idle_seconds": 600}).
    """
    user_id: int
    source: MemorySource
    reason: SummaryTriggerReason
    timestamp: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)

class ISummaryTriggerPolicy(ABC):
    """
    Strategy Interface for determining if a Long-Term Memory Summary should be generated.
    
    This interface decouples the "Decision Logic" (When to summarize) from the 
    "Execution Logic" (How to summarize) and the "Trigger Source" (Who asked).
    """

    @abstractmethod
    def should_trigger(self, snapshot: ContextSnapshot, hint: Optional[SummaryHint] = None) -> bool:
        """
        Evaluate the current state and optional hint to decide if summarization is needed.
        
        Logic Examples:
            - If hint.reason == SESSION_END: return True
            - If snapshot.state.interaction_depth > 20: return True
            - If hint.reason == USER_IDLE and snapshot.state.interaction_depth < 3: return False (Too short to summarize)
            
        Args:
            snapshot (ContextSnapshot): The current read-only snapshot of the user's context.
                                        Used to check interaction depth, mood, recent messages, etc.
            hint (Optional[SummaryHint]): An optional external suggestion. 
                                          If None, implies a routine internal check.
        
        Returns:
            bool: True if the SummaryAgent should proceed to generate a summary.
        """
        pass
