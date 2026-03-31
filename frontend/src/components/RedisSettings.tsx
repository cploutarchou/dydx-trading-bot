import { AxiosError } from 'axios';
import { AlertCircle, Check, RefreshCw, Trash2, X } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import api from '../api';

interface RedisSettings {
  id: number;
  enabled: boolean;
  host: string;
  port: number;
  database: number;
  password: string | null;
  ssl: boolean;
  timeout: number;
  max_connections: number;
  cache_ttl_seconds: number;
  cache_backtest_results: boolean;
  cache_market_data: boolean;
  cache_analysis_results: boolean;
  last_connection_test: string | null;
  last_connection_status: string;
  total_cache_hits: number;
  total_cache_misses: number;
}

interface ConnectionStatus {
  connected: boolean;
  enabled: boolean;
  host?: string;
  port?: number;
  db?: number;
  redis_version?: string;
  uptime_seconds?: number;
  connected_clients?: number;
  used_memory_mb?: number;
  total_system_memory_mb?: number;
  operations_per_sec?: number;
  message?: string;
}

interface CacheStats {
  enabled: boolean;
  total_keys?: number;
  hits?: number;
  misses?: number;
  hit_rate?: number;
  evictions?: number;
  memory_used_mb?: number;
  error?: string;
}

interface RedisStatusPayload {
  settings: RedisSettings | null;
  connection: ConnectionStatus | null;
  cache_stats: CacheStats | null;
}

