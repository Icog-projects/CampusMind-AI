import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';

export const DocumentManagement = ({ onNavigate }) => {
  const { token, API_BASE_URL } = useAuth();
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
      const res = await fetch(`${API_BASE_URL}/documents`, {
        headers: {
          'Authorization': `Bearer ${token}`,
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
      setError(err.message || 'Error fetching documents from MySQL repository.');
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
      setError('Invalid file type. Only PDF (.pdf), Word (.docx), and Plain Text (.txt) are supported per SRS FR-08.');
      setSelectedFile(null);
      return;
    }

    setError(null);
    setSelectedFile(file);
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!selectedFile) {
      setError('Please select a PDF, DOCX, or TXT file to upload.');
      return;
    }

    setUploading(true);
    setError(null);
    setSuccessMsg(null);

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('chunking_method', chunkingMethod);

    try {
      const res = await fetch(`${API_BASE_URL}/documents/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          // Notice: Content-Type is left empty so browser sets multipart boundary automatically
        },
        body: formData,
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || `Upload failed with status ${res.status}`);
      }

      setSuccessMsg(
        `Successfully ingested "${data.filename}". Created ${data.chunk_count} chunks, updated Qdrant & BM25 index, and invalidated stale Redis cache.`
      );
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      fetchDocuments();
    } catch (err) {
      setError(err.message || 'An error occurred during document ingestion.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-6 border-b border-slate-200 gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-800 uppercase tracking-wider">
              Document Pipeline
            </span>
            <span className="text-slate-400">&bull;</span>
            <span className="text-xs text-slate-500">SRS v1.2 FR-08, FR-09, FR-10, FR-16</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-1">
            Corpus Document Management
          </h1>
          <p className="text-sm text-slate-600 mt-0.5">
            Upload institutional policy files, extract text, synchronize Qdrant & BM25 indices, and manage corpus versioning.
          </p>
        </div>

        <button
          onClick={fetchDocuments}
          disabled={loading}
          className="inline-flex items-center px-3.5 py-2 text-xs font-semibold rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 shadow-sm transition-colors disabled:opacity-50 self-start sm:self-auto"
        >
          <svg className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh Documents
        </button>
      </div>

      {/* Notifications */}
      {error && (
        <div className="mt-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <svg className="w-5 h-5 text-red-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-xs font-bold text-red-700 hover:text-red-900">
            &times;
          </button>
        </div>
      )}

      {successMsg && (
        <div className="mt-6 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <svg className="w-5 h-5 text-emerald-600 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-xs font-bold text-emerald-800 hover:text-emerald-900">
            &times;
          </button>
        </div>
      )}

      {/* Upload Form Box */}
      <div className="mt-6 p-6 bg-white rounded-2xl border border-slate-200 shadow-sm">
        <h2 className="text-base font-bold text-slate-900 mb-1">Ingest New University Document</h2>
        <p className="text-xs text-slate-500 mb-5">
          Select an academic handbook or guideline. The file will be extracted, split into overlapping chunks, embedded via BGE-small, and indexed in Qdrant & BM25.
        </p>

        <form onSubmit={handleUpload} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* File Input */}
            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                Document File (.PDF, .DOCX, .TXT)
              </label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={handleFileChange}
                disabled={uploading}
                className="w-full text-xs text-slate-500 file:mr-4 file:py-2.5 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 border border-slate-300 rounded-xl p-1.5 focus:outline-none"
              />
            </div>

            {/* Chunking Method Selector */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                Chunking Strategy
              </label>
              <select
                value={chunkingMethod}
                onChange={(e) => setChunkingMethod(e.target.value)}
                disabled={uploading}
                className="w-full px-3 py-2.5 rounded-xl border border-slate-300 text-xs font-medium focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 bg-white"
              >
                <option value="recursive">Recursive Character (Recommended)</option>
                <option value="fixed">Fixed-Size Chunks</option>
                <option value="semantic">Semantic (Header-Aware)</option>
              </select>
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            <span className="text-xs text-slate-400">
              {selectedFile ? `Selected: ${selectedFile.name} (${(selectedFile.size / 1024).toFixed(1)} KB)` : 'Max file size: 50MB'}
            </span>

            <button
              type="submit"
              disabled={uploading || !selectedFile}
              className="inline-flex items-center px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 shadow-md shadow-blue-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {uploading && (
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              )}
              <span>{uploading ? 'Extracting & Indexing...' : 'Upload and Index Document'}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Documents Table */}
      <div className="mt-8 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-900">Indexed Knowledge Base Corpus</h2>
            <p className="text-xs text-slate-500">All authoritative files currently active in RAG vector and keyword search</p>
          </div>
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 text-slate-700">
            {documents.length} Total Records
          </span>
        </div>

        {loading ? (
          <div className="p-12 text-center text-slate-500 text-sm flex items-center justify-center space-x-2">
            <svg className="animate-spin h-5 w-5 text-blue-600" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>Loading document corpus...</span>
          </div>
        ) : documents.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-sm font-semibold text-slate-700">No documents indexed in database.</p>
            <p className="text-xs text-slate-500 mt-1">Upload your first PDF or DOCX policy file above to build the corpus.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 font-semibold uppercase tracking-wider border-b border-slate-200">
                <tr>
                  <th className="py-3 px-6">Document Name</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Chunks</th>
                  <th className="py-3 px-4">KB Version</th>
                  <th className="py-3 px-4">Document ID</th>
                  <th className="py-3 px-6">Upload Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-4 px-6 font-semibold text-slate-900 flex items-center space-x-3">
                      <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center font-bold text-[11px] flex-shrink-0">
                        {doc.filename.endsWith('.pdf') ? 'PDF' : doc.filename.endsWith('.docx') ? 'DOC' : 'TXT'}
                      </div>
                      <div className="truncate max-w-sm">
                        <div className="font-semibold text-slate-900 truncate">{doc.filename}</div>
                        <div className="text-[11px] text-slate-400 font-mono truncate">{doc.file_path || 'Indexed directly'}</div>
                      </div>
                    </td>
                    <td className="py-4 px-4">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                        doc.status === 'indexed'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-amber-50 text-amber-700 border border-amber-200'
                      }`}>
                        {doc.status}
                      </span>
                    </td>
                    <td className="py-4 px-4 font-mono font-medium">{doc.chunk_count}</td>
                    <td className="py-4 px-4 font-mono text-slate-500">{doc.version || 'v1.0'}</td>
                    <td className="py-4 px-4 font-mono text-[11px] text-slate-400">
                      {doc.id.substring(0, 12)}...
                    </td>
                    <td className="py-4 px-6 text-slate-500">
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

