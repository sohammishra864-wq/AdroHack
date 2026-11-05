import React, { useState, useEffect } from 'react';
import { api, CaseNotReady, MyClaim } from '../lib/api';
import { Band } from '../types';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { NewClaimModal } from '../components/NewClaimModal';
import { CameraModal } from '../components/CameraModal';
import {
  Shield,
  Plus,
  Car,
  CheckCircle2,
  Clock,
  FileText,
  ChevronRight,
  Eye,
  AlertCircle,
  Sparkles,
  ArrowUpRight,
  Camera,
  RotateCcw,
  UserCheck,
} from 'lucide-react';

export const ClientPortalPage: React.FC = () => {
  const { user, loginAsReviewer } = useAuth();
  const navigate = useNavigate();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isCameraModalOpen, setIsCameraModalOpen] = useState(false);
  const [verifiedSelfieUrl, setVerifiedSelfieUrl] = useState<string | null>(null);
  const [selfieTimestamp, setSelfieTimestamp] = useState<string | null>(null);

  const clientName = user?.name || 'Guest';
  const owner = user?.email || 'guest';
  const [claims, setClaims] = useState<ClaimView[]>([]);
  const [loadingClaims, setLoadingClaims] = useState(true);

  // Real claims this account filed, with their live status from the backend
  const loadClaims = async () => {
    const mine = api.myClaims(owner);
    const views = await Promise.all(mine.map(async (c): Promise<ClaimView> => {
      try {
        const res = await api.getCase(c.case_id);
        const hist = await api.getHistory(c.case_id);
        const last = hist.length ? hist[hist.length - 1].action : null;
        return { ...c, band: res.claim.band, decision: last, scoring: false, files: res.images.length + res.documents.length };
      } catch (e) {
        return { ...c, band: null, decision: null, scoring: e instanceof CaseNotReady, files: null };
      }
    }));
    setClaims(views);
    setLoadingClaims(false);
  };

  useEffect(() => {
    loadClaims();
    const timer = setInterval(loadClaims, 10000);   // status follows scoring + the adjuster's decision
    return () => clearInterval(timer);
  }, [owner]);

  const handleSwitchToReviewerInspection = (caseId: string) => {
    loginAsReviewer('asha');
    navigate(`/cases/${caseId}`);
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#FAF8F5] text-stone-900 py-10 px-4 sm:px-6">
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Top Welcome Bar */}
        <div className="bg-white p-6 sm:p-8 rounded-3xl border border-[#EAE5DC] shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-6">
          <div className="space-y-1">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold bg-violet-50 text-violet-700 border border-violet-200">
              <span className="w-2 h-2 rounded-full bg-violet-600 animate-pulse" />
              Policyholder Self-Service Portal
            </div>
            <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-stone-900">
              Welcome back, {clientName}
            </h1>
            <p className="text-xs text-stone-500 font-mono">
              {user?.email || 'Not signed in'} · {user?.verified ? 'Verified account' : 'Demo persona'}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsCameraModalOpen(true)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl font-bold text-xs text-stone-800 bg-white border border-[#EAE5DC] hover:bg-stone-50 shadow-xs pencil-hover transition-all active:scale-95 cursor-pointer"
            >
              <Camera className="w-4 h-4 text-violet-600" />
              <span>Take Live Selfie</span>
            </button>
            <button
              onClick={() => setIsModalOpen(true)}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-xs text-white bg-violet-600 hover:bg-violet-700 shadow-md transition-all active:scale-95 cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>File a New Claim</span>
            </button>
          </div>
        </div>

        {/* 2-Column Dashboard Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left Column (8 cols): Active & Historical Claims */}
          <div className="lg:col-span-8 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-extrabold text-stone-900 tracking-tight">
                My Insurance Claims
              </h2>
              <span className="text-xs text-stone-500">{claims.length} claim{claims.length === 1 ? '' : 's'} on file</span>
            </div>

            {loadingClaims ? (
              <div className="bg-white p-6 rounded-3xl border border-[#EAE5DC] shadow-sm text-xs text-stone-500">
                Loading your claims…
              </div>
            ) : claims.length === 0 ? (
              <div className="bg-white p-6 rounded-3xl border border-[#EAE5DC] shadow-sm space-y-3 text-xs">
                <p className="text-sm font-bold text-stone-900">No claims yet</p>
                <p className="text-stone-500">
                  File a claim with your damage photos, invoice or medical report. Each piece of evidence is checked in seconds.
                </p>
                <button
                  type="button"
                  onClick={() => setIsModalOpen(true)}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-xs text-white bg-violet-600 hover:bg-violet-700 shadow-md transition-all active:scale-95 cursor-pointer"
                >
                  <Plus className="w-4 h-4" />
                  <span>File a New Claim</span>
                </button>
              </div>
            ) : (
              claims.map((c) => (
                <ClaimStatusCard key={c.case_id} claim={c} onInspect={() => handleSwitchToReviewerInspection(c.case_id)} />
              ))
            )}
          </div>

          {/* Right Column (4 cols): Policy Summary & Fast Filing */}
          <div className="lg:col-span-4 space-y-5">
            {/* Policy Summary Card */}
            <div className="bg-white p-6 rounded-3xl border border-[#EAE5DC] shadow-sm space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-stone-100">
                <h3 className="text-sm font-bold text-stone-900">Account Details</h3>
                <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-100 text-emerald-800 uppercase">
                  {user?.verified ? 'Verified' : 'Demo'}
                </span>
              </div>

              <div className="space-y-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-stone-500">Name:</span>
                  <span className="font-semibold text-stone-900">{clientName}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-stone-500">Email:</span>
                  <span className="font-mono font-bold text-stone-900 truncate max-w-[160px]">{user?.email || '—'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-stone-500">Sign-in:</span>
                  <span className={`font-semibold ${user?.verified ? 'text-emerald-600' : 'text-amber-700'}`}>
                    {user?.verified ? 'Verified (Supabase)' : 'Demo persona'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-stone-500">Claims on file:</span>
                  <span className="font-mono text-stone-700">{claims.length}</span>
                </div>
              </div>
            </div>

            {/* Live Biometric Selfie Card */}
            <div className="bg-white p-6 rounded-3xl border border-[#EAE5DC] shadow-sm space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-stone-100">
                <div className="flex items-center gap-2">
                  <UserCheck className="w-4 h-4 text-violet-600" />
                  <h3 className="text-sm font-bold text-stone-900">Biometric Identity</h3>
                </div>
                <span
                  className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase ${
                    verifiedSelfieUrl
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-amber-100 text-amber-800'
                  }`}
                >
                  {verifiedSelfieUrl ? 'Verified' : 'Action Available'}
                </span>
              </div>

              {verifiedSelfieUrl ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <img
                      src={verifiedSelfieUrl}
                      alt="Verified Live Selfie"
                      className="w-14 h-14 rounded-2xl object-cover border-2 border-emerald-500 shadow-sm"
                    />
                    <div>
                      <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-700">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Live Selfie Captured</span>
                      </div>
                      <span className="text-[11px] text-stone-500 font-mono block">
                        {selfieTimestamp || 'Captured today'}
                      </span>
                      <span className="text-[10px] text-stone-400 font-mono">
                        Kept on this device until you attach it to a claim
                      </span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsCameraModalOpen(true)}
                    className="w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl text-xs font-bold text-stone-700 bg-stone-100 hover:bg-stone-200 pencil-hover transition-colors cursor-pointer"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>Retake Live Selfie</span>
                  </button>
                </div>
              ) : (
                <div className="space-y-3 text-xs">
                  <p className="text-stone-600 leading-relaxed text-[11px]">
                    Capture your live camera selfie now to pre-verify claim submissions and expedite payout clearance.
                  </p>
                  <button
                    type="button"
                    onClick={() => setIsCameraModalOpen(true)}
                    className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl font-bold text-xs text-white bg-violet-600 hover:bg-violet-700 shadow-xs pencil-hover transition-all active:scale-95 cursor-pointer"
                  >
                    <Camera className="w-4 h-4" />
                    <span>Take Selfie with Camera</span>
                  </button>
                </div>
              )}
            </div>

            {/* Fair Claim Pledge Card */}
            <div className="bg-gradient-to-br from-violet-600 to-indigo-700 p-6 rounded-3xl text-white shadow-md space-y-3">
              <div className="w-8 h-8 rounded-xl bg-white/20 flex items-center justify-center">
                <Shield className="w-4 h-4 text-white" />
              </div>
              <h4 className="text-sm font-bold">Fast & Fair Claims Guarantee</h4>
              <p className="text-xs text-white/80 leading-relaxed">
                Honest claims are fast-tracked. Anything unusual goes to a human adjuster with the evidence explained, and no claim is ever denied automatically.
              </p>
            </div>
          </div>
        </div>
      </div>

      <NewClaimModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onClaimCreated={() => {
          setIsModalOpen(false);
          loadClaims();   // the new claim appears here; its status updates as scoring finishes
        }}
      />

      <CameraModal
        isOpen={isCameraModalOpen}
        onClose={() => setIsCameraModalOpen(false)}
        onCapture={(file, previewUrl) => {
          setVerifiedSelfieUrl(previewUrl);
          setSelfieTimestamp(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
        }}
        title="Policyholder Biometric Selfie"
        subtitle="Align your face inside the oval guide to complete camera verification."
      />
    </div>
  );
};

interface ClaimView extends MyClaim {
  band: Band | null;
  decision: 'accept' | 'reject' | 'escalate' | null;
  scoring: boolean;
  files: number | null;
}

// What the CLAIMANT sees: a plain status, never the fraud score (explanations are for adjusters only).
function claimStatus(c: ClaimView): { label: string; step: number; done: boolean; note: string } {
  if (c.decision === 'accept') return { label: 'Approved', step: 3, done: true, note: 'An adjuster approved this claim.' };
  if (c.decision === 'reject') return { label: 'Declined after review', step: 3, done: true, note: 'An adjuster reviewed the evidence. Contact us to appeal or add evidence.' };
  if (c.decision === 'escalate') return { label: 'With a claims specialist', step: 2, done: false, note: 'A specialist is taking a closer look at your evidence.' };
  if (c.scoring || c.band === null) return { label: 'Checking your evidence', step: 1, done: false, note: 'Your files are being checked. This usually takes a few seconds.' };
  if (c.band === 'UNCERTAIN') return { label: 'Better photo needed', step: 2, done: false, note: 'A photo was too blurry or small to check. You may be asked to upload a clearer one.' };
  if (c.band === 'LOW') return { label: 'Fast-track: awaiting approval', step: 2, done: false, note: 'Your evidence checks passed. An adjuster will confirm the payout.' };
  return { label: 'Under review', step: 2, done: false, note: 'An adjuster is reviewing your evidence. No action is needed from you.' };
}

const ClaimStatusCard: React.FC<{ claim: ClaimView; onInspect: () => void }> = ({ claim, onInspect }) => {
  const s = claimStatus(claim);
  const filed = new Date(claim.filed).toLocaleDateString([], { year: 'numeric', month: 'short', day: 'numeric' });
  if (s.done && claim.decision === 'accept') {
    return (
      <div className="bg-white p-6 rounded-3xl border border-[#EAE5DC] shadow-sm space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-stone-900">{claim.title}</h3>
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800">{s.label}</span>
              </div>
              <span className="text-xs text-stone-500 font-mono">Claim {claim.case_id} · Filed on {filed}</span>
            </div>
          </div>
        </div>
        <div className="pt-2 flex items-center justify-between text-xs border-t border-stone-100">
          <span className="text-stone-500 text-[11px]">{s.note}</span>
          <button type="button" onClick={onInspect} className="text-stone-700 hover:text-stone-900 font-semibold flex items-center gap-1">
            <span>View Proof Report</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    );
  }
  return (
    <div className="bg-white p-6 rounded-3xl border-2 border-amber-200 shadow-sm space-y-4 relative overflow-hidden">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center shrink-0">
            {claim.decision === 'reject' ? <AlertCircle className="w-6 h-6" /> : <Car className="w-6 h-6" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-stone-900">{claim.title}</h3>
              <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-800 flex items-center gap-1">
                <Clock className="w-3 h-3" /> {s.label}
              </span>
            </div>
            <span className="text-xs text-stone-500 font-mono">Claim {claim.case_id} · Filed on {filed}</span>
          </div>
        </div>
        {claim.files !== null && (
          <div className="text-right">
            <span className="text-xs text-stone-400 block font-mono">Evidence:</span>
            <span className="text-base font-extrabold text-stone-900 font-mono">{claim.files} file{claim.files === 1 ? '' : 's'}</span>
          </div>
        )}
      </div>

      <div className="p-3.5 rounded-2xl bg-[#FAF8F5] border border-[#EAE5DC] text-xs space-y-2">
        <div className="flex items-center justify-between text-[11px] font-bold text-stone-600">
          <span className="text-amber-700 flex items-center gap-1">
            <Sparkles className="w-3.5 h-3.5" /> {s.label}
          </span>
          <span>Step {s.step} of 3</span>
        </div>
        <div className="w-full bg-stone-200 h-2 rounded-full overflow-hidden">
          <div className="bg-amber-500 h-full rounded-full transition-all" style={{ width: `${(s.step / 3) * 100}%` }} />
        </div>
        <p className="text-[11px] text-stone-500">{s.note}</p>
      </div>

      <div className="pt-2 flex items-center justify-between text-xs">
        <span className="text-stone-400">Want to inspect the forensic details?</span>
        <button type="button" onClick={onInspect} className="flex items-center gap-1.5 font-bold text-amber-800 hover:text-amber-900 underline underline-offset-4">
          <Eye className="w-4 h-4" />
          <span>Inspect Forensic Check (Adjuster View)</span>
          <ArrowUpRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};
