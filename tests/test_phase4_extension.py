"""Tests for the BrowserService WebSocket server."""

import asyncio
import json
import logging
import os
import sys

import pytest
import websockets

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
from browser_service import BrowserService


@pytest.fixture
def browser_service():
    """Fixture to start and cleanly stop a test BrowserService."""
    service = BrowserService(port=11436)  # Use a different port for tests
    service.start()
    yield service
    service.stop()


@pytest.mark.asyncio
async def test_websocket_connection_lifecycle(browser_service):
    """Test that a mock extension can connect and disconnect."""
    assert not browser_service.is_connected()
    
    # Needs a brief moment for the thread to start the loop
    await asyncio.sleep(0.1)

    uri = f"ws://{browser_service.host}:{browser_service.port}"
    async with websockets.connect(uri) as websocket:
        await asyncio.sleep(0.1)
        assert browser_service.is_connected()

    # Wait for the server to register the disconnect
    await asyncio.sleep(0.1)
    assert not browser_service.is_connected()


@pytest.mark.asyncio
async def test_get_dom_request(browser_service):
    """Test that the server can route a get_dom request to the mock extension."""
    await asyncio.sleep(0.1)

    uri = f"ws://{browser_service.host}:{browser_service.port}"
    
    # Start the mock extension in a background task
    async def mock_extension():
        async with websockets.connect(uri) as ws:
            # Wait for a command from the server
            msg = await ws.recv()
            data = json.loads(msg)
            
            assert data["action"] == "get_dom"
            
            # Send a fake DOM back
            response = {
                "id": data["id"],
                "result": {
                    "url": "https://example.com",
                    "nodes": [{"id": "node-0", "tag": "button", "text": "Submit"}]
                }
            }
            await ws.send(json.dumps(response))
            # Keep alive momentarily
            await asyncio.sleep(0.5)

    extension_task = asyncio.create_task(mock_extension())
    await asyncio.sleep(0.2)  # Wait for connect
    
    assert browser_service.is_connected()
    
    # This must be run in a thread because sync_get_dom uses asyncio.run_coroutine_threadsafe
    result = await asyncio.to_thread(browser_service.sync_get_dom)
        
    assert result["url"] == "https://example.com"
    assert len(result["nodes"]) == 1
    assert result["nodes"][0]["text"] == "Submit"
    
    extension_task.cancel()


@pytest.mark.asyncio
async def test_timeout_handling(browser_service):
    """Test that requests time out if the extension doesn't respond."""
    await asyncio.sleep(0.1)

    uri = f"ws://{browser_service.host}:{browser_service.port}"
    
    async def silent_extension():
        async with websockets.connect(uri) as ws:
            await ws.recv()  # Block and ignore the request
            await asyncio.sleep(1.0)

    extension_task = asyncio.create_task(silent_extension())
    await asyncio.sleep(0.2)
    
    def run_failing_coro():
        coro = browser_service._send_request("click_node", {"node_id": "test"}, timeout=0.5)
        future = asyncio.run_coroutine_threadsafe(coro, browser_service._loop)
        return future.result(timeout=2)

    with pytest.raises(TimeoutError, match="timed out after 0.5s"):
        await asyncio.to_thread(run_failing_coro)

    extension_task.cancel()
