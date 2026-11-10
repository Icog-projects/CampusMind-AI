import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { MarkdownRenderer } from './MarkdownRenderer';

export const ChatPage = ({ onNavigate }) => {
  const { token, user, API_BASE_URL } = useAuth();
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputQuestion, setInputQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedCitation, setSelectedCitation] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  // Fetch user's conversation sessions
  const fetchSessions = async () => {
    setSessionsLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/chat/sessions`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      if (res.ok) {
        const data = await res.json();
        setSessions(data);
      }
    } catch (err) {
      console.warn('Failed to fetch chat sessions:', err);
    } finally {
      setSessionsLoading(false);
    }
  };

  useEffect(() => {
    if (token) {
      fetchSessions();
    }
  }, [token]);

  // Load conversation messages for a selected session
  const loadSession = async (sessionId) => {
    setCurrentSessionId(sessionId);
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/chat/history/${sessionId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!res.ok) {
        throw new Error(`Failed to load chat history (${res.status})`);
      }

      const data = await res.json();
      setMessages(data);
    } catch (err) {
      setError(err.message || 'Error loading conversation.');
    } finally {
      setLoading(false);
      setSidebarOpen(false);
    }
  };

  // Start a new blank chat session
  const handleNewChat = () => {
    setCurrentSessionId(null);
    setMessages([]);
    setError(null);
    setInputQuestion('');
    setSidebarOpen(false);
  };

  // Send question to /chat/ask
  const handleSendMessage = async (e, directQuestion = null) => {
    if (e) e.preventDefault();
    const query = (directQuestion || inputQuestion).trim();
    if (!query || loading) return;

    setError(null);
    setInputQuestion('');

    // Optimistically add user message
    const tempUserMsg = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: query,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);
    setLoading(true);

    try {
      const payload = {
        question: query,
        session_id: currentSessionId || undefined,
        scope: user?.role === 'student' ? 'public' : 'all',
        top_k: 5,
      };

      const res = await fetch(`${API_BASE_URL}/chat/ask`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || `Server responded with status ${res.status}`);
      }

      // If this was a new conversation, update currentSessionId and refresh sessions list
      if (!currentSessionId && data.session_id) {
        setCurrentSessionId(data.session_id);
        fetchSessions();
      }

      // Add assistant response
      const assistantMsg = {
        id: data.message_id || `msg-${Date.now()}`,
        role: 'assistant',
        content: data.answer,
        source_references: data.sources || [],
        is_cache_hit: Boolean(data.is_cache_hit),
        has_sufficient_context: Boolean(data.has_sufficient_context),
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      setError(err.message || 'Failed to generate answer. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Clean, realistic academic questions
  const exampleQuestions = [
    'What is the minimum CGPA required for good academic standing?',
    'What are the campus library hours and locations?',
    'What are the requirements for academic probation review?',
    'Where is the student wellness center located?',
  ];

  return (
    <div className="flex h-[calc(100vh-4rem)] bg-slate-50 overflow-hidden font-sans">
      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Conversations Sidebar */}
      <aside
        className={`fixed lg:static inset-y-0 left-0 z-50 w-64 bg-white border-r border-slate-200 flex flex-col transition-transform duration-300 ease-in-out lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Sidebar Header: New Chat Button */}
        <div className="p-3.5 border-b border-slate-100 flex items-center justify-between">
          <button
            onClick={handleNewChat}
            className="w-full inline-flex items-center justify-center px-4 py-2 rounded-xl text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 shadow-sm transition-colors space-x-1.5"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            <span>New Chat</span>
          </button>
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden ml-2 p-1 text-slate-400 hover:text-slate-600"
          >
            &times;
          </button>
        </div>

        {/* Sessions List */}
        <div className="flex-1 overflow-y-auto p-2.5 space-y-1">
          <div className="px-2 py-1 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            History
          </div>

          {sessionsLoading ? (
            <div className="p-4 text-center text-xs text-slate-400 flex items-center justify-center space-x-2">
              <svg className="animate-spin h-3.5 w-3.5 text-blue-600" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span>Loading history...</span>
            </div>
          ) : sessions.length === 0 ? (
            <div className="p-4 text-center text-xs text-slate-400">
              No conversations yet.
            </div>
          ) : (
            sessions.map((sess) => {
              const isActive = sess.id === currentSessionId;
              return (
                <button
                  key={sess.id}
                  onClick={() => loadSession(sess.id)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors flex items-center space-x-2 truncate ${
                    isActive
                      ? 'bg-blue-50 text-blue-700 font-semibold'
                      : 'text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  <svg
                    className={`w-3.5 h-3.5 flex-shrink-0 ${isActive ? 'text-blue-600' : 'text-slate-400'}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                    />
                  </svg>
                  <span className="truncate">{sess.title || 'Conversation'}</span>
                </button>
              );
            })
          )}
        </div>
      </aside>

      {/* Main Chat Area */}
      <section className="flex-1 flex flex-col bg-slate-50 relative overflow-hidden">
        {/* Top Header */}
        <div className="h-13 px-4 sm:px-6 bg-white border-b border-slate-200 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-1.5 rounded-lg text-slate-600 hover:bg-slate-100"
              aria-label="Open History"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <h2 className="text-sm font-semibold text-slate-900">
              CampusMind Assistant
            </h2>
          </div>

          <button
            onClick={handleNewChat}
            className="text-xs font-medium px-2.5 py-1 rounded-md border border-slate-200 hover:bg-slate-50 text-slate-600"
          >
            New Session
          </button>
        </div>

        {/* Message Stream */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 max-w-4xl w-full mx-auto space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs flex items-center justify-between">
              <span>{error}</span>
              <button onClick={() => setError(null)} className="font-bold text-red-700 ml-2">&times;</button>
            </div>
          )}

          {/* Simple Clean Welcome Screen */}
          {messages.length === 0 && !loading && (
            <div className="py-16 text-center animate-fade-in">
              <h3 className="text-lg font-bold text-slate-900">
                How can I help you today?
              </h3>
              <p className="mt-1 text-xs text-slate-500 max-w-md mx-auto">
                Ask questions regarding courses, academic regulations, policies, or campus facilities.
              </p>

              {/* Clean Example Chips */}
              <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-2.5 max-w-xl mx-auto text-left">
                {exampleQuestions.map((q, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSendMessage(null, q)}
                    className="p-3 rounded-xl bg-white border border-slate-200 hover:border-blue-400 hover:shadow-xs transition-all text-xs text-slate-700 leading-snug"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Messages */}
          {messages.map((msg, index) => {
            const isUser = msg.role === 'user';
            return (
              <div
                key={msg.id || index}
                className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}
              >
                <div
                  className={`max-w-2xl rounded-2xl p-4 text-xs sm:text-sm leading-relaxed ${
                    isUser
                      ? 'bg-blue-600 text-white rounded-br-xs'
                      : 'bg-white text-slate-800 border border-slate-200 shadow-2xs rounded-bl-xs'
                  }`}
                >
                  {/* Clean Cache Badge */}
                  {!isUser && msg.is_cache_hit && (
                    <div className="mb-2">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                        ⚡ Cached Answer
                      </span>
                    </div>
                  )}

                  {/* Properly rendered Markdown for Assistant, Plain Text for User */}
                  {isUser ? (
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                  ) : (
                    <MarkdownRenderer content={msg.content} />
                  )}

                  {/* Clean Citations Block */}
                  {!isUser && msg.source_references && msg.source_references.length > 0 && (
                    <div className="mt-3.5 pt-2.5 border-t border-slate-100">
                      <div className="text-[11px] font-semibold text-slate-500 mb-1.5">
                        Sources ({msg.source_references.length}):
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {msg.source_references.map((src, sIdx) => (
                          <button
                            key={sIdx}
                            onClick={() => setSelectedCitation(src)}
                            className="inline-flex items-center px-2.5 py-1 rounded-md bg-slate-50 hover:bg-blue-50 border border-slate-200 hover:border-blue-300 text-[11px] text-slate-700 transition-colors text-left"
                          >
                            <span className="font-bold text-blue-600 mr-1.5">
                              [{src.citation_index || sIdx + 1}]
                            </span>
                            <span className="font-medium truncate max-w-[200px]">
                              {src.document_name}
                            </span>
                            {src.page_number && (
                              <span className="text-slate-400 ml-1.5 font-mono text-[10px]">
                                p.{src.page_number}
                              </span>
                            )}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {/* Simple Loading Indicator */}
          {loading && (
            <div className="flex items-center space-x-2 text-xs text-slate-500 py-2">
              <svg className="animate-spin h-3.5 w-3.5 text-blue-600" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span>Generating answer...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="p-3.5 bg-white border-t border-slate-200 flex-shrink-0">
          <form onSubmit={handleSendMessage} className="max-w-4xl mx-auto flex items-center space-x-2">
            <input
              type="text"
              value={inputQuestion}
              onChange={(e) => setInputQuestion(e.target.value)}
              placeholder="Ask a question..."
              disabled={loading}
              className="flex-1 px-3.5 py-2.5 text-xs sm:text-sm bg-slate-50 border border-slate-300 rounded-xl focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={loading || !inputQuestion.trim()}
              className="px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 shadow-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Send
            </button>
          </form>
        </div>
      </section>

      {/* Citation Inspector Modal */}
      {selectedCitation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-md w-full p-5 shadow-xl border border-slate-200 animate-fade-in">
            <div className="flex items-center justify-between pb-2.5 border-b border-slate-100">
              <div className="flex items-center space-x-2">
                <span className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 text-xs font-bold">
                  [{selectedCitation.citation_index || 1}]
                </span>
                <span className="font-semibold text-xs sm:text-sm text-slate-900 truncate max-w-xs">
                  {selectedCitation.document_name}
                </span>
              </div>
              <button
                onClick={() => setSelectedCitation(null)}
                className="text-slate-400 hover:text-slate-600 font-bold p-1 text-sm"
              >
                &times;
              </button>
            </div>

            <div className="mt-3 space-y-2 text-xs">
              <div className="flex items-center justify-between text-slate-500">
                <span>Document: <code className="font-mono text-slate-700">{selectedCitation.document_name}</code></span>
                {selectedCitation.page_number && (
                  <span className="font-medium text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
                    Page {selectedCitation.page_number}
                  </span>
                )}
              </div>

              {selectedCitation.content_snippet && (
                <div>
                  <span className="font-semibold text-slate-700">Source Excerpt:</span>
                  <div className="mt-1 p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-slate-700 leading-relaxed text-xs">
                    "{selectedCitation.content_snippet}"
                  </div>
                </div>
              )}
            </div>

            <div className="mt-4 flex justify-end">
              <button
                onClick={() => setSelectedCitation(null)}
                className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold rounded-lg text-xs"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
