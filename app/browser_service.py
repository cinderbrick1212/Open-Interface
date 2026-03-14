"""Browser Service: WebSocket server for Chrome Extension communication.

This module runs a background asyncio event loop and a WebSocket server
that allows the Noclip Desktop app to communicate directly with the
Chrome extension's background script.
"""

import asyncio
import json
import logging
import threading
from typing import Any, Optional

import websockets

logger = logging.getLogger(__name__)


class BrowserService:
    """A background WebSocket server that manages the connection to Chrome."""

    def __init__(self, host: str = "localhost", port: int = 11435):
        self.host = host
        self.port = port
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        
        # Currently, we only support one active browser connection at a time
        self._active_connection: Optional[websockets.WebSocketServerProtocol] = None
        
        # Shutdown event for clean exit
        self._shutdown_event: Optional[asyncio.Event] = None
        
        # Futures for pending requests
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._request_counter = 0

    def start(self):
        """Start the WebSocket server in a background thread."""
        if self._thread and self._thread.is_alive():
            return

        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the WebSocket server."""
        if self._loop and self._shutdown_event and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._shutdown_event.set)
        if self._thread:
            self._thread.join(timeout=2)

    def is_connected(self) -> bool:
        """Return True if a browser extension is currently connected."""
        if self._active_connection is None:
            return False
            
        # For websockets >= 14
        if hasattr(self._active_connection, "state"):
            return getattr(self._active_connection.state, "name", "") == "OPEN"
        # For legacy websockets
        if hasattr(self._active_connection, "closed"):
            return not self._active_connection.closed
            
        return True

    def _run_server(self):
        """The main entry point for the background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        async def run():
            self._shutdown_event = asyncio.Event()
            async with websockets.serve(self._handle_connection, self.host, self.port):
                logger.info(f"BrowserService started on ws://{self.host}:{self.port}")
                await self._shutdown_event.wait()
        
        try:
            self._loop.run_until_complete(run())
        except Exception as e:
            logger.error(f"BrowserService error: {e}")
        finally:
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            self._loop.close()

    async def _handle_connection(self, websocket: websockets.WebSocketServerProtocol, *args, **kwargs):
        """Handle a single WebSocket connection from the Chrome extension."""
        logger.info("Browser connection accepted.")
        self._active_connection = websocket
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    self._process_message(data)
                except json.JSONDecodeError:
                    logger.error("Received malformed JSON from browser")
                except Exception as e:
                    logger.error(f"Error processing browser message: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.info("Browser connection closed.")
        finally:
            if self._active_connection == websocket:
                self._active_connection = None
                # Cancel all pending requests
                for req_id, future in self._pending_requests.items():
                    if not future.done():
                        future.set_exception(ConnectionError("Browser disconnected"))
                self._pending_requests.clear()

    def _process_message(self, data: dict):
        """Process an incoming message and resolve any pending futures."""
        req_id = data.get("id")
        if req_id and req_id in self._pending_requests:
            future = self._pending_requests.pop(req_id)
            if not future.done():
                error = data.get("error")
                if error:
                    future.set_exception(RuntimeError(error))
                else:
                    future.set_result(data.get("result"))

    async def _send_request(self, action: str, params: Optional[dict] = None, timeout: float = 5.0) -> Any:
        """Send a request to the browser and wait for a response."""
        if not self.is_connected():
            raise ConnectionError("No browser connected")

        self._request_counter += 1
        req_id = str(self._request_counter)
        
        payload = {
            "id": req_id,
            "action": action,
            "params": params or {}
        }
        
        future = self._loop.create_future()
        self._pending_requests[req_id] = future
        
        await self._active_connection.send(json.dumps(payload))
        
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_requests.pop(req_id, None)
            raise TimeoutError(f"Request {action} timed out after {timeout}s")

    # --- Sync wrapper methods for use by BrowserClient ---

    def sync_get_dom(self) -> dict:
        """Synchronously request the interactive DOM context from the active tab.
        
        Returns:
            A dictionary containing the DOM context (nodes, text, bounds).
        """
        future = asyncio.run_coroutine_threadsafe(
            self._send_request("get_dom"), 
            self._loop
        )
        return future.result(timeout=10.0)

    def sync_click_node(self, node_id: str) -> bool:
        """Synchronously request the browser to click a specific node ID."""
        future = asyncio.run_coroutine_threadsafe(
            self._send_request("click_node", {"node_id": node_id}), 
            self._loop
        )
        return future.result(timeout=5.0)
        
    def sync_type_node(self, node_id: str, text: str) -> bool:
        """Synchronously request the browser to type text into a specific node ID."""
        future = asyncio.run_coroutine_threadsafe(
            self._send_request("type_node", {"node_id": node_id, "text": text}), 
            self._loop
        )
        return future.result(timeout=5.0)
