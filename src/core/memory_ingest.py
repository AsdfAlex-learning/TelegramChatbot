from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from abc import ABC, abstractmethod

class MemorySource(Enum):
    """
    Enumeration of valid memory sources.
    
    Ensures that the origin of every memory entry is traceable.
    """
    TELEGRAM = "telegram"
    LIVE2D = "live2d"
    SYSTEM_EVENT = "system"

@dataclass
class MemoryPayload:
    """
    Data payload for injecting a new long-term memory summary.
    
    This structure ensures that only summarized, structured data enters the memory system,
    rather than raw chat logs.
    
    Attributes:
        summary_text (str): The LLM-generated summary text.
        keywords (List[str]): Key tags extracted from the interaction.
        importance_score (float): A weight from 0.0 to 1.0 indicating memory retention priority.
        related_context_ids (List[str/int]): IDs of the original messages/interactions that generated this summary.
                                         Used for lineage and debugging.
        source_platform (MemorySource): The platform where the interaction originated.
        timestamp (datetime): The time when the memory was formed (usually now, or session end time).
    """
    summary_text: str
    keywords: List[str]
    importance_score: float
    related_context_ids: List[str]  # Or int, depending on ID type
    source_platform: MemorySource
    timestamp: datetime

class MemoryManagerInterface(ABC):
    """
    Abstract Interface for the Memory Manager.
    
    Defines the contract for interacting with the long-term memory store.
    This interface ensures that external modules (like Live2D) or internal agents
    adhere to the 'Ingest' protocol rather than writing directly to the DB.
    """

    @abstractmethod
    def ingest_summary(self, user_id: int, payload: MemoryPayload) -> bool:
        """
        The standard entry point for injecting long-term memory.
        
        This method acts as a firewall for the memory database. It is responsible for:
        1. Validating the payload (e.g., text is not empty, score is within range).
        2. Performing de-duplication (e.g., vector similarity check).
        3. Persisting the data to Vector Store and SQL Database.
        4. Triggering any necessary cleanup or decay tasks.
        
        Constraints:
            - ONLY to be called by Core internal services (SummaryAgent, BackgroundWorker).
            - External clients (Live2D) MUST NOT call this directly.
        
        Args:
            user_id (int): The ID of the user who owns this memory.
            payload (MemoryPayload): The structured memory data to ingest.
            
        Returns:
            bool: True if ingestion was successful, False otherwise.
        """
        pass
