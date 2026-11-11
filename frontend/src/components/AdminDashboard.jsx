/**
 * Admin Dashboard Component
 * Displays system telemetry, corpus statistics, and cache performance metrics.
 */
import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

export const AdminDashboard = ({ onNavigate }) => {
  const { token, authFetch, API_BASE_URL } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [cacheMetrics, setCacheMetrics] = useState(null);
  const [systemHealth, setSystemHealth] = useState(null);

  /**
   * Fetches document counts, cache telemetry, and health statuses in parallel.
   */
  const fetchDashboardData = async () => {
    setLoading(true);
    setError(null);

    try {
      const headers = {
        'Content-Type': 'application/json',
      };

      // Parallel fetch for documents, cache metrics, and system health with auto-renewal authFetch
      const [docsRes, metricsRes, healthRes] = await Promise.all([
        authFetch(`${API_BASE_URL}/documents`, { headers }),
        authFetch(`${API_BASE_URL}/metrics/cache`, { headers }),
        fetch(`${API_BASE_URL}/health`),
      ]);

      if (docsRes.status === 403 || metricsRes.status === 403) {
        throw new Error('Administrative authorization required.');
      }

      const docsData = docsRes.ok ? await docsRes.json() : [];
      const metricsData = metricsRes.ok ? await metricsRes.json() : null;
      const healthData = healthRes.ok ? await healthRes.json() : null;

      setDocuments(docsData);
      setCacheMetrics(metricsData);
      setSystemHealth(healthData);
    } catch (err) {
      setError(err.message || 'Failed to load administrator dashboard data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, [token]);

  // Derived statistics from actual data
  const totalDocs = documents.length;
  const indexedDocs = documents.filter((d) => d.status === 'indexed').length;
  const totalChunks = documents.reduce((sum, d) => sum + (d.chunk_count || 0), 0);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-6 border-b border-slate-200 gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900">
            System Dashboard
          </h1>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={fetchDashboardData}
            disabled={loading}
            className="inline-flex items-center px-3.5 py-2 text-xs font-semibold rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 shadow-sm transition-colors disabled:opacity-50"
          >
            <svg className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
          <button
            onClick={() => onNavigate('documents')}
            className="inline-flex items-center px-4 py-2 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-700 text-white shadow-sm transition-colors"
          >
            <svg className="w-3.5 h-3.5 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Manage Documents
          </button>
        </div>
      </div>

      {error && (
        <div className="mt-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <svg className="w-5 h-5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{error}</span>
          </div>
          <button onClick={fetchDashboardData} className="text-xs font-semibold underline hover:no-underline">
            Retry
          </button>
        </div>
      )}

      {/* Main Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mt-6">
        {/* Card 1: Total Corpus Documents */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-sm hover:border-slate-300 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Documents</span>
            <span className="p-2 rounded-xl bg-blue-50 text-blue-600">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </span>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-slate-900">{loading ? '...' : totalDocs}</span>
            <span className="text-xs font-medium text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">
              {indexedDocs} indexed
            </span>
          </div>
        </div>

        {/* Card 2: Total Chunks */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-sm hover:border-slate-300 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Chunks</span>
            <span className="p-2 rounded-xl bg-indigo-50 text-indigo-600">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </span>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-slate-900">{loading ? '...' : totalChunks}</span>
          </div>
        </div>

        {/* Card 3: Cache Hit Rate */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-sm hover:border-slate-300 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Cache Hit Rate</span>
            <span className="p-2 rounded-xl bg-amber-50 text-amber-600">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </span>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-slate-900">
              {loading ? '...' : `${cacheMetrics?.hit_rate_pct ?? 0}%`}
            </span>
            <span className="text-xs text-slate-500 font-medium">
              {cacheMetrics?.hits ?? 0} / {cacheMetrics?.total_queries ?? 0} queries
            </span>
          </div>
        </div>

        {/* Card 4: Avoided LLM Calls */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-sm hover:border-slate-300 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Calls Avoided</span>
            <span className="p-2 rounded-xl bg-emerald-50 text-emerald-600">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </span>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-slate-900">
              {loading ? '...' : (cacheMetrics?.llm_calls_avoided ?? 0)}
            </span>
          </div>
        </div>
      </div>

      {/* Two Column Layout: Infrastructure Health + Quick Navigation */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-8">
        {/* Left Column (2 cols): System Infrastructure Health */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center justify-between pb-4 border-b border-slate-100">
            <div>
              <h2 className="text-base font-bold text-slate-900">Services & Infrastructure</h2>
            </div>
            <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${
              systemHealth?.status === 'healthy' 
                ? 'bg-emerald-100 text-emerald-800' 
                : 'bg-amber-100 text-amber-800'
            }`}>
              <span className={`w-2 h-2 rounded-full mr-1.5 ${
                systemHealth?.status === 'healthy' ? 'bg-emerald-600' : 'bg-amber-600'
              }`}></span>
              Status: {systemHealth?.status?.toUpperCase() || 'UNKNOWN'}
            </span>
          </div>

          <div className="divide-y divide-slate-100 mt-3">
            {/* MySQL */}
            <div className="py-3.5 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-700 flex items-center justify-center font-bold text-xs">
                  SQL
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-slate-800">MySQL Database</h3>
                  <p className="text-xs text-slate-500">
                    {systemHealth?.dependencies?.mysql?.details || 'Database connection'}
                  </p>
                </div>
              </div>
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                {systemHealth?.dependencies?.mysql?.status || 'Active'}
              </span>
            </div>

            {/* Redis */}
            <div className="py-3.5 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-9 h-9 rounded-xl bg-red-50 text-red-600 flex items-center justify-center font-bold text-xs">
                  RDS
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-slate-800">Redis Cache</h3>
                  <p className="text-xs text-slate-500">
                    {systemHealth?.dependencies?.redis?.details || 'Cache connection'}
                  </p>
                </div>
              </div>
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                {systemHealth?.dependencies?.redis?.status || 'Active'}
              </span>
            </div>

            {/* Qdrant */}
            <div className="py-3.5 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-9 h-9 rounded-xl bg-purple-50 text-purple-700 flex items-center justify-center font-bold text-xs">
                  QDR
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-slate-800">Qdrant Vector Database</h3>
                  <p className="text-xs text-slate-500">
                    {systemHealth?.dependencies?.qdrant?.details || 'Vector store connection'}
                  </p>
                </div>
              </div>
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                {systemHealth?.dependencies?.qdrant?.status || 'Active'}
              </span>
            </div>
          </div>
        </div>

        {/* Right Column (1 col): Navigation & Shortcuts */}
        <div className="space-y-4">
          {/* Document Management Card */}
          <div className="bg-gradient-to-br from-blue-50 to-indigo-50/50 rounded-2xl border border-blue-200/80 p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-blue-700 uppercase tracking-wider">Documents</span>
              <span className="text-xs font-semibold bg-white px-2 py-0.5 rounded-full text-blue-800 shadow-xs border border-blue-100">
                {totalDocs} files
              </span>
            </div>
            <h3 className="text-base font-extrabold text-slate-900 mt-2">Document Management</h3>
            <button
              onClick={() => onNavigate('documents')}
              className="mt-4 w-full py-2 px-3 text-xs font-bold rounded-xl text-white bg-blue-600 hover:bg-blue-700 shadow-sm transition-colors flex items-center justify-center space-x-1"
            >
              <span>Manage Documents</span>
              <span>&rarr;</span>
            </button>
          </div>

          {/* Redis Cache Analytics Card */}
          <div className="bg-gradient-to-br from-slate-50 to-slate-100 rounded-2xl border border-slate-200 p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">Cache</span>
              <span className="text-xs font-semibold bg-white px-2 py-0.5 rounded-full text-slate-700 shadow-xs border border-slate-200">
                {cacheMetrics?.hit_rate_pct ?? 0}%
              </span>
            </div>
            <h3 className="text-base font-extrabold text-slate-900 mt-2">Cache Analytics</h3>
            <button
              onClick={() => onNavigate('cache-analytics')}
              className="mt-4 w-full py-2 px-3 text-xs font-bold rounded-xl text-slate-800 bg-white hover:bg-slate-50 border border-slate-300 shadow-sm transition-colors flex items-center justify-center space-x-1"
            >
              <span>View Analytics</span>
              <span>&rarr;</span>
            </button>
          </div>
        </div>
      </div>

      {/* Recent Indexed Documents Preview */}
      <div className="mt-8 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-900">Recent Documents</h2>
          </div>
          <button
            onClick={() => onNavigate('documents')}
            className="text-xs font-semibold text-blue-600 hover:underline"
          >
            View all documents &rarr;
          </button>
        </div>

        {documents.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-500">
            No documents uploaded yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 font-semibold uppercase tracking-wider border-b border-slate-200">
                <tr>
                  <th className="py-3 px-6">Filename</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Chunks</th>
                  <th className="py-3 px-4">KB Version</th>
                  <th className="py-3 px-6">Uploaded Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {documents.slice(0, 5).map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3.5 px-6 font-semibold text-slate-900 flex items-center space-x-2">
                      <svg className="w-4 h-4 text-blue-600 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                      </svg>
                      <span className="truncate max-w-xs">{doc.filename}</span>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                        {doc.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-mono">{doc.chunk_count}</td>
                    <td className="py-3.5 px-4 font-mono text-slate-500">{doc.version || 'v1.0'}</td>
                    <td className="py-3.5 px-6 text-slate-500">
                      {new Date(doc.upload_date).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

