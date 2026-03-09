/**
 * Electron preload script.
 *
 * Runs in a sandboxed context before any web page code.  Currently a
 * no-op placeholder — add IPC bridges here if the renderer needs to
 * communicate with the main process in the future.
 */

const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('openInterface', {
  platform: process.platform,
});
