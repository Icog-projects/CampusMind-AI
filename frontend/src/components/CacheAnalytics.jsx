import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

export const CacheAnalytics = ({ onNavigate }) => {
  const { token, API_BASE_URL } = useAuth();
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [updatingPolicy, setUpdatingPolicy] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  const fetchMetrics = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/metrics/cache`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (res.status === 403) {
        throw new Error('Access denied. Administrator privileges required.');
      }
      if (!res.ok) {
        throw new Error(`Failed to load cache metrics (${res.status})`);
      }

      const data = await res.json();
      setMetrics(data);
    } catch (err) {
      setError(err.message || 'Error fetching metrics.');
    } finally {
      setLoading(false);
    }
  };

  const handlePolicyChange = async (newPolicy) => {
    setUpdatingPolicy(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await fetch(`${API_BASE_URL}/metrics/cache/policy`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ policy: newPolicy }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Failed to update eviction policy (${res.status})`);
      }

      const data = await res.json();
      setSuccessMsg(`Eviction policy successfully updated to ${newPolicy}.`);
      fetchMetrics();
    } catch (err) {
      setError(err.message || 'Error updating eviction policy.');
    } finally {
      setUpdatingPolicy(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 10000);
    return () => clearInterval(interval);
  }, [token]);

  const totalQueries = metrics?.total_queries ?? 0;
  const hits = metrics?.hits ?? 0;
  const misses = metrics?.misses ?? 0;
  const hitRate = metrics?.hit_rate_pct ?? 0;
  const llmSaved = metrics?.llm_calls_avoided ?? 0;
  const ttlSeconds = metrics?.ttl_seconds ?? 1800;
  const usedMemory = metrics?.used_memory_human ?? 'N/A';
  const maxMemory = metrics?.maxmemory_human ?? 'N/A';
  const currentPolicy = metrics?.live_policy || metrics?.configured_policy || 'allkeys-lru';

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-5 border-b border-slate-200 gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900">
            Cache Analytics
          </h1>
          <p className="text-xs sm:text-sm text-slate-600 mt-0.5">
            Query traffic, performance, and Redis memory eviction management.
          </p>
        </div>

        <button
          onClick={fetchMetrics}
          disabled={loading}
          className="inline-flex items-center px-3.5 py-2 text-xs font-semibold rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 shadow-xs transition-colors disabled:opacity-50 self-start sm:self-auto"
        >
          <svg className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh
        </button>
      </div>

      {error && (
        <div className="mt-4 p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs sm:text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-xs font-semibold underline hover:no-underline ml-2">
            Dismiss
          </button>
        </div>
      )}

      {successMsg && (
        <div className="mt-4 p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs sm:text-sm flex items-center justify-between">
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-xs font-semibold underline hover:no-underline ml-2">
            Dismiss
          </button>
        </div>
      )}

      {/* Primary KPI Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-5">
        {/* Metric 1: Total Queries */}
        <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-xs">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Total Inquiries
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-slate-900">{totalQueries}</span>
            <span className="text-xs text-slate-400">queries</span>
          </div>
        </div>

        {/* Metric 2: Cache Hits */}
        <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-xs">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Cache Hits
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-emerald-600">{hits}</span>
            <span className="text-xs text-emerald-700 font-medium bg-emerald-50 px-1.5 py-0.5 rounded">
              Fast Path
            </span>
          </div>
        </div>

        {/* Metric 3: Cache Misses */}
        <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-xs">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Cache Misses
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-amber-600">{misses}</span>
            <span className="text-xs text-slate-500">Direct Lookup</span>
          </div>
        </div>

        {/* Metric 4: Avoided LLM Calls */}
        <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-xs">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Calls Avoided
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-indigo-600">{llmSaved}</span>
            <span className="text-xs text-emerald-700 font-medium bg-emerald-50 px-1.5 py-0.5 rounded">
              Saved
            </span>
          </div>
        </div>
      </div>

      {/* Redis Configuration & Eviction Controls */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
        {/* Card 1: Hit Ratio Breakdown */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
          <div>
            <h2 className="text-sm sm:text-base font-bold text-slate-900 mb-1">Cache Hit Efficiency</h2>
            <p className="text-xs text-slate-500 mb-4">Percentage of student queries served directly from Redis</p>

            <div className="flex justify-between text-xs font-semibold text-slate-700 mb-1.5">
              <span>Hit Rate</span>
              <span>{hitRate}%</span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-3 overflow-hidden">
              <div
                className="bg-emerald-500 h-3 rounded-full transition-all duration-500"
                style={{ width: `${Math.min(Math.max(hitRate, 0), 100)}%` }}
              ></div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 pt-4 mt-4 border-t border-slate-100">
            <div className="p-3 bg-emerald-50/50 rounded-lg border border-emerald-100">
              <div className="text-[11px] font-semibold text-emerald-800 uppercase">Hits</div>
              <div className="text-lg font-bold text-emerald-900 mt-0.5">{hits}</div>
            </div>

            <div className="p-3 bg-amber-50/50 rounded-lg border border-amber-100">
              <div className="text-[11px] font-semibold text-amber-800 uppercase">Misses</div>
              <div className="text-lg font-bold text-amber-900 mt-0.5">{misses}</div>
            </div>
          </div>
        </div>

        {/* Card 2: Memory & Eviction Policy Management */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-sm sm:text-base font-bold text-slate-900">Redis Memory & Eviction</h2>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
              TTL: {ttlSeconds}s ({ttlSeconds / 60}m)
            </span>
          </div>
          <p className="text-xs text-slate-500 mb-4">
            Memory limits govern key eviction when capacity is reached, while TTL governs answer freshness.
          </p>

          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
              <div className="text-[11px] font-semibold text-slate-500 uppercase">Memory Used</div>
              <div className="text-base sm:text-lg font-bold text-slate-900 mt-0.5 font-mono">{usedMemory}</div>
            </div>
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
              <div className="text-[11px] font-semibold text-slate-500 uppercase">Memory Limit</div>
              <div className="text-base sm:text-lg font-bold text-slate-900 mt-0.5 font-mono">{maxMemory}</div>
            </div>
          </div>

          <div className="pt-3 border-t border-slate-100">
            <div className="text-xs font-semibold text-slate-700 mb-2 flex items-center justify-between">
              <span>Eviction Policy</span>
              <span className="font-mono text-[11px] px-2 py-0.5 bg-blue-50 text-blue-700 rounded font-semibold border border-blue-200">
                {currentPolicy}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 mt-2">
              <button
                type="button"
                onClick={() => handlePolicyChange('allkeys-lru')}
                disabled={updatingPolicy || currentPolicy === 'allkeys-lru'}
                className={`px-3 py-2 text-xs font-semibold rounded-lg border transition-all text-center ${currentPolicy === 'allkeys-lru'
                    ? 'bg-blue-600 text-white border-blue-600 shadow-xs cursor-default'
                    : 'bg-white hover:bg-slate-50 text-slate-700 border-slate-300'
                  }`}
              >
                LRU (Least Recently Used)
              </button>

              <button
                type="button"
                onClick={() => handlePolicyChange('allkeys-lfu')}
                disabled={updatingPolicy || currentPolicy === 'allkeys-lfu'}
                className={`px-3 py-2 text-xs font-semibold rounded-lg border transition-all text-center ${currentPolicy === 'allkeys-lfu'
                    ? 'bg-blue-600 text-white border-blue-600 shadow-xs cursor-default'
                    : 'bg-white hover:bg-slate-50 text-slate-700 border-slate-300'
                  }`}
              >
                LFU (Least Frequently Used)
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
