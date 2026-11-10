import React from 'react';
import { useAuth } from '../context/AuthContext';

export const HomePage = ({ onNavigate }) => {
  const { isAuthenticated, user } = useAuth();

  const handleStartChat = () => {
    if (isAuthenticated) {
      onNavigate('chat');
    } else {
      onNavigate('login');
    }
  };

  return (
    <div className="flex flex-col min-h-[calc(100vh-4rem)]">
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-b from-slate-50 via-blue-50/40 to-white pt-16 pb-20 lg:pt-24 lg:pb-28">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
          <div className="text-center max-w-3xl mx-auto">
            {/* Pill Badge */}
            <div className="inline-flex items-center space-x-2 px-3 py-1.5 rounded-full bg-blue-100/70 border border-blue-200 text-blue-800 text-xs sm:text-sm font-medium mb-6">
              <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse"></span>
              <span>Intelligent Campus Knowledge Base Platform</span>
            </div>

            {/* Main Headline */}
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-slate-900 tracking-tight leading-[1.15]">
              Instant, verified answers for your{' '}
              <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-800">
                university journey
              </span>
            </h1>

            {/* Sub-headline */}
            <p className="mt-6 text-lg sm:text-xl text-slate-600 leading-relaxed font-normal">
              CampusMind AI connects students and faculty to official course syllabi,
              regulations, academic policies, and campus procedures — with verifiable
              page-level citations and grounded accuracy.
            </p>

            {/* CTA Buttons */}
            <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
              <button
                onClick={handleStartChat}
                className="w-full sm:w-auto inline-flex items-center justify-center px-8 py-3.5 text-base font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-xl shadow-lg shadow-blue-500/25 hover:shadow-xl transition-all duration-200"
              >
                <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                {isAuthenticated ? 'Go to AI Chat' : 'Start Chatting Now'}
              </button>

              {!isAuthenticated ? (
                <button
                  onClick={() => onNavigate('register')}
                  className="w-full sm:w-auto inline-flex items-center justify-center px-8 py-3.5 text-base font-semibold text-slate-700 bg-white hover:bg-slate-50 border border-slate-300 rounded-xl shadow-sm transition-all duration-200"
                >
                  Create Student Account
                </button>
              ) : (
                <div className="inline-flex items-center text-sm font-medium text-slate-500 px-4 py-3 bg-white/80 rounded-xl border border-slate-200">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 mr-2"></span>
                  Signed in as <strong className="text-slate-800 ml-1">{user?.email}</strong>
                </div>
              )}
            </div>

            {/* Micro-guarantee */}
            <p className="mt-4 text-xs text-slate-500">
              {isAuthenticated
                ? 'Welcome back! You have active access to the verified university RAG pipeline.'
                : 'Guests are prompted to sign in to access personalized student chat sessions.'}
            </p>
          </div>
        </div>

        {/* Decorative background grid */}
        <div className="absolute inset-0 pointer-events-none opacity-40 bg-[radial-gradient(#cbd5e1_1px,transparent_1px)] [background-size:16px_16px] [mask-image:radial-gradient(ellipse_50%_50%_at_50%_50%,#000_70%,transparent_100%)]"></div>
      </section>

      {/* Feature Highlights Section */}
      <section id="how-it-works" className="py-16 sm:py-20 bg-white border-y border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <h2 className="text-xs sm:text-sm font-bold uppercase tracking-wider text-blue-600 mb-2">
              Engineered for Academic Integrity
            </h2>
            <h3 className="text-3xl font-extrabold text-slate-900 tracking-tight">
              Why CampusMind AI is not just another chatbot
            </h3>
            <p className="mt-3 text-base text-slate-600">
              Unlike generic public models that hallucinate policies, CampusMind AI
              retrieves and synthesizes answers exclusively from authoritative university documents.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {/* Card 1 */}
            <div className="relative p-8 rounded-2xl bg-slate-50/70 border border-slate-200 hover:border-blue-300 hover:shadow-md transition-all">
              <div className="w-12 h-12 rounded-xl bg-blue-600/10 text-blue-700 flex items-center justify-center font-bold text-xl mb-5">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h4 className="text-xl font-bold text-slate-900 mb-2">Document Grounding</h4>
              <p className="text-slate-600 text-sm leading-relaxed">
                Answers are synthesized strictly from indexed institutional handbooks,
                department policies, and course guidelines with refusal mechanisms for ungrounded queries.
              </p>
            </div>

            {/* Card 2 */}
            <div className="relative p-8 rounded-2xl bg-slate-50/70 border border-slate-200 hover:border-blue-300 hover:shadow-md transition-all">
              <div className="w-12 h-12 rounded-xl bg-indigo-600/10 text-indigo-700 flex items-center justify-center font-bold text-xl mb-5">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
                </svg>
              </div>
              <h4 className="text-xl font-bold text-slate-900 mb-2">Verifiable Citations</h4>
              <p className="text-slate-600 text-sm leading-relaxed">
                Every statement includes source tags showing the exact source document,
                page number, and chunk snippet so students can immediately verify the policy rule.
              </p>
            </div>

            {/* Card 3 */}
            <div className="relative p-8 rounded-2xl bg-slate-50/70 border border-slate-200 hover:border-blue-300 hover:shadow-md transition-all">
              <div className="w-12 h-12 rounded-xl bg-emerald-600/10 text-emerald-700 flex items-center justify-center font-bold text-xl mb-5">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h4 className="text-xl font-bold text-slate-900 mb-2">Sub-Second Responses</h4>
              <p className="text-slate-600 text-sm leading-relaxed">
                High-performance hybrid retrieval (dense vectors + sparse BM25) powered by Redis caching
                delivers instant answers to common student inquiries without latency.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Citation & Grounding Interactive Explanation */}
      <section id="citations" className="py-16 sm:py-20 bg-slate-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <div>
              <div className="inline-flex items-center space-x-2 text-xs font-semibold px-2.5 py-1 rounded bg-indigo-100 text-indigo-800 mb-4">
                Transparency by Design
              </div>
              <h3 className="text-3xl font-extrabold text-slate-900 tracking-tight leading-snug">
                Never guess an academic rule again.
              </h3>
              <p className="mt-4 text-base text-slate-600 leading-relaxed">
                When you ask CampusMind AI about graduation thresholds, prerequisites, or drop deadlines,
                the assistant provides the answer alongside direct citations to the official university document.
              </p>

              <ul className="mt-6 space-y-4 text-sm text-slate-700">
                <li className="flex items-start">
                  <div className="flex-shrink-0 w-5 h-5 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mr-3 mt-0.5">
                    ✓
                  </div>
                  <span><strong>Zero Hallucinations:</strong> If a topic is not in the uploaded university corpus, the system transparently indicates insufficient context.</span>
                </li>
                <li className="flex items-start">
                  <div className="flex-shrink-0 w-5 h-5 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mr-3 mt-0.5">
                    ✓
                  </div>
                  <span><strong>Granular Citations:</strong> Inspect exact page numbers, document titles, and excerpt snippets.</span>
                </li>
                <li className="flex items-start">
                  <div className="flex-shrink-0 w-5 h-5 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mr-3 mt-0.5">
                    ✓
                  </div>
                  <span><strong>Role-Scoped Privacy:</strong> Students only access public academic handbooks; internal staff notices remain securely partitioned.</span>
                </li>
              </ul>

              <div className="mt-8">
                <button
                  onClick={handleStartChat}
                  className="inline-flex items-center font-semibold text-blue-600 hover:text-blue-700"
                >
                  Experience the grounded QA demo &rarr;
                </button>
              </div>
            </div>

            {/* Mocked UI Card showing citation feature */}
            <div className="bg-white rounded-2xl shadow-xl border border-slate-200/80 p-6 sm:p-7">
              <div className="flex items-center justify-between pb-4 border-b border-slate-100">
                <div className="flex items-center space-x-2">
                  <span className="w-3 h-3 rounded-full bg-red-400"></span>
                  <span className="w-3 h-3 rounded-full bg-amber-400"></span>
                  <span className="w-3 h-3 rounded-full bg-emerald-400"></span>
                  <span className="ml-2 text-xs font-mono text-slate-400">CampusMind QA Output</span>
                </div>
                <span className="text-[11px] font-semibold uppercase px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded border border-emerald-200">
                  Grounded: 100%
                </span>
              </div>

              <div className="mt-4 space-y-4">
                <div className="bg-slate-50 p-3 rounded-lg text-xs font-mono text-slate-700 border border-slate-200">
                  <span className="text-blue-600 font-bold">Q:</span> What is the minimum CGPA required for good academic standing?
                </div>

                <div className="text-sm text-slate-800 leading-relaxed bg-blue-50/50 p-4 rounded-xl border border-blue-100">
                  <p>
                    A minimum Cumulative Grade Point Average (CGPA) of <strong>2.00 out of 4.00</strong> is required
                    to remain in good academic standing. Students whose CGPA falls below 2.00 will be placed on
                    academic probation for one semester{' '}
                    <span className="inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-blue-700 bg-blue-200 rounded-full cursor-pointer hover:bg-blue-300">
                      1
                    </span>.
                  </p>
                </div>

                {/* Citation Snippet box */}
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs">
                  <div className="flex items-center justify-between font-semibold text-slate-700 mb-1">
                    <span className="flex items-center">
                      <span className="w-4 h-4 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px] mr-1.5">1</span>
                      CS_Student_Handbook_2026.pdf
                    </span>
                    <span className="text-slate-500">Page 2</span>
                  </div>
                  <p className="text-slate-500 italic mt-1 text-[11px]">
                    "...a student must maintain a minimum cumulative grade point average of 2.00 on a 4.00 scale to avoid academic probation..."
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Final Call to Action */}
      <section className="py-16 bg-gradient-to-tr from-blue-700 to-indigo-800 text-white text-center">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight">
            Ready to explore verified university intelligence?
          </h2>
          <p className="mt-4 text-base sm:text-lg text-blue-100 max-w-2xl mx-auto">
            Get instant, reliable guidance tailored specifically for students, faculty, and administrative staff.
          </p>
          <div className="mt-8 flex justify-center">
            <button
              onClick={handleStartChat}
              className="px-8 py-3.5 text-base font-bold text-blue-900 bg-white hover:bg-blue-50 rounded-xl shadow-lg transition-all transform hover:-translate-y-0.5"
            >
              {isAuthenticated ? 'Open AI Chat' : 'Start Asking Questions'}
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto py-8 bg-slate-900 text-slate-400 text-xs sm:text-sm border-t border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-2">
            <span className="font-bold text-white">CampusMind AI</span>
            <span>&bull;</span>
            <span>Academic Knowledge Assistant</span>
          </div>
          <p>&copy; {new Date().getFullYear()} CampusMind AI. Built strictly to SRS Version 1.2 specifications.</p>
        </div>
      </footer>
    </div>
  );
};

