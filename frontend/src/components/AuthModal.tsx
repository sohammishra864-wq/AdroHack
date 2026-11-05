import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, UserRole } from '../context/AuthContext';
import {
  X,
  User,
  Shield,
  ArrowRight,
  Sparkles,
  CheckCircle2,
  Lock,
  Mail,
  UserCheck,
  ChevronRight,
} from 'lucide-react';
import { REVIEWERS } from '../lib/constants';

export const AuthModal: React.FC = () => {
  const {
    isAuthModalOpen,
    authModalInitialRole,
    closeAuthModal,
    loginAsClient,
    loginAsReviewer,
    authEnabled,
    loginWithPassword,
    signupWithPassword,
  } = useAuth();

  const navigate = useNavigate();
  const [selectedRole, setSelectedRole] = useState<UserRole>('client');
  const [authMode, setAuthMode] = useState<'signin' | 'signup'>('signin');
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [reviewerName, setReviewerName] = useState(REVIEWERS[0]);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formNote, setFormNote] = useState<string | null>(null);

  useEffect(() => {
    setSelectedRole(authModalInitialRole);
  }, [authModalInitialRole, isAuthModalOpen]);

  if (!isAuthModalOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setFormNote(null);
    if (authEnabled) {
      // Real Supabase login / signup through the backend
      setBusy(true);
      try {
        if (authMode === 'signup') {
          const note = await signupWithPassword(name, email, password, selectedRole);
          if (note) {
            setFormNote(note);
            setAuthMode('signin');
            return;
          }
        } else {
          await loginWithPassword(email, password, selectedRole);
        }
        navigate(selectedRole === 'client' ? '/portal' : '/inbox');
      } catch (err: any) {
        setFormError(err.message || 'Sign-in failed');
      } finally {
        setBusy(false);
      }
      return;
    }
    if (selectedRole === 'client') {
      loginAsClient(name || 'Marcus Vance', email || 'marcus.vance@gmail.com');
      navigate('/portal');
    } else {
      loginAsReviewer(reviewerName);
      navigate('/inbox');
    }
  };

  const handleQuickDemoClient = () => {
    loginAsClient('Marcus Vance', 'marcus.vance@gmail.com');
    navigate('/portal');
  };

  const handleQuickDemoReviewer = (rev: string) => {
    loginAsReviewer(rev);
    navigate('/inbox');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 backdrop-blur-sm p-4 animate-in fade-in">
      <div className="w-full max-w-xl bg-white rounded-3xl border border-[#EAE5DC] shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="px-6 py-5 bg-[#FAF8F5] border-b border-[#EAE5DC] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-stone-900 flex items-center justify-center text-white shadow-xs">
              <Shield className="w-4 h-4 text-amber-300" />
            </div>
            <div>
              <h3 className="text-base font-extrabold text-stone-900 tracking-tight">
                {authMode === 'signin' ? 'Sign in to ClaimShield' : 'Create your Account'}
              </h3>
              <p className="text-xs text-stone-500">
                Choose your role to access the policyholder portal or adjuster workspace.
              </p>
            </div>
          </div>
          <button
            onClick={closeAuthModal}
            className="p-1.5 rounded-lg text-stone-400 hover:text-stone-700 hover:bg-stone-200/60 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-6">
          {/* Two Distinct Role Selection Cards */}
          <div>
            <label className="text-xs font-bold text-stone-700 uppercase tracking-wider block mb-2.5">
              Select Your Access Role
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              {/* Option 1: Login as Client */}
              <button
                type="button"
                onClick={() => setSelectedRole('client')}
                className={`p-4 rounded-2xl border-2 text-left transition-all relative flex flex-col justify-between ${
                  selectedRole === 'client'
                    ? 'border-violet-600 bg-violet-50/40 ring-4 ring-violet-600/10'
                    : 'border-[#EAE5DC] bg-[#FAF8F5]/60 hover:border-stone-400'
                }`}
              >
                {selectedRole === 'client' && (
                  <span className="absolute top-3 right-3 w-5 h-5 rounded-full bg-violet-600 text-white flex items-center justify-center">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  </span>
                )}
                <div>
                  <div className="w-8 h-8 rounded-xl bg-violet-100 text-violet-700 flex items-center justify-center mb-2.5 font-bold">
                    <User className="w-4 h-4" />
                  </div>
                  <h4 className="text-sm font-extrabold text-stone-900 leading-tight">
                    Login as Client
                  </h4>
                  <span className="text-[11px] font-semibold text-violet-600 block mt-0.5">
                    Policyholder / Claimant
                  </span>
                  <p className="text-xs text-stone-500 mt-2 leading-relaxed">
                    Submit photos, upload repair invoices, and track your instant claim payouts.
                  </p>
                </div>
                <div className="mt-3 pt-2.5 border-t border-violet-100 flex items-center text-[11px] font-bold text-violet-700">
                  <span>Client Self-Service</span>
                  <ChevronRight className="w-3.5 h-3.5 ml-auto" />
                </div>
              </button>

              {/* Option 2: Login as Reviewer */}
              <button
                type="button"
                onClick={() => setSelectedRole('reviewer')}
                className={`p-4 rounded-2xl border-2 text-left transition-all relative flex flex-col justify-between ${
                  selectedRole === 'reviewer'
                    ? 'border-amber-600 bg-amber-50/40 ring-4 ring-amber-600/10'
                    : 'border-[#EAE5DC] bg-[#FAF8F5]/60 hover:border-stone-400'
                }`}
              >
                {selectedRole === 'reviewer' && (
                  <span className="absolute top-3 right-3 w-5 h-5 rounded-full bg-amber-600 text-white flex items-center justify-center">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  </span>
                )}
                <div>
                  <div className="w-8 h-8 rounded-xl bg-amber-100 text-amber-800 flex items-center justify-center mb-2.5 font-bold">
                    <Shield className="w-4 h-4" />
                  </div>
                  <h4 className="text-sm font-extrabold text-stone-900 leading-tight">
                    Login as Reviewer
                  </h4>
                  <span className="text-[11px] font-semibold text-amber-700 block mt-0.5">
                    Claims Adjuster / SIU
                  </span>
                  <p className="text-xs text-stone-500 mt-2 leading-relaxed">
                    Inspect AI inpainting heatmaps, PDF incremental diffs, and authorize decisions.
                  </p>
                </div>
                <div className="mt-3 pt-2.5 border-t border-amber-100 flex items-center text-[11px] font-bold text-amber-800">
                  <span>Forensics Workspace</span>
                  <ChevronRight className="w-3.5 h-3.5 ml-auto" />
                </div>
              </button>
            </div>
          </div>

          {/* Quick 1-Click Instant Demo Credentials */}
          <div className="p-3.5 rounded-2xl bg-[#FAF8F5] border border-[#EAE5DC] space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-stone-800 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                Instant 1-Click Demo Login
              </span>
              <span className="text-[10px] text-stone-400 font-mono">No password required</span>
            </div>

            {selectedRole === 'client' ? (
              <button
                type="button"
                onClick={handleQuickDemoClient}
                className="w-full py-2 px-3 rounded-xl bg-white border border-[#EAE5DC] hover:border-violet-400 text-xs font-semibold text-stone-800 flex items-center justify-between shadow-xs transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-violet-100 text-violet-700 flex items-center justify-center font-bold text-[10px]">
                    MV
                  </span>
                  <span>Continue as <strong>Marcus Vance</strong> (Policyholder)</span>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-stone-400" />
              </button>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                {REVIEWERS.slice(0, 2).map((rev) => (
                  <button
                    key={rev}
                    type="button"
                    onClick={() => handleQuickDemoReviewer(rev)}
                    className="py-2 px-3 rounded-xl bg-white border border-[#EAE5DC] hover:border-amber-400 text-xs font-semibold text-stone-800 flex items-center justify-between shadow-xs transition-colors"
                  >
                    <span>Adjuster: <strong>{rev.toUpperCase()}</strong></span>
                    <ArrowRight className="w-3 h-3 text-stone-400" />
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Regular Credentials Form */}
          <form onSubmit={handleSubmit} className="space-y-3.5 text-xs">
            {authMode === 'signup' && (
              <div>
                <label className="font-semibold text-stone-700 block mb-1">Full Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={selectedRole === 'client' ? 'Marcus Vance' : 'Asha Patel'}
                  className="w-full p-2.5 rounded-xl border border-[#EAE5DC] bg-white text-stone-900 placeholder-stone-400 focus:outline-hidden focus:ring-2 focus:ring-stone-400"
                />
              </div>
            )}

            {selectedRole === 'client' || authEnabled ? (
              <div>
                <label className="font-semibold text-stone-700 block mb-1">Email Address</label>
                <div className="relative">
                  <Mail className="w-4 h-4 absolute left-3 top-3 text-stone-400" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder={selectedRole === 'client' ? 'claimant@gmail.com' : 'adjuster@insurer.com'}
                    className="w-full pl-9 pr-3 py-2.5 rounded-xl border border-[#EAE5DC] bg-white text-stone-900 placeholder-stone-400 focus:outline-hidden focus:ring-2 focus:ring-stone-400"
                  />
                </div>
              </div>
            ) : (
              <div>
                <label className="font-semibold text-stone-700 block mb-1">Adjuster ID / Name</label>
                <div className="relative">
                  <UserCheck className="w-4 h-4 absolute left-3 top-3 text-stone-400" />
                  <select
                    value={reviewerName}
                    onChange={(e) => setReviewerName(e.target.value)}
                    className="w-full pl-9 pr-3 py-2.5 rounded-xl border border-[#EAE5DC] bg-white text-stone-900 font-semibold focus:outline-hidden focus:ring-2 focus:ring-stone-400 cursor-pointer"
                  >
                    {REVIEWERS.map((r) => (
                      <option key={r} value={r}>
                        {r.toUpperCase()} (Senior Reviewer)
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            <div>
              <label className="font-semibold text-stone-700 block mb-1">Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 absolute left-3 top-3 text-stone-400" />
                <input
                  type="password"
                  required={authEnabled}
                  minLength={authEnabled ? 6 : undefined}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full pl-9 pr-3 py-2.5 rounded-xl border border-[#EAE5DC] bg-white text-stone-900 placeholder-stone-400 focus:outline-hidden focus:ring-2 focus:ring-stone-400"
                />
              </div>
            </div>

            {formError && (
              <p className="text-[11px] font-semibold text-rose-700">{formError}</p>
            )}
            {formNote && (
              <p className="text-[11px] font-semibold text-emerald-700">{formNote}</p>
            )}

            <button
              type="submit"
              disabled={busy}
              className={`w-full py-3 rounded-xl font-bold text-xs text-white shadow-md transition-all mt-2 disabled:opacity-60 ${
                selectedRole === 'client'
                  ? 'bg-violet-600 hover:bg-violet-700'
                  : 'bg-stone-900 hover:bg-stone-800'
              }`}
            >
              {busy
                ? (authMode === 'signin' ? 'Signing in…' : 'Creating account…')
                : authMode === 'signin'
                ? `Enter as ${selectedRole === 'client' ? 'Client' : 'Reviewer'}`
                : `Create ${selectedRole === 'client' ? 'Client' : 'Reviewer'} Account`}
            </button>
          </form>

          {/* Toggle between Sign In & Sign Up */}
          <div className="text-center pt-2 border-t border-[#EAE5DC] text-xs text-stone-500">
            {authMode === 'signin' ? (
              <span>
                Don't have an account?{' '}
                <button
                  type="button"
                  onClick={() => setAuthMode('signup')}
                  className="font-bold text-stone-900 hover:underline"
                >
                  Sign Up
                </button>
              </span>
            ) : (
              <span>
                Already have an account?{' '}
                <button
                  type="button"
                  onClick={() => setAuthMode('signin')}
                  className="font-bold text-stone-900 hover:underline"
                >
                  Sign In
                </button>
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
