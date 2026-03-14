// Background Service Worker for Noclip Extension

const WS_URL = "ws://localhost:11435";
let socket = null;
let isConnected = false;
let reconnectTimer = null;

function connect() {
  console.log(`[Noclip] Attempting connection to ${WS_URL}...`);
  socket = new WebSocket(WS_URL);

  socket.onopen = () => {
    console.log("[Noclip] Connected to Desktop App");
    isConnected = true;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };

  socket.onmessage = async (event) => {
    try {
      const data = JSON.parse(event.data);
      console.log(`[Noclip] Received command: ${data.action}`);
      await handleCommand(data);
    } catch (e) {
      console.error("[Noclip] Failed to parse message", e);
    }
  };

  socket.onclose = () => {
    console.log("[Noclip] Disconnected from Desktop App");
    isConnected = false;
    socket = null;
    // Auto-reconnect every 3 seconds
    reconnectTimer = setTimeout(connect, 3000);
  };

  socket.onerror = (error) => {
    console.warn("[Noclip] WebSocket error");
    if (socket) socket.close();
  };
}

// Initial connection
connect();

// Provide status to the popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "get_status") {
    sendResponse({ connected: isConnected });
  }
});

/**
 * Handle incoming commands from the Python WebSocket server.
 */
async function handleCommand(payload) {
  const { id, action, params } = payload;
  
  // Find the active tab to execute the command on
  const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  
  if (!activeTab || activeTab.url.startsWith("chrome://")) {
    sendResponse(id, { error: "No active valid tab found" });
    return;
  }

  try {
    // Forward the action to the content script in the active tab
    const result = await chrome.tabs.sendMessage(activeTab.id, { action, params });
    sendResponse(id, { result });
  } catch (e) {
    if (e.message.includes("Receiving end does not exist")) {
      sendResponse(id, { error: "Content script not injected - reload the page" });
    } else {
      sendResponse(id, { error: e.message });
    }
  }
}

/**
 * Send a JSON response back to the Python WebSocket server.
 */
function sendResponse(id, data) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  const payload = JSON.stringify({ id, ...data });
  socket.send(payload);
}