const RedisSettings: React.FC = () => {
  const [settings, setSettings] = useState<RedisSettings | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus | null>(null);
  const [cacheStats, setCacheStats] = useState<CacheStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testingConnection, setTestingConnection] = useState(false);
  const [flushingCache, setFlushingCache] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editedSettings, setEditedSettings] = useState<Partial<RedisSettings>>({});

  useEffect(() => {
    fetchRedisStatus();
  }, []);

  const fetchRedisStatus = async () => {
    try {
      setLoading(true);
      const response = await api.getRedisStatus();

      if (response.success && response.data) {
        const data = response.data as unknown as RedisStatusPayload;
        setSettings(data.settings || null);
        setConnectionStatus(data.connection || null);
        setCacheStats(data.cache_stats || null);
      }
    } catch (err) {
      const axiosError = err as AxiosError<{ message?: string }>;
      setError(axiosError.message || 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  const handleTestConnection = async () => {
    try {
      setTestingConnection(true);
      const response = await api.testRedisConnection();

      if (response.success && response.data) {
        setConnectionStatus(response.data as unknown as ConnectionStatus);
      } else {
        setError(response.message || 'Connection test failed');
      }
    } catch (err) {
      const axiosError = err as AxiosError<{ message?: string }>;
      setError(axiosError.message || 'Connection test failed');
    } finally {
      setTestingConnection(false);
    }
  };

  const handleToggleRedis = async () => {
    try {
      const response = await api.toggleRedis(!settings?.enabled);

      if (response.success && response.data) {
        setSettings(response.data as unknown as RedisSettings);
      } else {
        setError(response.message || 'Failed to toggle Redis');
      }
    } catch (err) {
      const axiosError = err as AxiosError<{ message?: string }>;
      setError(axiosError.message || 'Failed to toggle Redis');
    }
  };

  const handleFlushCache = async () => {
    if (!window.confirm('Are you sure? This will clear all Redis cache data.')) {
      return;
    }

    try {
      setFlushingCache(true);
      const response = await api.flushRedis();

      if (response.success) {
        setCacheStats({ enabled: true, total_keys: 0 });
      } else {
        setError(response.message || 'Failed to flush cache');
      }
    } catch (err) {
      const axiosError = err as AxiosError<{ message?: string }>;
      setError(axiosError.message || 'Failed to flush cache');
    } finally {
      setFlushingCache(false);
    }
  };

  const handleSaveSettings = async () => {
    try {
      const updates: Record<string, unknown> = {};
      Object.entries(editedSettings).forEach(([key, value]) => {
        updates[`redis.${key}`] = value;
      });

      const updateResponse = await api.updateSettings(updates);

      if (!updateResponse.success) {
        setError(updateResponse.message || 'Failed to save settings');
        return;
      }

      const response = await api.getRedisSettings();

      if (response.success && response.data) {
        setSettings(response.data as unknown as RedisSettings);
        setIsEditing(false);
        setError(null);
      } else {
        setError(response.message || 'Failed to save settings');
      }
    } catch (err) {
      const axiosError = err as AxiosError<{ message?: string }>;
      setError(axiosError.message || 'Failed to save settings');
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6 bg-slate-900 rounded-lg">
      <h1 className="text-3xl font-bold text-white">Redis Cache Settings</h1>

      {error && (
        <div className="bg-red-900/20 border border-red-500 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div className="text-red-200">{error}</div>
        </div>
      )}

      {/* Connection Status Card */}
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-white">Connection Status</h2>
          <button
            onClick={handleTestConnection}
            disabled={testingConnection}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${testingConnection ? 'animate-spin' : ''}`} />
            Test Connection
          </button>
        </div>

        {connectionStatus && (
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
              <span className="text-slate-300">Status:</span>
              <div className="flex items-center gap-2">
                {connectionStatus.connected ? (
                  <>
                    <Check className="w-5 h-5 text-green-400" />
                    <span className="text-green-400 font-semibold">Connected</span>
                  </>
                ) : (
                  <>
                    <X className="w-5 h-5 text-red-400" />
                    <span className="text-red-400 font-semibold">Disconnected</span>
                  </>
                )}
              </div>
            </div>

            {connectionStatus.connected && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 bg-slate-700/50 rounded-lg">
                    <p className="text-slate-400 text-sm">Redis Version</p>
                    <p className="text-white font-mono">
                      {connectionStatus.redis_version || 'N/A'}
                    </p>
                  </div>
                  <div className="p-3 bg-slate-700/50 rounded-lg">
                    <p className="text-slate-400 text-sm">Uptime</p>
                    <p className="text-white font-mono">
                      {connectionStatus.uptime_seconds
                        ? `${Math.floor(connectionStatus.uptime_seconds / 3600)}h`
                        : 'N/A'}
                    </p>
                  </div>
                  <div className="p-3 bg-slate-700/50 rounded-lg">
                    <p className="text-slate-400 text-sm">Connected Clients</p>
                    <p className="text-white font-mono">
                      {connectionStatus.connected_clients || 0}
                    </p>
                  </div>
                  <div className="p-3 bg-slate-700/50 rounded-lg">
                    <p className="text-slate-400 text-sm">Memory Used</p>
                    <p className="text-white font-mono">{connectionStatus.used_memory_mb}MB</p>
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Enable/Disable Redis */}
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-white">Enable Redis</h2>
            <p className="text-slate-400 text-sm mt-1">Toggle Redis caching functionality on/off</p>
          </div>
          <button
            onClick={handleToggleRedis}
            className={`relative inline-flex h-8 w-14 rounded-full transition ${
              settings?.enabled
                ? 'bg-green-600 hover:bg-green-700'
                : 'bg-slate-600 hover:bg-slate-700'
            }`}
          >
            <span
              className={`inline-block h-7 w-7 transform rounded-full bg-white transition ${
                settings?.enabled ? 'translate-x-7' : 'translate-x-0'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Settings Form */}
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-white">Configuration</h2>
          {!isEditing && (
            <button
              onClick={() => {
                setIsEditing(true);
                setEditedSettings(settings || {});
              }}
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition"
            >
              Edit
            </button>
          )}
        </div>

        {isEditing ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-slate-300 text-sm font-medium mb-2">Host</label>
                <input
                  type="text"
                  value={editedSettings.host || ''}
                  onChange={(e) =>
                    setEditedSettings({
                      ...editedSettings,
                      host: e.target.value,
                    })
                  }
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-slate-300 text-sm font-medium mb-2">Port</label>
                <input
                  type="number"
                  value={editedSettings.port || ''}
                  onChange={(e) =>
                    setEditedSettings({
                      ...editedSettings,
                      port: parseInt(e.target.value),
                    })
                  }
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-slate-300 text-sm font-medium mb-2">Database</label>
                <input
                  type="number"
                  value={editedSettings.database || ''}
                  onChange={(e) =>
                    setEditedSettings({
                      ...editedSettings,
                      database: parseInt(e.target.value),
                    })
                  }
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="block text-slate-300 text-sm font-medium mb-2">
                  Timeout (seconds)
                </label>
                <input
                  type="number"
                  value={editedSettings.timeout || ''}
                  onChange={(e) =>
                    setEditedSettings({
                      ...editedSettings,
                      timeout: parseInt(e.target.value),
                    })
                  }
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-slate-300 text-sm font-medium mb-2">Password</label>
                <input
                  type="password"
                  value={editedSettings.password || ''}
                  onChange={(e) =>
                    setEditedSettings({
                      ...editedSettings,
                      password: e.target.value,
                    })
                  }
                  placeholder="Leave empty for no password"
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white"
                />
              </div>
            </div>

            {/* Cache TTL */}
            <div>
              <label className="block text-slate-300 text-sm font-medium mb-2">
                Cache TTL (seconds)
              </label>
              <input
                type="number"
                value={editedSettings.cache_ttl_seconds || ''}
                onChange={(e) =>
                  setEditedSettings({
                    ...editedSettings,
                    cache_ttl_seconds: parseInt(e.target.value),
                  })
                }
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white"
              />
              <p className="text-slate-400 text-xs mt-1">Default: 24 hours (86400 seconds)</p>
            </div>

            {/* Cache Features */}
            <div className="bg-slate-700/50 rounded-lg p-4 space-y-3">
              <h3 className="text-sm font-medium text-slate-200">Cache Features</h3>
              {[
                {
                  key: 'cache_backtest_results',
                  label: 'Cache Backtest Results',
                },
                { key: 'cache_market_data', label: 'Cache Market Data' },
                {
                  key: 'cache_analysis_results',
                  label: 'Cache Analysis Results',
                },
              ].map((feature) => (
                <label key={feature.key} className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={editedSettings[feature.key as keyof Partial<RedisSettings>] as boolean}
                    onChange={(e) =>
                      setEditedSettings({
                        ...editedSettings,
                        [feature.key]: e.target.checked,
                      })
                    }
                    className="rounded w-4 h-4"
                  />
                  <span className="text-slate-300 text-sm">{feature.label}</span>
                </label>
              ))}
            </div>

            {/* Buttons */}
            <div className="flex gap-3 pt-4">
              <button
                onClick={handleSaveSettings}
                className="flex-1 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg transition font-medium"
              >
                Save Changes
              </button>
              <button
                onClick={() => setIsEditing(false)}
                className="flex-1 bg-slate-600 hover:bg-slate-700 text-white px-4 py-2 rounded-lg transition font-medium"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 bg-slate-700/50 rounded-lg">
                <p className="text-slate-400 text-sm">Host</p>
                <p className="text-white font-mono">{settings?.host}</p>
              </div>
              <div className="p-3 bg-slate-700/50 rounded-lg">
                <p className="text-slate-400 text-sm">Port</p>
                <p className="text-white font-mono">{settings?.port}</p>
              </div>
              <div className="p-3 bg-slate-700/50 rounded-lg">
                <p className="text-slate-400 text-sm">Database</p>
                <p className="text-white font-mono">{settings?.database}</p>
              </div>
              <div className="p-3 bg-slate-700/50 rounded-lg">
                <p className="text-slate-400 text-sm">Timeout</p>
                <p className="text-white font-mono">{settings?.timeout}s</p>
              </div>
            </div>
            <div className="p-3 bg-slate-700/50 rounded-lg">
              <p className="text-slate-400 text-sm">Cache TTL</p>
              <p className="text-white font-mono">
                {settings?.cache_ttl_seconds}s (
                {Math.floor((settings?.cache_ttl_seconds || 0) / 3600)}h)
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Cache Statistics */}
      {cacheStats && cacheStats.enabled && (
        <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-white">Cache Statistics</h2>
            <button
              onClick={handleFlushCache}
              disabled={flushingCache}
              className="flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg transition disabled:opacity-50"
            >
              <Trash2 className="w-4 h-4" />
              Flush Cache
            </button>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 bg-slate-700/50 rounded-lg">
              <p className="text-slate-400 text-sm">Total Keys</p>
              <p className="text-2xl font-bold text-green-400">{cacheStats.total_keys || 0}</p>
            </div>
            <div className="p-4 bg-slate-700/50 rounded-lg">
              <p className="text-slate-400 text-sm">Cache Hit Rate</p>
              <p className="text-2xl font-bold text-blue-400">
                {((cacheStats.hit_rate || 0) * 100).toFixed(2)}%
              </p>
            </div>
            <div className="p-4 bg-slate-700/50 rounded-lg">
              <p className="text-slate-400 text-sm">Memory Used</p>
              <p className="text-2xl font-bold text-purple-400">
                {(cacheStats.memory_used_mb || 0).toFixed(2)}MB
              </p>
            </div>
            <div className="p-4 bg-slate-700/50 rounded-lg">
              <p className="text-slate-400 text-sm">Evictions</p>
              <p className="text-2xl font-bold text-orange-400">{cacheStats.evictions || 0}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RedisSettings;
