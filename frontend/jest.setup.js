import '@testing-library/jest-dom'

// Mock IntersectionObserver
class IntersectionObserver {
  observe() { return null; }
  disconnect() { return null; }
  unobserve() { return null; }
}
window.IntersectionObserver = IntersectionObserver;

// Mock ResizeObserver
class ResizeObserver {
  observe() { return null; }
  disconnect() { return null; }
  unobserve() { return null; }
}
window.ResizeObserver = ResizeObserver;

// Mock EventSource
class EventSource {
    constructor(url) {
        this.url = url;
        this.onmessage = null;
        this.onopen = null;
        this.onerror = null;
        this.listeners = {};
    }

    addEventListener(event, callback) {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        this.listeners[event].push(callback);
    }

    removeEventListener(event, callback) {
        if (this.listeners[event]) {
            this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
        }
    }

    dispatchEvent(event) {
        if (this.listeners[event.type]) {
            this.listeners[event.type].forEach(callback => callback(event));
        }
        if (event.type === 'message' && this.onmessage) {
            this.onmessage(event);
        }
    }
    
    close() {
        // Mock close
    }
}
window.EventSource = EventSource;
