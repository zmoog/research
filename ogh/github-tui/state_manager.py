"""Manages persistent state for tracking when notifications were last viewed."""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class StateManager:
    """Manages the state of viewed notifications."""

    def __init__(self, state_file: str = ".state.json"):
        self.state_file = Path(state_file)
        self.state: Dict[str, str] = self._load_state()

    def _load_state(self) -> Dict[str, str]:
        """Load state from disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_state(self) -> None:
        """Save state to disk."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except IOError as e:
            print(f"Error saving state: {e}")

    def get_last_viewed(self, notification_id: str) -> Optional[datetime]:
        """Get the last time a notification was viewed."""
        timestamp = self.state.get(notification_id)
        if timestamp:
            return datetime.fromisoformat(timestamp)
        return None

    def mark_viewed(self, notification_id: str) -> None:
        """Mark a notification as viewed at the current time."""
        self.state[notification_id] = datetime.now().isoformat()
        self._save_state()

    def clear(self) -> None:
        """Clear all state."""
        self.state = {}
        self._save_state()
