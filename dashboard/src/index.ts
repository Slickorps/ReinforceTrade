import { TradingService, Position, Trade, PortfolioSummary } from './trading_service';

// ── DOM References ───────────────────────────────────────────────

const connectionStatus = document.getElementById('connection-status')!;
const totalPnlEl = document.getElementById('total-pnl')!;
const openPositionsEl = document.getElementById('open-positions')!;
const winRateEl = document.getElementById('win-rate')!;
const positionsBody = document.getElementById('positions-body')!;
const tradesBody = document.getElementById('trades-body')!;
const canvas = document.getElementById('pnl-chart') as HTMLCanvasElement;
const ctx = canvas.getContext('2d')!;

// ── Chart State ──────────────────────────────────────────────────

const CHART_PADDING = 40;
const MAX_POINTS = 200;

function drawChart(pnlHistory: number[]): void {
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  if (pnlHistory.length < 2) {
    ctx.fillStyle = '#888';
    ctx.font = '14px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Waiting for P&L data...', w / 2, h / 2);
    return;
  }

  const data = pnlHistory.slice(-MAX_POINTS);
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  // Grid lines
  ctx.strokeStyle = '#2a2a2a';
  ctx.lineWidth = 1;
  for (let i = 0; i < 5; i++) {
    const y = CHART_PADDING + (i / 4) * (h - 2 * CHART_PADDING);
    ctx.beginPath();
    ctx.moveTo(CHART_PADDING, y);
    ctx.lineTo(w - CHART_PADDING, y);
    ctx.stroke();
  }

  // P&L curve
  const stepX = (w - 2 * CHART_PADDING) / (data.length - 1);

  ctx.beginPath();
  data.forEach((val, i) => {
    const x = CHART_PADDING + i * stepX;
    const y = CHART_PADDING + (1 - (val - min) / range) * (h - 2 * CHART_PADDING);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });

  // Color: green if ending > starting, red otherwise
  const color = data[data.length - 1] >= data[0] ? '#00c853' : '#ff5252';
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.stroke();
}

// ── UI Renderers ─────────────────────────────────────────────────

function renderPortfolio(summary: PortfolioSummary): void {
  totalPnlEl.textContent = summary.totalPnl.toFixed(2);
  totalPnlEl.style.color = summary.totalPnl >= 0 ? '#00c853' : '#ff5252';

  openPositionsEl.textContent = String(summary.openPositions);
  winRateEl.textContent = (summary.winRate * 100).toFixed(1) + '%';
}

function renderPositions(positions: Position[]): void {
  if (positions.length === 0) {
    positionsBody.innerHTML = '<tr><td colspan="6" class="empty">No open positions</td></tr>';
    return;
  }

  positionsBody.innerHTML = positions.map(p => {
    const pnlColor = p.unrealizedPnl >= 0 ? 'green' : 'red';
    return `<tr>
      <td>${p.symbol}</td>
      <td>${p.size}</td>
      <td>${p.entryPrice.toFixed(2)}</td>
      <td>${p.markPrice.toFixed(2)}</td>
      <td class="${pnlColor}">${p.unrealizedPnl >= 0 ? '+' : ''}${p.unrealizedPnl.toFixed(2)}</td>
      <td class="${pnlColor}">${p.pnlPercent >= 0 ? '+' : ''}${p.pnlPercent.toFixed(2)}%</td>
    </tr>`;
  }).join('');
}

function renderTrades(trades: Trade[]): void {
  if (trades.length === 0) {
    tradesBody.innerHTML = '<tr><td colspan="6" class="empty">No trades yet</td></tr>';
    return;
  }

  tradesBody.innerHTML = trades.map(t => {
    const sideColor = t.side === 'buy' ? 'green' : 'red';
    const pnlColor = t.pnl >= 0 ? 'green' : 'red';
    return `<tr>
      <td>${t.time}</td>
      <td>${t.symbol}</td>
      <td class="${sideColor}">${t.side.toUpperCase()}</td>
      <td>${t.qty}</td>
      <td>${t.price.toFixed(2)}</td>
      <td class="${pnlColor}">${t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)}</td>
    </tr>`;
  }).join('');
}

function updateConnectionStatus(status: string): void {
  connectionStatus.className = `status-${status}`;
  const label = status === 'connected' ? '◉ Connected' :
                status === 'reconnecting' ? '◉ Reconnecting...' : '◉ Disconnected';
  connectionStatus.textContent = label;
}

// ── App Initialization ───────────────────────────────────────────

function init(): void {
  const service = new TradingService('ws://localhost:8000/ws');

  service.on('status', (data) => updateConnectionStatus(data.status));
  service.on('portfolio', (data: PortfolioSummary) => renderPortfolio(data));
  service.on('position', (data: Position) => renderPositions([data]));
  service.on('trade', (data: Trade) => renderTrades([data]));
  service.on('pnl_point', () => drawChart(service.pnlHistory));
  service.on('error', (data) => console.error('[Dashboard]', data.message));

  // Positions and trades are received as individual events.
  // For batch updates, we handle them as arrays:
  service.on('status', (data) => {
    if (data.positions) renderPositions(data.positions);
    if (data.trades) renderTrades(data.trades);
    if (data.portfolio) renderPortfolio(data.portfolio);
  });

  service.connect();

  // Redraw chart on resize
  window.addEventListener('resize', () => drawChart(service.pnlHistory));
}

document.addEventListener('DOMContentLoaded', init);