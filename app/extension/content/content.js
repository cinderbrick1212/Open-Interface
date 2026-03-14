// Content script injected into every valid webpage.
// Traverses the DOM, builds a representation, and executes actions.

let elementMap = new Map(); // Maps string ID to DOM Node
let nextId = 0;             // Incremental ID generator

/**
 * Check if an element is interactable (clickable or typeable).
 */
function isInteractable(el) {
  const tag = el.tagName.toLowerCase();
  
  if (tag === 'button' || tag === 'a' || tag === 'input' || tag === 'select' || tag === 'textarea') {
    return true;
  }
  
  if (el.getAttribute('role') === 'button' || el.getAttribute('role') === 'link') {
    return true;
  }
  
  const computedStyle = window.getComputedStyle(el);
  if (computedStyle.cursor === 'pointer' && el.textContent.trim().length > 0) {
    return true;
  }
  
  return false;
}

/**
 * Check if the element is actually visible on screen.
 */
function isVisible(el, rect) {
  const style = window.getComputedStyle(el);
  if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
    return false;
  }
  
  if (rect.width === 0 || rect.height === 0) {
    return false;
  }
  
  // Is within viewport?
  if (rect.bottom < 0 || rect.right < 0 || rect.top > window.innerHeight || rect.left > window.innerWidth) {
    return false;
  }
  
  return true;
}

/**
 * Traverse the DOM and extract all interactive elements.
 * Assigns a unique `data-noclip-id` attribute to each element found.
 */
function getDOMContext() {
  // Reset maps to clear old references
  elementMap.clear();
  nextId = 0;
  
  const resultNodes = [];
  const elements = document.querySelectorAll('*');
  
  for (const el of elements) {
    if (isInteractable(el)) {
      const rect = el.getBoundingClientRect();
      
      if (isVisible(el, rect)) {
        // Tag the element so we can find it later
        const elId = `node-${nextId++}`;
        el.setAttribute('data-noclip-id', elId);
        elementMap.set(elId, el);
        
        let text = el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || el.value || '';
        text = text.trim().substring(0, 50); // truncated
        
        // Highlight logic (temporarily box the element to show it was parsed)
        el.style.outline = "2px solid rgba(255, 0, 0, 0.4)";
        el.style.outlineOffset = "-2px";
        
        resultNodes.push({
          id: elId,
          tag: el.tagName.toLowerCase(),
          text: text,
          bounds: {
            x: Math.round(rect.left),
            y: Math.round(rect.top),
            w: Math.round(rect.width),
            h: Math.round(rect.height)
          }
        });
      }
    }
  }
  
  // Clean up highlighted outlines after 1 second so it doesn't stay permanently
  setTimeout(() => {
    elementMap.forEach(el => {
      if (el.style.outline === "2px solid rgba(255, 0, 0, 0.4)") {
        el.style.outline = "";
        el.style.outlineOffset = "";
      }
    });
  }, 1000);

  return {
    url: window.location.href,
    title: document.title,
    nodes: resultNodes
  };
}

/**
 * Execute a click on a specific element.
 */
function clickDomId(id) {
  const el = elementMap.get(id) || document.querySelector(`[data-noclip-id="${id}"]`);
  if (!el) {
    throw new Error(`Element with id ${id} not found.`);
  }
  el.click();
  return true;
}

/**
 * Type text into an input field.
 */
function typeDomId(id, text) {
  const el = elementMap.get(id) || document.querySelector(`[data-noclip-id="${id}"]`);
  if (!el) {
    throw new Error(`Element with id ${id} not found.`);
  }
  
  el.focus();
  
  // Use React-friendly native event dispatch
  const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  if (nativeInputValueSetter) {
    nativeInputValueSetter.call(el, text);
  } else {
    el.value = text;
  }
  
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
  
  return true;
}

// Start listener for messages from Background Script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  try {
    switch (request.action) {
      case "get_dom":
        sendResponse(getDOMContext());
        break;
      case "click_node":
        sendResponse(clickDomId(request.params.node_id));
        break;
      case "type_node":
        sendResponse(typeDomId(request.params.node_id, request.params.text));
        break;
      default:
        throw new Error(`Unknown action: ${request.action}`);
    }
  } catch (e) {
    console.error(`[Noclip Content] Error executing ${request.action}:`, e);
    // Send standard error object
    sendResponse({ error: e.message });
  }
});
