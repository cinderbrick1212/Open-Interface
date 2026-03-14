document.addEventListener('DOMContentLoaded', () => {
  const statusEl = document.getElementById('status');
  
  // Ask background script for current WebSocket status
  chrome.runtime.sendMessage({ action: "get_status" }, (response) => {
    if (response && response.connected) {
      statusEl.textContent = "Connected to Client";
      statusEl.className = "status connected";
    } else {
      statusEl.textContent = "Disconnected";
      statusEl.className = "status disconnected";
    }
  });
});
