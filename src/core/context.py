from typing import List, Dict, Optional

class ConversationContext:
    """
    Manages short-term memory (conversation history) with structure:
    - Summary (abstract of previous context)
    - Recent Messages (verbatim recent history)
    """
    def __init__(self, max_history: int = 20):
        self.history: List[Dict[str, str]] = []
        self.summary: str = "暂无前情提要"
        self.max_history = max_history

    def add_message(self, role: str, content: str):
        """Adds a message to the history."""
        self.history.append({"role": role, "content": content})
        # Maintain fixed window size for now
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def update_summary(self, new_summary: str):
        """Updates the conversation summary."""
        if new_summary:
            self.summary = new_summary

    def format(self, exclude_last_n: int = 0) -> str:
        """Formats the context into a string for the prompt."""
        lines = []
        
        # 1. Summary Section
        lines.append("【前情提要】")
        lines.append(self.summary)
        lines.append("") # Empty line
        
        # 2. Recent Conversation Section
        lines.append("【近期对话】")
        
        msgs_to_show = self.history[:-exclude_last_n] if exclude_last_n > 0 else self.history
        
        if not msgs_to_show:
            lines.append("（暂无近期对话）")
        else:
            for msg in msgs_to_show:
                role_name = "User" if msg["role"] == "user" else "AI"
                lines.append(f"{role_name}: {msg['content']}")
        
        return "\n".join(lines)

    def get_raw_history(self) -> List[Dict[str, str]]:
        return self.history
