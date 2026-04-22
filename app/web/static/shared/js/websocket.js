/* WebSocket Client Utility */

export class WebSocketClient {
  constructor(url) {
    this.ws = new WebSocket(url);
    this.listeners = {};
    this.reconnectDelay = 1000;
    this.maxReconnectDelay = 30000;
    this.reconnectAttempts = 0;
    
    this.ws.onopen = () => {
      console.log(`WebSocket connected to ${url}`);
      this.reconnectAttempts = 0;
      this.reconnectDelay = 1000;
    };
    
    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        const messageType = message.type;
        const messageData = message.data;
        
        if (this.listeners[messageType]) {
          this.listeners[messageType].forEach(cb => cb(messageData));
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    this.ws.onclose = () => {
      console.log('WebSocket connection closed');
      this.attemptReconnect(url);
    };
  }
  
  on(type, callback) {
    if (!this.listeners[type]) {
      this.listeners[type] = [];
    }
    this.listeners[type].push(callback);
  }
  
  off(type, callback) {
    if (this.listeners[type]) {
      this.listeners[type] = this.listeners[type].filter(cb => cb !== callback);
    }
  }
  
  send(data) {
    if (this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.warn('WebSocket is not open. Cannot send message.');
    }
  }
  
  close() {
    this.ws.close();
  }
  
  attemptReconnect(url) {
    if (this.reconnectAttempts >= 10) {
      console.log('Max reconnection attempts reached. Giving up.');
      return;
    }
    
    this.reconnectAttempts++;
    const delay = Math.min(this.reconnectDelay, this.maxReconnectDelay);
    
    console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);
    
    setTimeout(() => {
      this.ws = new WebSocket(url);
      this.setupWebSocketHandlers(url);
    }, delay);
    
    this.reconnectDelay *= 2;
  }
  
  setupWebSocketHandlers(url) {
    this.ws.onopen = () => {
      console.log(`WebSocket reconnected to ${url}`);
      this.reconnectAttempts = 0;
      this.reconnectDelay = 1000;
    };
    
    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        const messageType = message.type;
        const messageData = message.data;
        
        if (this.listeners[messageType]) {
          this.listeners[messageType].forEach(cb => cb(messageData));
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    this.ws.onclose = () => {
      console.log('WebSocket connection closed');
      this.attemptReconnect(url);
    };
  }
}
