// WebSocket Service for Real-Time Updates
// Handles connections, reconnection, message queuing, and subscriptions

import { enhancedApiClient } from './enhancedClient';
import { resolveBackendWebSocketUrl } from './origin';

// WebSocket connection states
export enum WebSocketState {
  CONNECTING = 'CONNECTING',
  CONNECTED = 'CONNECTED',
  DISCONNECTED = 'DISCONNECTED',
  RECONNECTING = 'RECONNECTING',
  ERROR = 'ERROR',
}

// Message types
export enum MessageType {
  BOT_UPDATE = 'BOT_UPDATE',
  TRADE_UPDATE = 'TRADE_UPDATE',
  POSITION_UPDATE = 'POSITION_UPDATE',
  ALERT = 'ALERT',
  BACKTEST_PROGRESS = 'BACKTEST_PROGRESS',
  SYSTEM_STATUS = 'SYSTEM_STATUS',
  HEARTBEAT = 'HEARTBEAT',
}

// WebSocket message interface
export interface WebSocketMessage {
  type: MessageType;
  payload: unknown;
  timestamp: string;
  id?: string;
}

// Subscription interface
export interface Subscription {
  id: string;
  channel: string;
  callback: (message: WebSocketMessage) => void;
  filter?: (message: WebSocketMessage) => boolean;
}

// Connection configuration
interface WebSocketConfig {
  url: string;
  protocols?: string[];
  reconnectInterval: number;
  maxReconnectAttempts: number;
  heartbeatInterval: number;
  queueMaxSize: number;
  debug: boolean;
}

/**
 * Advanced WebSocket Manager
 * Features:
 * - Automatic reconnection with exponential backoff
 * - Message queuing when disconnected
 * - Subscription management
 * - Heartbeat monitoring
 * - Error recovery
 * - Debug logging
 */
export class WebSocketManager {
  private ws: WebSocket | null = null;
  private config: WebSocketConfig;
  private state: WebSocketState = WebSocketState.DISCONNECTED;
  private subscriptions = new Map<string, Subscription>();
  private messageQueue: WebSocketMessage[] = [];
  private reconnectAttempts = 0;
  private reconnectTimer?: ReturnType<typeof setTimeout>;
  private heartbeatTimer?: ReturnType<typeof setTimeout>;
  private lastHeartbeat = 0;
  private listeners = new Map<string, Set<(event: unknown) => void>>();

  constructor(config: Partial<WebSocketConfig> = {}) {
    this.config = {
      url: config.url || this.buildWebSocketUrl(),
      protocols: config.protocols,
      reconnectInterval: config.reconnectInterval || 3000,
      maxReconnectAttempts: config.maxReconnectAttempts || 10,
      heartbeatInterval: config.heartbeatInterval || 30000,
      queueMaxSize: config.queueMaxSize || 100,
      debug: config.debug ?? true,
    };

    // Auto-connect when authenticated
    if (enhancedApiClient.isAuthenticated()) {
      this.connect();
    }
  }

  private buildWebSocketUrl(): string {
    return resolveBackendWebSocketUrl('/ws');
  }

  private log(message: string, ...args: unknown[]): void {
    if (this.config.debug) {
      console.log(`[WebSocket] ${message}`, ...args);
    }
  }

  private error(message: string, ...args: unknown[]): void {
    console.error(`[WebSocket] ${message}`, ...args);
  }

  // ==================== Connection Management ====================

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      this.setState(WebSocketState.CONNECTING);
      this.log('Connecting to', this.config.url);

