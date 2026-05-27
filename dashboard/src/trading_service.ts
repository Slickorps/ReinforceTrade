/**
 * TradingService — WebSocket client for real-time trading data.
 *
 * Connects to the ReinforceTrade WebSocket endpoint, parses JSON messages,
 * and emits typed events (position, pnl, trade) to UI components.
 *
 * Features:
 * - Exponential backoff reconnection (max 10 retries)
 * - Connection status tracking
 * - Typed event emission
 */

export interface Position {
  symbol: string;
  size: number;
  entryPrice: number;
  markPrice: number;
  unrealizedPnl: number;
  pnlPercent: number;
}

export interface Trade {
  time: string;
  symbol: string;
  side: 'buy' | 'sell';
  qty: number;
  price: number;
  pnl: number;
}

export interface PortfolioSummary {
  totalPnl: number;
  openPositions: number;
  winRate: number;
}

export type ConnectionStatus = 'connected' | 'disconnected' | 'reconnecting';

export type EventType =
  | 'position'
  | 'trade'
  | 'portfolio'
  | 'pnl_point'
  | 'status'
  | 'error';

export type EventCallback = (data: any) => void;

export class TradingService {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 10;
  private reconnectDelay: number = 1000; // starts at 1s
  private shouldReconnect: boolean = true;
  private status: ConnectionStatus = 'disconnected';
  private listeners: Map<EventType, Set<EventCallback>> = new Map();

  /** P&L history buffer for chart rendering */
  public pnlHistory: number[] = [];

  constructor(url: string = 'ws://localhost:8000/ws') {
    this.url = url;
  }

  // ── Event Emitter ──────────────────────────────────────────────

  on(event: EventType, callback: EventCallback): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
  }

  off(event: EventType, callback: EventCallback): void {
    this.listeners.get(event)?.delete(callback);
  }

  private emit(event: EventType, data: any): void {
    this.listeners.get(event)?.forEach(cb => cb(data));
  }

  // ── Connection Management ──────────────────────────────────────

  connect(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return; // already connected or connecting
    }

    this.shouldReconnect = true;
    this.setStatus('reconnecting');

    try {
      this.ws = new WebSocket(this.url);
    } catch (err) {
      this.handleError(err);
      return;
    }

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.reconnectDelay = 1000;
      this.setStatus('connected');
    };

    this.ws.onmessage = (event: MessageEvent) => {
      this.handleMessage(event.data);
    };

    this.ws.onclose = () => {
      if (this.status === 'connected') {
        this.setStatus('disconnected');
      }
      this.attemptReconnect();
    };

    this.ws.onerror = (event: Event) => {
      this.handleError(event);
    };
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.setStatus('disconnected');
  }

  // ── Reconnection (Exponential Backoff) ─────────────────────────

  private attemptReconnect(): void {
    if (!this.shouldReconnect) return;
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.setStatus('disconnected');
      this.emit('error', { message: `Max reconnect attempts (${this.maxReconnectAttempts}) reached` });
      return;
    }

    this.reconnectAttempts++;
    this.setStatus('reconnecting');

    const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000);
    const jitter = Math.random() * 1000;
    const totalDelay = delay + jitter;

    setTimeout(() => {
      if (this.shouldReconnect) {
        this.connect();
      }
    }, totalDelay);
  }

  // ── Message Handling ───────────────────────────────────────────

  private handleMessage(raw: string): void {
    try {
      const msg = JSON.parse(raw);
      const { type, data } = msg;

      switch (type) {
        case 'position':
          this.emit('position', data as Position);
          break;

        case 'trade':
          this.emit('trade', data as Trade);
          break;

        case 'portfolio':
          this.emit('portfolio', data as PortfolioSummary);
          break;

        case 'pnl_point':
          this.pnlHistory.push(data.pnl);
          this.emit('pnl_point', data);
          break;

        case 'status':
          this.emit('status', data);
          break;

        default:
          console.warn(`[TradingService] Unknown message type: ${type}`, data);
      }
    } catch (err) {
      console.error('[TradingService] Failed to parse message:', raw, err);
    }
  }

  // ── Helpers ────────────────────────────────────────────────────

  private setStatus(status: ConnectionStatus): void {
    this.status = status;
    this.emit('status', { status });
  }

  private handleError(err: unknown): void {
    const message = err instanceof Error ? err.message : String(err);
    console.error('[TradingService] Error:', message);
    this.emit('error', { message });
  }

  getStatus(): ConnectionStatus {
    return this.status;
  }

  isConnected(): boolean {
    return this.status === 'connected';
  }
}