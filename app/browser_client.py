"""Client wrapper for interacting with the browser extension.

This provides a clean, synchronous interface for the LangGraph agent
to talk to the background WebSocket server.
"""

from typing import Optional
from browser_service import BrowserService


class BrowserClient:
    """Synchronous client to communicate with the browser extension via the BrowserService."""

    def __init__(self, service: BrowserService):
        self._service = service

    def is_available(self) -> bool:
        """Check if a browser extension is currently connected and active."""
        return self._service.is_connected()

    def get_dom_context(self) -> Optional[dict]:
        """Fetch the interactive DOM tree from the active browser tab.
        
        Returns:
            A dictionary containing 'nodes' (list of interactive elements) and 'url',
            or None if the browser is unavailable or an error occurs.
        """
        if not self.is_available():
            return None
            
        try:
            return self._service.sync_get_dom()
        except Exception:
            return None

    def click_dom_id(self, node_id: str) -> bool:
        """Click an element by its data-noclip-id in the active tab."""
        if not self.is_available():
            return False
            
        try:
            return self._service.sync_click_node(node_id)
        except Exception:
            return False

    def type_dom_id(self, node_id: str, text: str) -> bool:
        """Type text into an element by its data-noclip-id in the active tab."""
        if not self.is_available():
            return False
            
        try:
            return self._service.sync_type_node(node_id, text)
        except Exception:
            return False