      try {
        // Add authentication token to connection
        const token = localStorage.getItem('access_token') || undefined;
        const urlWithAuth = resolveBackendWebSocketUrl(this.config.url, token);

        this.ws = new WebSocket(urlWithAuth, this.config.protocols);

        this.ws.onopen = (event) => {
          this.log('Connected successfully');
          this.setState(WebSocketState.CONNECTED);
          this.reconnectAttempts = 0;
          this.startHeartbeat();
          this.processMessageQueue();
          this.emit('open', event);
          resolve();
        };

        this.ws.onmessage = (event) => {
          this.handleMessage(event);
        };

        this.ws.onclose = (event) => {
          this.log('Connection closed', event.code, event.reason);
          this.setState(WebSocketState.DISCONNECTED);
          this.stopHeartbeat();
          this.emit('close', event);

          // Attempt reconnection if not manually closed
          if (event.code !== 1000) {
            this.scheduleReconnect();
          }
        };

        this.ws.onerror = (event) => {
          this.error('Connection error', event);
          this.setState(WebSocketState.ERROR);
          this.emit('error', event);
          reject(new Error('WebSocket connection failed'));
        };
      } catch (error) {
        this.error('Failed to create WebSocket connection', error);
        this.setState(WebSocketState.ERROR);
        reject(error);
      }
    });
  }

  disconnect(): void {
    this.log('Disconnecting...');

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = undefined;
    }

    this.stopHeartbeat();

    if (this.ws) {
      this.ws.close(1000, 'Manual disconnect');
      this.ws = null;
    }

    this.setState(WebSocketState.DISCONNECTED);
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
      this.error('Max reconnection attempts reached');
      this.setState(WebSocketState.ERROR);
      return;
    }

    this.setState(WebSocketState.RECONNECTING);
    this.reconnectAttempts++;

    // Exponential backoff
    const delay = Math.min(
      this.config.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1),
      30000
    );

    this.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

    this.reconnectTimer = setTimeout(() => {
      this.connect().catch((error) => {
        this.error('Reconnection failed', error);
        this.scheduleReconnect();
      });
    }, delay);
  }

  // ==================== State Management ====================

  private setState(newState: WebSocketState): void {
    if (this.state !== newState) {
      const oldState = this.state;
      this.state = newState;
      this.log(`State changed: ${oldState} -> ${newState}`);
      this.emit('stateChange', { oldState, newState });
    }
  }

  getState(): WebSocketState {
    return this.state;
  }

  isConnected(): boolean {
    return this.state === WebSocketState.CONNECTED;
  }

  // ==================== Message Handling ====================

  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);

      // Handle heartbeat
      if (message.type === MessageType.HEARTBEAT) {
        this.lastHeartbeat = Date.now();
        return;
      }

      this.log('Received message', message.type, message.payload);

      // Distribute to subscribers
      this.subscriptions.forEach((subscription) => {
        if (this.matchesSubscription(message, subscription)) {
          try {
            subscription.callback(message);
          } catch (error) {
            this.error('Subscription callback error', error);
          }
        }
      });

      this.emit('message', message);
    } catch (error) {
      this.error('Failed to parse message', error, event.data);
    }
  }

  private matchesSubscription(message: WebSocketMessage, subscription: Subscription): boolean {
    const channel =
      typeof message.payload === 'object' &&
      message.payload !== null &&
      typeof (message.payload as { channel?: unknown }).channel === 'string'
        ? (message.payload as { channel: string }).channel
        : undefined;

    // Check channel match (if specified)
    if (subscription.channel && !channel?.includes(subscription.channel)) {
      return false;
    }

    // Apply custom filter
    if (subscription.filter && !subscription.filter(message)) {
      return false;
    }

    return true;
  }

  send(message: WebSocketMessage | object): void {
    const msgToSend =
      'type' in message
        ? message
        : { type: 'CUSTOM', payload: message, timestamp: new Date().toISOString() };

    if (this.isConnected() && this.ws) {
      try {
        this.ws.send(JSON.stringify(msgToSend));
        this.log('Sent message', msgToSend);
      } catch (error) {
        this.error('Failed to send message', error);
        this.queueMessage(msgToSend as WebSocketMessage);
      }
    } else {
      this.log('Not connected, queuing message');
      this.queueMessage(msgToSend as WebSocketMessage);
    }
  }

  private queueMessage(message: WebSocketMessage): void {
    if (this.messageQueue.length >= this.config.queueMaxSize) {
      this.messageQueue.shift(); // Remove oldest message
    }
    this.messageQueue.push(message);
  }

  private processMessageQueue(): void {
    while (this.messageQueue.length > 0 && this.isConnected()) {
      const message = this.messageQueue.shift();
      if (message) {
        this.send(message);
      }
    }
  }

  // ==================== Subscription Management ====================

  subscribe(
    channel: string,
    callback: (message: WebSocketMessage) => void,
    filter?: (message: WebSocketMessage) => boolean
  ): string {
    const id = `sub_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    const subscription: Subscription = {
      id,
      channel,
      callback,
      filter,
    };

    this.subscriptions.set(id, subscription);
    this.log('Added subscription', id, 'for channel', channel);

    // Send subscription message to server
    this.send({
      type: 'SUBSCRIBE',
      payload: { channel },
      timestamp: new Date().toISOString(),
    });

    return id;
  }

  unsubscribe(subscriptionId: string): void {
    const subscription = this.subscriptions.get(subscriptionId);
    if (subscription) {
      this.subscriptions.delete(subscriptionId);
      this.log('Removed subscription', subscriptionId);

      // Send unsubscription message to server
      this.send({
        type: 'UNSUBSCRIBE',
        payload: { channel: subscription.channel },
        timestamp: new Date().toISOString(),
      });
    }
  }

  unsubscribeAll(): void {
    this.log('Removing all subscriptions');
    this.subscriptions.clear();

    this.send({
      type: 'UNSUBSCRIBE_ALL',
      payload: {},
      timestamp: new Date().toISOString(),
    });
  }

  // ==================== Heartbeat ====================

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.lastHeartbeat = Date.now();

    this.heartbeatTimer = setInterval(() => {
      if (this.isConnected()) {
        // Send ping
        this.send({
          type: MessageType.HEARTBEAT,
          payload: { ping: Date.now() },
          timestamp: new Date().toISOString(),
        });

        // Check if we've received a heartbeat recently
        const timeSinceLastHeartbeat = Date.now() - this.lastHeartbeat;
        if (timeSinceLastHeartbeat > this.config.heartbeatInterval * 2) {
          this.error('Heartbeat timeout, reconnecting...');
          this.disconnect();
          this.scheduleReconnect();
        }
      }
    }, this.config.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = undefined;
    }
  }

  // ==================== Event Emitter ====================

  on(event: string, callback: (data: unknown) => void): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
  }

  off(event: string, callback: (data: unknown) => void): void {
    this.listeners.get(event)?.delete(callback);
  }

  private emit(event: string, data: unknown): void {
    this.listeners.get(event)?.forEach((callback) => {
      try {
        callback(data);
      } catch (error) {
        this.error('Event callback error', error);
      }
    });
  }

  // ==================== Convenience Methods ====================

  subscribeToBotUpdates(instanceId: string, callback: (data: unknown) => void): string {
    return this.subscribe(
      `bot.${instanceId}`,
      callback,
      (msg) => msg.type === MessageType.BOT_UPDATE
    );
  }

  subscribeToTradeUpdates(instanceId: string, callback: (data: unknown) => void): string {
    return this.subscribe(
      `bot.${instanceId}.trades`,
      callback,
      (msg) => msg.type === MessageType.TRADE_UPDATE
    );
  }

  subscribeToPositionUpdates(instanceId: string, callback: (data: unknown) => void): string {
    return this.subscribe(
      `bot.${instanceId}.positions`,
      callback,
      (msg) => msg.type === MessageType.POSITION_UPDATE
    );
  }

  subscribeToAlerts(instanceId: string, callback: (data: unknown) => void): string {
    return this.subscribe(
      `bot.${instanceId}.alerts`,
      callback,
      (msg) => msg.type === MessageType.ALERT
    );
  }

  subscribeToBacktestProgress(runId: string, callback: (data: unknown) => void): string {
    return this.subscribe(
      `backtest.${runId}`,
      callback,
      (msg) => msg.type === MessageType.BACKTEST_PROGRESS
    );
  }

  subscribeToSystemStatus(callback: (data: unknown) => void): string {
    return this.subscribe(
      'system.status',
      callback,
      (msg) => msg.type === MessageType.SYSTEM_STATUS
    );
  }

  // ==================== Statistics ====================

  getStats(): object {
    return {
      state: this.state,
      reconnectAttempts: this.reconnectAttempts,
      subscriptions: this.subscriptions.size,
      queuedMessages: this.messageQueue.length,
      lastHeartbeat: this.lastHeartbeat,
      connected: this.isConnected(),
    };
  }
}

// Create singleton instance
export const wsManager = new WebSocketManager();

// Auto-connect when authentication state changes
let wasAuthenticated = enhancedApiClient.isAuthenticated();

setInterval(() => {
  const isAuthenticated = enhancedApiClient.isAuthenticated();

  if (isAuthenticated && !wasAuthenticated) {
    // User just logged in
    wsManager.connect().catch(console.error);
  } else if (!isAuthenticated && wasAuthenticated) {
    // User just logged out
    wsManager.disconnect();
  }

  wasAuthenticated = isAuthenticated;
}, 1000);

export default wsManager;
