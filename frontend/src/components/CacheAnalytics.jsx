import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

export const CacheAnalytics = ({ onNavigate }) => {
  const { token, API_BASE_URL } = useAuth();
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
      setError(err.message || 'Error fetching Redis telemetry from backend.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    // Periodic refresh every 10 seconds for live monitoring
    const interval = setInterval(fetchMetrics, 10000);
    return () => clearInterval(interval);
  }, [token]);

  const totalQueries = metrics?.total_queries ?? 0;
  const hits = metrics?.hits ?? 0;
  const misses = metrics?.misses ?? 0;
  const hitRate = metrics?.hit_rate_pct ?? 0;
  const llmSaved = metrics?.llm_calls_avoided ?? 0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-6 border-b border-slate-200 gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-800 uppercase tracking-wider">
              Redis Telemetry
            </span>
            <span className="text-slate-400">&bull;</span>
            <span className="text-xs text-slate-500">SRS v1.2 FR-21, FR-22, FR-23</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-1">
            Redis Cache & Performance Analytics
          </h1>
          <p className="text-sm text-slate-600 mt-0.5">
            Monitor real-time semantic answer caching, hit-vs-miss telemetry, and avoided external LLM inference overhead.
          </p>
        </div>

        <button
          onClick={fetchMetrics}
          disabled={loading}
          className="inline-flex items-center px-3.5 py-2 text-xs font-semibold rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 shadow-sm transition-colors disabled:opacity-50 self-start sm:self-auto"
        >
          <svg className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh Live Metrics
        </button>
      </div>

      {error && (
        <div className="mt-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <svg className="w-5 h-5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{error}</span>
          </div>
          <button onClick={fetchMetrics} className="text-xs font-semibold underline hover:no-underline">
            Retry
          </button>
        </div>
      )}

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mt-6">
        {/* Metric 1: Total Questions Processed */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-500 uppercase tracking-wider">
            <span>Total Inquiries</span>
            <span className="p-2 rounded-xl bg-blue-50 text-blue-600">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
            </span>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-slate-900">{totalQueries}</span>
            <span className="text-xs text-slate-500">requests</span>
          </div>
          <p className="mt-2 text-xs text-slate-400">Total chat inquiries tracked</p>
        </div>

        {/* Metric 2: Cache Hits */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-500 uppercase tracking-wider">
            <span>Cache Hits</span>
            <span className="p-2 rounded-xl bg-emerald-50 text-emerald-600">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </span>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-slate-900">{hits}</span>
            <span className="text-xs font-medium text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">
              ~2ms latency
            </span>
          </div>
          <p className="mt-2 text-xs text-slate-400">Served instantly without LLM generation</p>
        </div>

        {/* Metric 3: Cache Misses */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-500 uppercase tracking-wider">
            <span>Cache Misses</span>
            <span className="p-2 rounded-xl bg-amber-50 text-amber-600">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </span>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-slate-900">{misses}</span>
            <span className="text-xs text-slate-500 font-medium">Full RAG Pipeline</span>
          </div>
          <p className="mt-2 text-xs text-slate-400">Triggered Qdrant + BM25 + Groq</p>
        </div>

        {/* Metric 4: Avoided LLM Calls */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-500 uppercase tracking-wider">
            <span>Calls Avoided</span>
            <span className="p-2 rounded-xl bg-indigo-50 text-indigo-600">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </span>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-slate-900">{llmSaved}</span>
            <span className="text-xs font-medium text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">
              100% saved
            </span>
          </div>
          <p className="mt-2 text-xs text-slate-400">Zero inference cost on cache hits</p>
        </div>
      </div>

      {/* Visual Analytics & Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8">
        {/* Hit Ratio Visual Card */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <h2 className="text-base font-bold text-slate-900">Cache Hit Ratio Efficiency</h2>
          <p className="text-xs text-slate-500 mb-6">Percentage of student queries served directly from Redis memory</p>

          <div className="space-y-4">
            <div>
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

            <div className="grid grid-cols-2 gap-4 pt-4 border-t border-slate-100">
              <div className="p-3 bg-emerald-50/50 rounded-xl border border-emerald-100">
                <div className="text-[11px] font-semibold text-emerald-800 uppercase">Hits (Fast Path)</div>
                <div className="text-xl font-bold text-emerald-900 mt-0.5">{hits}</div>
                <div className="text-[10px] text-emerald-700 mt-1">Bypasses Qdrant, BM25, and LLM</div>
              </div>

              <div className="p-3 bg-amber-50/50 rounded-xl border border-amber-100">
                <div className="text-[11px] font-semibold text-amber-800 uppercase">Misses (Slow Path)</div>
                <div className="text-xl font-bold text-amber-900 mt-0.5">{misses}</div>
                <div className="text-[10px] text-amber-700 mt-1">Executes Hybrid Search & Synthesis</div>
              </div>
            </div>
          </div>
        </div>

        {/* Cache Invalidation & Architecture Rules */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <h2 className="text-base font-bold text-slate-900">Redis Architecture & Invalidation (SRS v1.2)</h2>
          <p className="text-xs text-slate-500 mb-4">Underlying mechanisms guaranteeing strict policy compliance</p>

          <div className="space-y-3 text-xs text-slate-700">
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 flex items-start space-x-2.5">
              <span className="font-bold text-blue-600 mt-0.5">&bull;</span>
              <div>
                <strong>Scope-Isolated Keys:</strong> Cache keys combine knowledge-base version, user role scope (`public` vs `internal`), and normalized question hash.
              </div>
            </div>

            <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 flex items-start space-x-2.5">
              <span className="font-bold text-blue-600 mt-0.5">&bull;</span>
              <div>
                <strong>Knowledge Base Invalidation:</strong> Whenever an admin uploads a new document, the system automatically invalidates outdated Redis entries to eliminate policy staleness.
              </div>
            </div>

            <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 flex items-start space-x-2.5">
              <span className="font-bold text-blue-600 mt-0.5">&bull;</span>
              <div>
                <strong>Persistence Parity:</strong> Even on cache hits, every question-and-answer interaction is faithfully persisted to MySQL with `is_cache_hit=True` for auditing.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

