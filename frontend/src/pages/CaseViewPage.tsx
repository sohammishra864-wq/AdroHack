import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  InboxCase,
  CaseResult,
  Signal,
  ImageResult,
  DocResult,
  ClaimScore,
  AuditRecord,
} from '../types';
import { api, CaseNotReady } from '../lib/api';
import { BandChip } from '../components/BandChip';
import { ImagesTab } from '../components/tabs/ImagesTab';
import { DocumentsTab } from '../components/tabs/DocumentsTab';
import { IdentityTab } from '../components/tabs/IdentityTab';
import { ScoreTab } from '../components/tabs/ScoreTab';
import { NewClaimModal } from '../components/NewClaimModal';
import {
  Plus,
  Play,
  FileSearch,
  Sparkles,
  Inbox as InboxIcon,
  RefreshCw,
  Clock,
  Layers,
} from 'lucide-react';

export const CaseViewPage: React.FC = () => {
  const { caseId } = useParams<{ caseId?: string }>();
  const navigate = useNavigate();

  const [inboxCases, setInboxCases] = useState<InboxCase[]>([]);
  const [currentCase, setCurrentCase] = useState<CaseResult | null>(null);
  type CaseTab = 'images' | 'documents' | 'identity' | 'score';
  // ?tab=score etc. deep-links straight to a tab (shareable links)
  const urlTab = new URLSearchParams(window.location.search).get('tab') as CaseTab | null;
  const [activeTab, setActiveTab] = useState<CaseTab>(
    urlTab && ['images', 'documents', 'identity', 'score'].includes(urlTab) ? urlTab : 'images');
  const [loading, setLoading] = useState<boolean>(false);
  const [scoringRunning, setScoringRunning] = useState<boolean>(false);
  const [provisionalPill, setProvisionalPill] = useState<boolean>(false);
  const [history, setHistory] = useState<AuditRecord[]>([]);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Dynamic signals accumulated during streaming
  const [streamedSignals, setStreamedSignals] = useState<Signal[]>([]);
  const streamingFor = useRef<string | null>(null);

  // Load inbox cases
  const loadInbox = async () => {
    try {
      const cases = await api.getCases();
      setInboxCases(cases);
    } catch (e) {
      console.error(e);
    }
  };

  // Load selected case
  const loadCase = async (id: string) => {
    setLoading(true);
    try {
      const data = await api.getCase(id);
      setCurrentCase(data);
      setStreamedSignals(data.claim.signals || []);
      setProvisionalPill(data.claim.pending_deep);
      const hist = await api.getHistory(id);
      setHistory(hist);
    } catch (err: any) {
      console.warn('Error loading case', err);
      setCurrentCase(null);
      // Live mode: an inbox case that was never scored (404) or is still scoring (409)
      // is scored live instead of showing an empty page.
      if (err instanceof CaseNotReady && streamingFor.current !== id) {
        setToastMessage(err.status === 409 ? 'Scoring in progress…' : 'Not scored yet: scoring now…');
        startLiveScoring(id);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInbox();
  }, []);

  useEffect(() => {
    if (caseId) {
      loadCase(caseId);
    } else {
      setCurrentCase(null);
    }
  }, [caseId]);

  // Start live scoring stream (Spec § 6)
  const startLiveScoring = async (id: string, customEventsUrl?: string) => {
    streamingFor.current = id;   // a 409 for this case while we stream it is expected, not a reason to re-score
    setScoringRunning(true);
    setStreamedSignals([]);
    setProvisionalPill(false);

    try {
      let eventsUrl = customEventsUrl;
      if (!eventsUrl) {
        const scoreRes = await api.scoreCase(id);
        eventsUrl = scoreRes.events;
      }

      const unsubscribe = api.subscribeToEvents(eventsUrl, id, {
        onCard: ({ signal }) => {
          setStreamedSignals((prev) => {
            const exists = prev.some((s) => s.name === signal.name);
            return exists ? prev : [...prev, signal];
          });
        },
        onImageFastDone: ({ result }) => {
          setCurrentCase((prev) => (prev ? { ...prev, images: [result] } : prev));
        },
        onDocDone: ({ result }) => {
          setCurrentCase((prev) => (prev ? { ...prev, documents: [result] } : prev));
        },
        onProvisional: ({ claim }) => {
          setProvisionalPill(true);
          setCurrentCase((prev) => (prev ? { ...prev, claim } : prev));
        },
        onDeepDone: ({ result, signal }) => {
          setProvisionalPill(false);
          setCurrentCase((prev) => (prev ? { ...prev, images: [result] } : prev));
          setStreamedSignals((prev) => [...prev.filter((s) => s.name !== signal.name), signal]);
        },
        onFinal: (finalCase) => {
          setCurrentCase(finalCase);
          setStreamedSignals(finalCase.claim.signals);
          setScoringRunning(false);
          setProvisionalPill(false);
          loadInbox();
        },
        onError: ({ message }) => {
          setToastMessage(message);
          setScoringRunning(false);
        },
      });

      return () => unsubscribe();
    } catch (err: any) {
      setToastMessage(err.message || 'Scoring initiation failed');
      setScoringRunning(false);
    }
  };

  const handleDecisionSubmitted = async () => {
    if (caseId) {
      const hist = await api.getHistory(caseId);
      setHistory(hist);
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex flex-col bg-[#FAF8F5] text-stone-900">
      {/* Toast notification banner */}
      {toastMessage && (
        <div className="fixed top-20 right-6 z-50 p-4 rounded-xl bg-stone-900 text-white shadow-2xl flex items-center justify-between gap-4 text-xs animate-in slide-in-from-top-4">
          <span>{toastMessage}</span>
          <button
            onClick={() => setToastMessage(null)}
            className="text-stone-400 hover:text-white font-bold"
          >
            ✕
          </button>
        </div>
      )}

      {/* Main Split Layout: Desktop First (≥1024px) */}
      <div className="flex-1 flex flex-col lg:flex-row max-w-7xl w-full mx-auto border-x border-[#EAE5DC]">
        {/* Left Sidebar: INBOX (width 320px) */}
        <aside className="w-full lg:w-80 border-b lg:border-b-0 lg:border-r border-[#EAE5DC] bg-white/80 flex flex-col justify-between shrink-0">
          <div>
            <div className="p-4 border-b border-[#EAE5DC] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <InboxIcon className="w-4 h-4 text-zinc-400" />
                <span className="font-extrabold text-xs tracking-wider uppercase text-zinc-500">
                  Inbox Claims
                </span>
              </div>
              <button
                type="button"
                onClick={() => setIsModalOpen(true)}
                className="flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-[#1d1d1f] text-white hover:bg-black apple-btn pencil-hover shadow-xs"
              >
                <Plus className="w-3.5 h-3.5" /> New
              </button>
            </div>

            {/* Case List */}
            <div className="divide-y divide-stone-100 overflow-y-auto max-h-[calc(100vh-12rem)]">
              {inboxCases.length === 0 ? (
                <div className="p-6 text-center text-xs text-stone-500">
                  No claims yet. Upload one with + New claim.
                </div>
              ) : (
                inboxCases.map((c) => {
                  const isSelected = c.case_id === caseId;
                  return (
                    <Link
                      key={c.case_id}
                      to={`/cases/${c.case_id}`}
                      className={`block p-3.5 text-left transition-all pencil-hover ${
                        isSelected
                          ? 'bg-stone-100 font-bold border-l-3 border-stone-900'
                          : 'hover:bg-stone-50/80'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-xs font-bold text-stone-900 truncate block">
                          {c.title}
                        </span>
                        <BandChip band={c.last_band} size="sm" />
                      </div>

                      <div className="mt-1.5 flex items-center gap-3 text-[11px] font-mono text-stone-500 font-medium">
                        <span>{c.counts.photos} photo(s)</span>
                        <span>{c.counts.documents} doc(s)</span>
                        {c.counts.id && <span className="text-emerald-700 font-bold">ID ✓</span>}
                      </div>
                    </Link>
                  );
                })
              )}
            </div>
          </div>

          {/* Quick Demo Trigger Footer */}
          <div className="p-3 border-t border-stone-200 text-[11px] text-stone-500 flex items-center justify-between font-medium">
            <span className="font-mono">Reviewer Mode</span>
            <button
              onClick={loadInbox}
              className="hover:text-stone-900 flex items-center gap-1 font-semibold cursor-pointer"
            >
              <RefreshCw className="w-3 h-3" /> Refresh
            </button>
          </div>
        </aside>

        {/* Right Main Panel: Case Details / Empty State */}
        <main className="flex-1 p-6 lg:p-8 overflow-y-auto">
          {!caseId || !currentCase ? (
            /* Empty State (§ 3 & § 8) */
            <div className="h-full min-h-[460px] flex flex-col items-center justify-center text-center p-8 apple-glass-elevated rounded-3xl border border-[#EAE5DC] shadow-md">
              <div className="w-14 h-14 rounded-2xl bg-stone-100 flex items-center justify-center text-stone-500 mb-4 border border-stone-200">
                <FileSearch className="w-7 h-7" />
              </div>
              <h3 className="text-lg font-bold text-stone-900 mb-1">
                Open a claim or upload one
              </h3>
              <p className="text-xs text-stone-600 max-w-md mb-6 leading-relaxed">
                Select an existing claim from the left inbox or submit photos, repair estimates, and biometric ID for streaming forensic verification.
              </p>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setIsModalOpen(true)}
                  className="px-5 py-2.5 rounded-full font-bold text-xs bg-[#1d1d1f] text-white hover:bg-black apple-btn pencil-hover shadow-md"
                >
                  + Upload New Claim
                </button>
                <Link
                  to="/cases/b_fraud"
                  className="px-5 py-2.5 rounded-full font-bold text-xs bg-stone-100 text-stone-800 hover:bg-stone-200 apple-btn pencil-hover border border-stone-200"
                >
                  Load Sample Fraud Claim
                </Link>
              </div>
            </div>
          ) : (
            /* Active Scored Claim Workspace (Apple macOS Pro Window) */
            <div className="space-y-6">
              {/* macOS Window Header Bar */}
              <div className="apple-glass-card rounded-2xl p-4 flex flex-wrap items-center justify-between gap-4 border border-white/80 shadow-sm">
                <div className="space-y-1">
                  {/* Traffic lights + title */}
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1.5 pr-1">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#FF5F56] border border-[#E0443E]/50 shadow-xs" />
                      <span className="w-2.5 h-2.5 rounded-full bg-[#FFBD2E] border border-[#DEA123]/50 shadow-xs" />
                      <span className="w-2.5 h-2.5 rounded-full bg-[#27C93F] border border-[#1AAB29]/50 shadow-xs" />
                    </div>
                    <h2 className="text-lg font-bold tracking-tight text-[#1d1d1f]">
                      {currentCase.title}
                    </h2>
                    <BandChip band={currentCase.claim.band} size="sm" />
                    {provisionalPill && (
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 animate-pulse">
                        Deep scan running…
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-[#86868b] font-mono pl-8">
                    <span>ID: {currentCase.case_id}</span>
                    <span>·</span>
                    <span>
                      Overall Risk:{' '}
                      <strong className="text-[#1d1d1f]">
                        {currentCase.claim.overall.toFixed(2)}
                      </strong>
                    </span>
                    <span>·</span>
                    <span>SHA-256: {currentCase.hashes[0]?.substring(0, 10)}…</span>
                  </div>
                </div>

                {/* Score Claim Trigger Button */}
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={scoringRunning}
                    onClick={() => startLiveScoring(currentCase.case_id)}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-semibold apple-glass hover:bg-white text-[#1d1d1f] border border-white/80 shadow-xs disabled:opacity-50 apple-btn"
                  >
                    <Play className="w-3.5 h-3.5 text-emerald-600 fill-emerald-600/20" />
                    {scoringRunning ? 'Streaming Cards…' : 'Re-score Claim'}
                  </button>
                </div>
              </div>

              {/* macOS Segmented Tabs Navigation (§ 3): Images · Documents · Identity · Score */}
              <div className="flex items-center justify-start pb-1">
                <div className="apple-segmented-bg inline-flex items-center gap-1">
                  {[
                    { id: 'images', label: `Images (${currentCase.images.length})` },
                    { id: 'documents', label: `Documents (${currentCase.documents.length})` },
                    { id: 'identity', label: 'Identity & Selfie' },
                    { id: 'score', label: 'Score & Decisions' },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id as any)}
                      className={`px-4 py-1.5 text-xs font-semibold transition-all cursor-pointer rounded-lg ${
                        activeTab === tab.id
                          ? 'apple-segmented-item-active'
                          : 'text-[#6e6e73] hover:text-[#1d1d1f]'
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Tab Contents */}
              <div>
                {activeTab === 'images' && currentCase.images[0] && (
                  <ImagesTab
                    image={currentCase.images[0]}
                    signals={streamedSignals.length > 0 ? streamedSignals : currentCase.claim.signals}
                  />
                )}

                {activeTab === 'documents' && currentCase.documents[0] && (
                  <DocumentsTab
                    document={currentCase.documents[0]}
                    signals={streamedSignals.length > 0 ? streamedSignals : currentCase.claim.signals}
                  />
                )}

                {activeTab === 'identity' && (
                  <IdentityTab identity={currentCase.identity} />
                )}

                {activeTab === 'score' && (
                  <ScoreTab
                    caseId={currentCase.case_id}
                    claim={currentCase.claim}
                    narrative={currentCase.narrative}
                    signals={streamedSignals.length > 0 ? streamedSignals : currentCase.claim.signals}
                    history={history}
                    onDecisionSubmitted={handleDecisionSubmitted}
                  />
                )}
              </div>
            </div>
          )}
        </main>
      </div>

      {/* New Claim Modal */}
      <NewClaimModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onClaimCreated={(newCaseId, eventsUrl) => {
          navigate(`/cases/${newCaseId}`);
          loadInbox();
          startLiveScoring(newCaseId, eventsUrl);
        }}
      />
    </div>
  );
};
