/**
 * DEV-ONLY mock data
 * Returned automatically when the API responds with an empty dataset in development mode.
 * Tree-shaken away in production builds (all usages are behind `import.meta.env.DEV`).
 */

// ── helpers ───────────────────────────────────────────────────────────────────

const daysAgo = (n: number): string => {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString();
};

const dateStr = (daysOffset: number): string => {
  const d = new Date('2024-01-01');
  d.setDate(d.getDate() + daysOffset);
  return d.toISOString().substring(0, 10);
};

// ── Backtest runs ─────────────────────────────────────────────────────────────

export interface MockBacktestRun {
  run_id: string;
  name?: string;
  start_date: string;
  end_date: string;
  status: string;
  progress_pct?: number;
  current_pair?: string;
  total_trades: number;
  profitable_trades: number;
  losing_trades: number;
  total_pnl: number;
  sharpe_ratio: number;
  win_rate: number;
  profit_factor: number;
  max_drawdown_pct: number;
  created_at: string;
  updated_at: string;
}

export const MOCK_BACKTEST_RUNS: MockBacktestRun[] = [
  {
    run_id: 'mock-run-aabb1122',
    name: 'Q1 Bull Run Strategy',
    start_date: '2024-01-01',
    end_date: '2024-03-31',
    status: 'COMPLETED',
    total_trades: 142,
    profitable_trades: 91,
    losing_trades: 51,
    total_pnl: 4820.35,
    sharpe_ratio: 2.14,
    win_rate: 64.1,
    profit_factor: 1.87,
    max_drawdown_pct: 8.3,
    created_at: daysAgo(14),
    updated_at: daysAgo(13),
  },
  {
    run_id: 'mock-run-ccdd3344',
    name: 'ETH/BTC Pairs Wide',
    start_date: '2024-02-01',
    end_date: '2024-04-30',
    status: 'COMPLETED',
    total_trades: 98,
    profitable_trades: 55,
    losing_trades: 43,
    total_pnl: 1230.75,
    sharpe_ratio: 1.42,
    win_rate: 56.1,
    profit_factor: 1.38,
    max_drawdown_pct: 12.1,
    created_at: daysAgo(10),
    updated_at: daysAgo(9),
  },
  {
    run_id: 'mock-run-eeff5566',
    name: 'High-Vol Momentum',
    start_date: '2023-10-01',
    end_date: '2023-12-31',
    status: 'COMPLETED',
    total_trades: 217,
    profitable_trades: 148,
    losing_trades: 69,
    total_pnl: 9103.60,
    sharpe_ratio: 3.01,
    win_rate: 68.2,
    profit_factor: 2.41,
    max_drawdown_pct: 5.7,
    created_at: daysAgo(30),
    updated_at: daysAgo(29),
  },
  {
    run_id: 'mock-run-gghh7788',
    name: 'Conservative Low-DD',
    start_date: '2024-01-15',
    end_date: '2024-02-15',
    status: 'COMPLETED',
    total_trades: 43,
    profitable_trades: 22,
    losing_trades: 21,
    total_pnl: -345.20,
    sharpe_ratio: 0.61,
    win_rate: 51.2,
    profit_factor: 0.92,
    max_drawdown_pct: 3.2,
    created_at: daysAgo(20),
    updated_at: daysAgo(19),
  },
  {
    run_id: 'mock-run-iijj9900',
    name: 'Altcoin Spread Arb',
    start_date: '2024-03-01',
    end_date: '2024-03-31',
    status: 'FAILED',
    total_trades: 12,
    profitable_trades: 5,
    losing_trades: 7,
    total_pnl: -120.00,
    sharpe_ratio: -0.22,
    win_rate: 41.7,
    profit_factor: 0.71,
    max_drawdown_pct: 18.4,
    created_at: daysAgo(7),
    updated_at: daysAgo(7),
  },
  {
    run_id: 'mock-run-kkll1122',
    name: 'Live Scan — Apr 2024',
    start_date: dateStr(-30),
    end_date: dateStr(0),
    status: 'RUNNING',
    progress_pct: 47.3,
    current_pair: 'ETH-USD / BTC-USD',
    total_trades: 0,
    profitable_trades: 0,
    losing_trades: 0,
    total_pnl: 0,
    sharpe_ratio: 0,
    win_rate: 0,
    profit_factor: 0,
    max_drawdown_pct: 0,
    created_at: daysAgo(0),
    updated_at: daysAgo(0),
  },
  {
    run_id: 'mock-run-mmnn3344',
    name: 'Pending Queue Run',
    start_date: dateStr(-60),
    end_date: dateStr(-30),
    status: 'PENDING',
    progress_pct: 0,
    total_trades: 0,
    profitable_trades: 0,
    losing_trades: 0,
    total_pnl: 0,
    sharpe_ratio: 0,
    win_rate: 0,
    profit_factor: 0,
    max_drawdown_pct: 0,
    created_at: daysAgo(0),
    updated_at: daysAgo(0),
  },
];

// ── Bot instances ─────────────────────────────────────────────────────────────

export interface MockBotInstance {
  instance_id: string;
  status: string;
}

export interface MockBotStats {
  instance_id: string;
  status: string;
  total_pnl: number;
  realized_pnl: number;
  unrealized_pnl: number;
  total_positions: number;
  open_positions: number;
  total_trades: number;
  win_rate: number;
  last_update: string;
}

export const MOCK_BOT_INSTANCES: MockBotInstance[] = [
  { instance_id: 'mock-bot-alpha-7f3a', status: 'RUNNING' },
  { instance_id: 'mock-bot-beta-2c8d',  status: 'STOPPED' },
  { instance_id: 'mock-bot-gamma-5e1b', status: 'RUNNING' },
];

