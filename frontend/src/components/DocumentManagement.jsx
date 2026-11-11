import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';

export const DocumentManagement = ({ onNavigate }) => {
  const { token, authFetch, API_BASE_URL } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [chunkingMethod, setChunkingMethod] = useState('recursive');
  const fileInputRef = useRef(null);

  const fetchDocuments = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await authFetch(`${API_BASE_URL}/documents`, {
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (res.status === 403) {
        throw new Error('Access denied. Administrator privileges are required.');
      }
      if (!res.ok) {
        throw new Error(`Failed to load documents (${res.status})`);
      }

      const data = await res.json();
      setDocuments(data);
    } catch (err) {
      setError(err.message || 'Error fetching documents.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, [token]);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const validExtensions = ['.pdf', '.docx', '.txt'];
    const hasValidExt = validExtensions.some((ext) => file.name.toLowerCase().endsWith(ext));

    if (!hasValidExt) {
      setError('Please select a valid PDF, DOCX, or TXT file.');
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      setError('File size exceeds the 50MB limit.');
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    setError(null);
    setSelectedFile(file);
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!selectedFile) {
      setError('Please choose a file to upload.');
      return;
    }

    setUploading(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('chunking_method', chunkingMethod);

      const res = await authFetch(`${API_BASE_URL}/documents/upload`, {
        method: 'POST',
        body: formData,
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || `Upload failed with status ${res.status}`);
      }

      setSuccessMsg(`Successfully uploaded "${data.filename}" (${data.chunk_count} chunks processed).`);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      fetchDocuments();
    } catch (err) {
      setError(err.message || 'An error occurred during upload.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-5 border-b border-slate-200 gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900">
            Document Management
          </h1>
          <p className="text-xs sm:text-sm text-slate-600 mt-0.5">
            Upload and manage university policy documents and guidelines.
          </p>
        </div>

        <button
          onClick={fetchDocuments}
          disabled={loading}
          className="inline-flex items-center px-3.5 py-2 text-xs font-semibold rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 shadow-xs transition-colors disabled:opacity-50 self-start sm:self-auto"
        >
          <svg className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh
        </button>
      </div>

      {/* Notifications */}
      {error && (
        <div className="mt-4 p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs sm:text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-xs font-bold text-red-700 hover:text-red-900 ml-2">
            &times;
          </button>
        </div>
      )}

      {successMsg && (
        <div className="mt-4 p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs sm:text-sm flex items-center justify-between">
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-xs font-bold text-emerald-800 hover:text-emerald-900 ml-2">
            &times;
          </button>
        </div>
      )}

      {/* Upload Form Box */}
      <div className="mt-5 p-5 bg-white rounded-xl border border-slate-200 shadow-xs">
        <h2 className="text-sm sm:text-base font-bold text-slate-900 mb-1">Upload Document</h2>
        <p className="text-xs text-slate-500 mb-4">
          Select an academic handbook or policy document (.pdf, .docx, .txt).
        </p>

        <form onSubmit={handleUpload} className="space-y-3.5">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {/* File Input */}
            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                Document File
              </label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={handleFileChange}
                disabled={uploading}
                className="w-full text-xs text-slate-500 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 border border-slate-300 rounded-lg p-1 focus:outline-none"
              />
            </div>

            {/* Chunking Method Selector */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                Strategy
              </label>
              <select
                value={chunkingMethod}
                onChange={(e) => setChunkingMethod(e.target.value)}
                disabled={uploading}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs font-medium focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 bg-white"
              >
                <option value="recursive">Recursive Character</option>
                <option value="fixed">Fixed-Size Chunks</option>
                <option value="semantic">Semantic</option>
              </select>
            </div>
          </div>

          <div className="flex items-center justify-between pt-1">
            <span className="text-xs text-slate-400">
              {selectedFile ? `${selectedFile.name} (${(selectedFile.size / 1024).toFixed(1)} KB)` : 'Max file size: 50MB'}
            </span>

            <button
              type="submit"
              disabled={uploading || !selectedFile}
              className="inline-flex items-center px-4 py-2 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 shadow-xs transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {uploading && (
                <svg className="animate-spin -ml-1 mr-2 h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              )}
              <span>{uploading ? 'Processing...' : 'Upload Document'}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Documents Table */}
      <div className="mt-6 bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-sm sm:text-base font-bold text-slate-900">Document Corpus</h2>
          <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
            {documents.length} Files
          </span>
        </div>

        {loading ? (
          <div className="p-10 text-center text-slate-500 text-xs flex items-center justify-center space-x-2">
            <svg className="animate-spin h-4 w-4 text-blue-600" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>Loading documents...</span>
          </div>
        ) : documents.length === 0 ? (
          <div className="p-10 text-center">
            <p className="text-xs sm:text-sm font-semibold text-slate-700">No documents uploaded yet.</p>
            <p className="text-xs text-slate-400 mt-1">Upload a policy document above to get started.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 font-semibold uppercase tracking-wider border-b border-slate-200">
                <tr>
                  <th className="py-2.5 px-4">Document</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Chunks</th>
                  <th className="py-2.5 px-3">Version</th>
                  <th className="py-2.5 px-4">Uploaded</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-50 transition-colors">
                    <td className="py-3 px-4 font-semibold text-slate-900 flex items-center space-x-2.5">
                      <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center font-bold text-[10px] flex-shrink-0">
                        {doc.filename.endsWith('.pdf') ? 'PDF' : doc.filename.endsWith('.docx') ? 'DOC' : 'TXT'}
                      </div>
                      <div className="truncate max-w-sm">
                        <div className="font-semibold text-slate-900 truncate">{doc.filename}</div>
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                        doc.status === 'indexed'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-amber-50 text-amber-700 border border-amber-200'
                      }`}>
                        {doc.status}
                      </span>
                    </td>
                    <td className="py-3 px-3 font-mono">{doc.chunk_count}</td>
                    <td className="py-3 px-3 font-mono text-slate-500">{doc.version || 'v1.0'}</td>
                    <td className="py-3 px-4 text-slate-500">
                      {new Date(doc.upload_date).toLocaleDateString()}
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
