// Frontend Development Guide - Using Backend API in React Components
// Comprehensive examples of how to integrate the dYdX bot API into React components

import { apiClient, BotInstance, BotPosition } from '@/api/client';
import { useAuthStore } from '@/store/auth';
import { useCallback, useEffect, useState } from 'react';

// ==================== Pattern 1: Authentication ====================

/**
 * Login Component Example
 * Shows how to handle user authentication and token management
 */
export function LoginComponent() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const login = useAuthStore((state) => state.login);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // API client handles token management automatically
      await apiClient.login(username, password);
      
      // Update Zustand store
      login(await apiClient.getCurrentUser());
      
      // Redirect to dashboard
      window.location.href = '/dashboard';
    } catch (err: any) {
      setError(err.response?.data?.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleLogin}>
      <input
        type="text"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        placeholder="Username"
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
      />
      <button type="submit" disabled={loading}>
        {loading ? 'Logging in...' : 'Login'}
      </button>
      {error && <p className="error">{error}</p>}
    </form>
  );
}

// ==================== Pattern 2: List Data with Pagination ====================

/**
 * Bot Instances List Component
 * Demonstrates how to fetch and display paginated data
 */
export function BotInstancesListComponent() {
  const [bots, setBots] = useState<BotInstance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pagination, setPagination] = useState({ limit: 50, offset: 0, total: 0 });

  const fetchBots = useCallback(async () => {
    try {
      setLoading(true);
      const result = await apiClient.listBotInstances(
        undefined,
        pagination.limit,
        pagination.offset
      );
      setBots(result.data);
      setPagination((prev) => ({ ...prev, total: result.count }));
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [pagination.limit, pagination.offset]);

  useEffect(() => {
    fetchBots();
  }, [fetchBots]);

  const handleNextPage = () => {
    setPagination((prev) => ({
      ...prev,
      offset: prev.offset + prev.limit,
    }));
  };

  const handlePrevPage = () => {
    setPagination((prev) => ({
      ...prev,
      offset: Math.max(0, prev.offset - prev.limit),
    }));
  };

  if (loading) return <div>Loading bots...</div>;
  if (error) return <div className="error">Error: {error}</div>;

  return (
    <div>
      <h2>Bot Instances</h2>
      {bots.length === 0 ? (
        <p>No bots found</p>
      ) : (
        <>
          <ul>
            {bots.map((bot) => (
              <li key={bot.instance_id}>
                <h3>{bot.name}</h3>
                <p>Status: {bot.status}</p>
                <p>Trades: {bot.total_trades || 0}</p>
                <p>Win Rate: {((bot.win_rate || 0) * 100).toFixed(1)}%</p>
                <p>P&L: ${(bot.pnl || 0).toFixed(2)}</p>
              </li>
            ))}
          </ul>
          <div className="pagination">
            <button onClick={handlePrevPage} disabled={pagination.offset === 0}>
              Previous
            </button>
            <span>
              Page {Math.floor(pagination.offset / pagination.limit) + 1} of{' '}
              {Math.ceil(pagination.total / pagination.limit)}
            </span>
            <button
              onClick={handleNextPage}
              disabled={pagination.offset + pagination.limit >= pagination.total}
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ==================== Pattern 3: Real-Time Updates with WebSocket ====================

/**
 * Real-Time Bot Status Component
 * Shows how to subscribe to real-time WebSocket updates
 */
export function BotRealtimeComponent({ instanceId }: { instanceId: string }) {
  const [status, setStatus] = useState<any>(null);
  const [positions, setPositions] = useState<BotPosition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let isMounted = true;

    const connect = async () => {
      try {
        // Fetch initial data
        const statsPromise = apiClient.getRealtimeStats(instanceId);
        const positionsPromise = apiClient.getCurrentPositions(instanceId);

        const [stats, pos] = await Promise.all([statsPromise, positionsPromise]);

        if (isMounted) {
          setStatus(stats);
          setPositions(pos);
          setLoading(false);
        }

        // Connect WebSocket for real-time updates
        ws = apiClient.connectBotUpdates(instanceId, (update) => {
          if (!isMounted) return;

          switch (update.type) {
            case 'POSITION_OPENED':
              setPositions((prev) => [...prev, update.position]);
              break;
            case 'POSITION_CLOSED':
              setPositions((prev) =>
                prev.filter((p) => p.position_id !== update.position.position_id)
              );
              break;
            case 'STATS_UPDATE':
              setStatus((prev) => ({ ...prev, ...update.stats }));
              break;
          }
        });

        ws.onerror = (error) => {
          if (isMounted) {
            setError('WebSocket connection failed');
          }
        };
      } catch (err: any) {
        if (isMounted) {
          setError(err.message);
          setLoading(false);
        }
      }
    };

    connect();

    return () => {
      isMounted = false;
      if (ws) ws.close();
    };
  }, [instanceId]);

  if (loading) return <div>Loading...</div>;
  if (error) return <div className="error">Error: {error}</div>;

  return (
    <div className="bot-status">
      <h2>Bot Status</h2>
      {status && (
        <div className="stats">
          <div>Uptime: {Math.floor(status.uptime_seconds / 60)} min</div>
          <div>Total Trades: {status.total_trades}</div>
          <div>Open Positions: {status.open_positions}</div>
          <div>P&L: ${status.total_pnl.toFixed(2)}</div>
          <div>Win Rate: {(status.win_rate * 100).toFixed(1)}%</div>
        </div>
      )}

      <h3>Current Positions ({positions.length})</h3>
      {positions.length === 0 ? (
        <p>No open positions</p>
      ) : (
        <div className="positions-list">
          {positions.map((pos) => (
            <div key={pos.position_id} className="position-card">
              <h4>
                {pos.market_1} ↔ {pos.market_2}
              </h4>
              <p>
                {pos.side_1} {pos.size_1} {pos.market_1}
              </p>
              <p>
                {pos.side_2} {pos.size_2} {pos.market_2}
              </p>
              <p className={pos.unrealized_pnl >= 0 ? 'profit' : 'loss'}>
                Unrealized P&L: ${pos.unrealized_pnl.toFixed(2)} (
                {pos.unrealized_pnl_percent.toFixed(2)}%)
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ==================== Pattern 4: Create and Manage Resources ====================

/**
 * Create Bot Instance Component
 * Shows how to create new resources and handle errors
 */
export function CreateBotInstanceComponent() {
  const [formData, setFormData] = useState({
    instance_id: '',
    name: '',
    address: '',
    mnemonic: '',
    zscore_threshold: 1.5,
    usd_per_trade: 100,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      await apiClient.createBotInstance({
        instance_id: formData.instance_id,
        name: formData.name,
        credentials: {
          address: formData.address,
          mnemonic: formData.mnemonic,
        },
        trading_params: {
          is_testnet: false,
          zscore_threshold: formData.zscore_threshold,
          usd_per_trade: formData.usd_per_trade,
        },
      });

      setSuccess(true);
      setFormData({
        instance_id: '',
        name: '',
        address: '',
        mnemonic: '',
        zscore_threshold: 1.5,
        usd_per_trade: 100,
      });

      // Redirect after success
      setTimeout(() => {
        window.location.href = '/bots';
      }, 2000);
    } catch (err: any) {
      setError(
        err.response?.data?.details?.message || err.response?.data?.message || err.message
      );
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'number' ? parseFloat(value) : value,
    }));
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        name="instance_id"
        value={formData.instance_id}
        onChange={handleInputChange}
        placeholder="Bot Instance ID"
        required
      />
      <input
        type="text"
        name="name"
        value={formData.name}
        onChange={handleInputChange}
        placeholder="Bot Name"
        required
      />
      <input
        type="text"
        name="address"
        value={formData.address}
        onChange={handleInputChange}
        placeholder="dYdX Address"
        required
      />
      <textarea
        name="mnemonic"
        value={formData.mnemonic}
        onChange={(e) =>
          setFormData((prev) => ({ ...prev, mnemonic: e.target.value }))
        }
        placeholder="Mnemonic phrase"
        required
      />
      <input
        type="number"
        name="zscore_threshold"
        value={formData.zscore_threshold}
        onChange={handleInputChange}
        placeholder="Z-Score Threshold"
        step={0.1}
        required
      />
      <input
        type="number"
        name="usd_per_trade"
        value={formData.usd_per_trade}
        onChange={handleInputChange}
        placeholder="USD Per Trade"
        step={10}
        required
      />
      <button type="submit" disabled={loading}>
        {loading ? 'Creating...' : 'Create Bot'}
      </button>
      {error && <p className="error">{error}</p>}
      {success && <p className="success">Bot created successfully! Redirecting...</p>}
    </form>
  );
}

// ==================== Pattern 5: Data Comparison ====================

/**
 * Backtest Comparison Component
 * Shows how to compare multiple items and display side-by-side
 */
export function BacktestComparisonComponent({
  backtestIds,
}: {
  backtestIds: string[];
}) {
  const [comparison, setComparison] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchComparison = async () => {
      try {
        const result = await apiClient.compareBacktests(backtestIds, [
          'total_return',
          'sharpe_ratio',
          'max_drawdown',
          'win_rate',
          'profit_factor',
        ]);
        setComparison(result);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchComparison();
  }, [backtestIds]);

  if (loading) return <div>Loading comparison...</div>;
  if (error) return <div className="error">Error: {error}</div>;
  if (!comparison) return <div>No comparison data</div>;

  return (
    <div className="comparison-table">
      <h2>Backtest Comparison</h2>
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            {comparison.comparison.map((item: any) => (
              <th key={item.run_id}>{item.run_id}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Total Return</td>
            {comparison.comparison.map((item: any) => (
              <td
                key={item.run_id}
                className={item.total_return >= 0 ? 'profit' : 'loss'}
              >
                {item.total_return.toFixed(2)}%
              </td>
            ))}
          </tr>
          <tr>
            <td>Sharpe Ratio</td>
            {comparison.comparison.map((item: any) => (
              <td key={item.run_id}>{item.sharpe_ratio.toFixed(2)}</td>
            ))}
          </tr>
          <tr>
            <td>Max Drawdown</td>
            {comparison.comparison.map((item: any) => (
              <td key={item.run_id} className="loss">
                {item.max_drawdown.toFixed(2)}%
              </td>
            ))}
          </tr>
          <tr>
            <td>Win Rate</td>
            {comparison.comparison.map((item: any) => (
              <td key={item.run_id}>
                {(item.win_rate * 100).toFixed(1)}%
              </td>
            ))}
          </tr>
          <tr>
            <td>Profit Factor</td>
            {comparison.comparison.map((item: any) => (
              <td key={item.run_id}>{item.profit_factor.toFixed(2)}</td>
            ))}
          </tr>
        </tbody>
      </table>

      <div className="best-metrics">
        <h3>Best Performers</h3>
        {Object.entries(comparison.best).map(([metric, run_id]) => (
          <p key={metric}>
            <strong>{metric}:</strong> {run_id}
          </p>
        ))}
      </div>
    </div>
  );
}

// ==================== Pattern 6: Polling for Status ====================

/**
 * Backtest Progress Component
 * Demonstrates polling for long-running operations
 */
export function BacktestProgressComponent({ runId }: { runId: string }) {
  const [progress, setProgress] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let intervalId: NodeJS.Timer | null = null;
    let isMounted = true;

    const fetchProgress = async () => {
      try {
        const status = await apiClient.getBacktestStatus(runId);
        
        if (isMounted) {
          setProgress(status);
          setLoading(false);

          // Stop polling if backtest is completed or failed
          if (['COMPLETED', 'FAILED', 'CANCELLED'].includes(status.status)) {
            if (intervalId) clearInterval(intervalId);
          }
        }
      } catch (err) {
        console.error('Failed to fetch progress:', err);
      }
    };

    // Fetch immediately
    fetchProgress();

    // Then poll every 2 seconds
    intervalId = setInterval(fetchProgress, 2000);

    return () => {
      isMounted = false;
      if (intervalId) clearInterval(intervalId);
    };
  }, [runId]);

  if (loading) return <div>Loading...</div>;
  if (!progress) return <div>No progress data</div>;

  const isCompleted = ['COMPLETED', 'FAILED', 'CANCELLED'].includes(
    progress.status
  );

  return (
    <div className="progress-container">
      <h2>Backtest Progress: {runId}</h2>
      
      <div className="progress-bar">
        <div
          className="progress-fill"
          style={{
            width: `${progress.progress_percent}%`,
            backgroundColor: isCompleted
              ? progress.status === 'COMPLETED'
                ? 'green'
                : 'red'
              : 'blue',
          }}
        />
      </div>

      <div className="progress-details">
        <p>
          <strong>Status:</strong> {progress.status}
        </p>
        <p>
          <strong>Progress:</strong> {progress.progress_percent}%
        </p>
        <p>
          <strong>Trades:</strong> {progress.trades_completed} /
          {progress.trades_total}
        </p>
        <p>
          <strong>Current Date:</strong> {progress.current_date}
        </p>
        {!isCompleted && (
          <p>
            <strong>Estimated Time:</strong>{' '}
            {Math.ceil(progress.estimated_completion_seconds / 60)} min
          </p>
        )}
      </div>
    </div>
  );
}

// ==================== Pattern 7: Error Recovery ====================

/**
 * Component with automatic retry logic
 * Shows best practices for handling transient failures
 */
export function ResilientDataFetchComponent({
  instanceId,
}: {
  instanceId: string;
}) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retries, setRetries] = useState(0);

  const MAX_RETRIES = 3;
  const RETRY_DELAY = 2000; // 2 seconds

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const result = await apiClient.getBotStats(instanceId);
      setData(result);
      setRetries(0);
    } catch (err: any) {
      // Check if error is retryable
      const isRetryable =
        err.response?.status >= 500 || err.code === 'ECONNABORTED';

      if (isRetryable && retries < MAX_RETRIES) {
        setRetries((prev) => prev + 1);
        setTimeout(fetchData, RETRY_DELAY);
      } else {
        setError(
          err.response?.data?.message || 'Failed to fetch data after retries'
        );
      }
    } finally {
      setLoading(false);
    }
  }, [instanceId, retries]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) return <div>Loading...</div>;
  if (error) {
    return (
      <div className="error">
        <p>{error}</p>
        <button onClick={() => setRetries(0) || fetchData()}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div>
      <h2>Bot Statistics</h2>
      {data && (
        <div>
          <p>Total Trades: {data.total_trades}</p>
          <p>Win Rate: {(data.win_rate * 100).toFixed(1)}%</p>
          <p>Total P&L: ${data.total_pnl.toFixed(2)}</p>
        </div>
      )}
    </div>
  );
}

// ==================== Pattern 8: Custom Hook for API Calls ====================

/**
 * Reusable Hook for simplified API calls
 * Demonstrates how to create custom hooks for common patterns
 */
function useAsyncData<T>(
  fetchFn: () => Promise<T>,
  dependencies: any[] = []
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    try {
      setLoading(true);
      const result = await fetchFn();
      setData(result);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [fetchFn]);

  useEffect(() => {
    refetch();
  }, dependencies);

  return { data, loading, error, refetch };
}

/**
 * Example usage of custom hook
 */
export function ExampleWithCustomHook({ instanceId }: { instanceId: string }) {
  const { data: stats, loading, error, refetch } = useAsyncData(
    () => apiClient.getBotStats(instanceId),
    [instanceId]
  );

  if (loading) return <div>Loading stats...</div>;
  if (error) {
    return (
      <div className="error">
        <p>{error}</p>
        <button onClick={refetch}>Retry</button>
      </div>
    );
  }

  return (
    <div>
      <h2>Stats for {instanceId}</h2>
      {stats && (
        <div>
          <p>Trades: {stats.total_trades}</p>
          <p>P&L: ${stats.total_pnl.toFixed(2)}</p>
          <button onClick={refetch}>Refresh</button>
        </div>
      )}
    </div>
  );
}