export const MOCK_BOT_STATS: Record<string, MockBotStats> = {
  'mock-bot-alpha-7f3a': {
    instance_id: 'mock-bot-alpha-7f3a',
    status: 'RUNNING',
    total_pnl: 3_412.80,
    realized_pnl: 2_890.40,
    unrealized_pnl: 522.40,
    total_positions: 28,
    open_positions: 3,
    total_trades: 112,
    win_rate: 62.5,
    last_update: daysAgo(0),
  },
  'mock-bot-beta-2c8d': {
    instance_id: 'mock-bot-beta-2c8d',
    status: 'STOPPED',
    total_pnl: -780.15,
    realized_pnl: -780.15,
    unrealized_pnl: 0,
    total_positions: 14,
    open_positions: 0,
    total_trades: 47,
    win_rate: 40.4,
    last_update: daysAgo(3),
  },
  'mock-bot-gamma-5e1b': {
    instance_id: 'mock-bot-gamma-5e1b',
    status: 'RUNNING',
    total_pnl: 1_201.50,
    realized_pnl: 950.00,
    unrealized_pnl: 251.50,
    total_positions: 9,
    open_positions: 2,
    total_trades: 38,
    win_rate: 57.9,
    last_update: daysAgo(0),
  },
};

export interface MockPosition {
  position_id: string;
  market_1: string;
  market_2: string;
  entry_time: string;
  z_score: number;
  status: string;
}

export const MOCK_POSITIONS: MockPosition[] = [
  {
    position_id: 'mock-pos-001',
    market_1: 'ETH-USD',
    market_2: 'BTC-USD',
    entry_time: daysAgo(1),
    z_score: 2.34,
    status: 'OPEN',
  },
  {
    position_id: 'mock-pos-002',
    market_1: 'SOL-USD',
    market_2: 'AVAX-USD',
    entry_time: daysAgo(0),
    z_score: -2.87,
    status: 'OPEN',
  },
  {
    position_id: 'mock-pos-003',
    market_1: 'LINK-USD',
    market_2: 'UNI-USD',
    entry_time: daysAgo(2),
    z_score: 1.92,
    status: 'PARTIAL',
  },
];

export interface MockAlert {
  timestamp: string;
  title: string;
  message: string;
}

export const MOCK_ALERTS: MockAlert[] = [
  {
    timestamp: daysAgo(0),
    title: 'Z-Score Threshold Breached',
    message: 'ETH-USD/BTC-USD z-score crossed +2.5 — entry signal triggered.',
  },
  {
    timestamp: daysAgo(1),
    title: 'Position Closed — Profit',
    message: 'SOL-USD/DOT-USD pair closed at +$142.30 PnL after mean reversion.',
  },
  {
    timestamp: daysAgo(2),
    title: 'API Rate Limit Warning',
    message: 'dYdX API rate limit approaching (85% used). Throttling order submissions.',
  },
];

// ── Utility ───────────────────────────────────────────────────────────────────

/**
 * In development mode: if `live` is empty, return `mock` instead.
 * In production (or when live data is present) always returns `live` unchanged.
 */
export type MockDataMode = 'auto' | 'on' | 'off';

const readQueryMode = (): MockDataMode | null => {
  if (typeof window === 'undefined') return null;
  const value = new URLSearchParams(window.location.search).get('mockData');
  if (value === '1' || value === 'on' || value === 'true') return 'on';
  if (value === '0' || value === 'off' || value === 'false') return 'off';
  return null;
};

const readStoredMode = (): MockDataMode => {
  if (typeof window === 'undefined') return 'auto';

  const mode = window.localStorage.getItem('mockDataMode');
  if (mode === 'auto' || mode === 'on' || mode === 'off') return mode;

  // Backward compatibility with previous boolean storage key.
  const legacy = window.localStorage.getItem('forceMockData');
  if (legacy === 'true') return 'on';
  if (legacy === 'false') return 'off';

  return 'auto';
};

/**
 * Returns true when mock data should be enabled.
 * Defaults to Vite dev mode, but can be forced via:
 * - VITE_FORCE_MOCK_DATA=true
 * - ?mockData=1
 * - localStorage.setItem('mockDataMode', 'on')
 */
export function getMockDataMode(): MockDataMode {
  const envForce = String(import.meta.env.VITE_FORCE_MOCK_DATA ?? '').toLowerCase();
  if (envForce === 'true' || envForce === 'on' || envForce === '1') return 'on';
  if (envForce === 'false' || envForce === 'off' || envForce === '0') return 'off';

  const queryMode = readQueryMode();
  if (queryMode) return queryMode;

  return readStoredMode();
}

export function setMockDataMode(mode: MockDataMode): void {
  if (typeof window === 'undefined') return;

  if (mode === 'auto') {
    window.localStorage.removeItem('mockDataMode');
    window.localStorage.removeItem('forceMockData');
    return;
  }

  window.localStorage.setItem('mockDataMode', mode);
  // Keep legacy key in sync for older code paths.
  window.localStorage.setItem('forceMockData', String(mode === 'on'));
}

export function shouldUseDevMocks(): boolean {
  const mode = getMockDataMode();
  if (mode === 'on') return true;
  if (mode === 'off') return false;
  return import.meta.env.DEV;
}

let hasLoggedMockFallback = false;

export function devFallback<T>(live: T[], mock: T[]): T[] {
  if (!shouldUseDevMocks()) return live;
  if (live.length > 0) return live;
  if (!hasLoggedMockFallback) {
    console.info('🔧 [dev] No data from API — rendering mock data for development.');
    hasLoggedMockFallback = true;
  }
  return mock;
}

