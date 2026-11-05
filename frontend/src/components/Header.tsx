import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  Shield,
  Activity,
  RefreshCw,
  AlertCircle,
  ChevronDown,
  Check,
  Sparkles,
  User,
  LogOut,
  UserCheck,
} from 'lucide-react';
import { api, API_BASE } from '../lib/api';
import { HealthStatus } from '../types';
import { useAuth } from '../context/AuthContext';
import { AuthModal } from './AuthModal';
import { REVIEWERS } from '../lib/constants';

interface HeaderProps {
  onNewClaimClick?: () => void;
}

export const Header: React.FC<HeaderProps> = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, role, openAuthModal, logout, loginAsReviewer, loginAsClient } = useAuth();

  const [health, setHealth] = useState<HealthStatus>({ ok: true, problems: [], device: 'detecting' });
  const [showHealthModal, setShowHealthModal] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [mode, setMode] = useState<'live' | 'mock'>(api.getMode());
  const [apiError, setApiError] = useState<boolean>(false);

  const fetchHealth = async () => {
    try {
      const data = await api.getHealth();
      setHealth(data);
      setApiError(false);
    } catch {
      setApiError(true);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, [mode]);

  const handleModeToggle = (newMode: 'live' | 'mock') => {
    api.setMode(newMode);
    setMode(newMode);
    fetchHealth();
  };

  return (
    <>
      <header className="sticky top-0 z-40 w-full apple-glass border-b border-white/60 transition-colors">
        {/* Live Server unreachable banner (Spec § 8) */}
        {apiError && mode === 'live' && (
          <div className="w-full bg-[#FF3B30] text-white px-4 py-2 text-xs flex items-center justify-between font-medium shadow-sm">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>Can't reach the ClaimShield server at {API_BASE}</span>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => handleModeToggle('mock')}
                className="underline hover:text-white/80 font-semibold"
              >
                Switch to Offline Simulator
              </button>
              <button
                onClick={fetchHealth}
                className="px-2.5 py-0.5 rounded-full bg-white/20 hover:bg-white/30 text-white flex items-center gap-1 font-semibold transition-colors"
              >
                <RefreshCw className="w-3 h-3" /> Retry
              </button>
            </div>
          </div>
        )}

        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          {/* Left: Brand Logo */}
          <Link to="/" className="flex items-center gap-2.5 group shrink-0">
            <div className="w-8 h-8 rounded-xl bg-[#1d1d1f] flex items-center justify-center text-white shadow-md transition-transform group-hover:scale-105">
              <Shield className="w-4 h-4 text-amber-300" />
            </div>
            <span className="font-bold text-base tracking-tight text-[#1d1d1f]">
              ClaimShield
            </span>
          </Link>

          {/* Center: Navigation Box with Centrally Aligned Portals */}
          <nav className="hidden md:flex items-center justify-center">
            <div className="apple-segmented-bg inline-flex items-center gap-1 px-1.5 py-1">
              <Link
                to="/"
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  location.pathname === '/'
                    ? 'apple-segmented-item-active'
                    : 'text-[#6e6e73] hover:text-[#1d1d1f]'
                }`}
              >
                Home
              </Link>

              {/* Client Portal */}
              <Link
                to="/portal"
                className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                  location.pathname.startsWith('/portal')
                    ? 'apple-segmented-item-active text-violet-700'
                    : 'text-[#6e6e73] hover:text-violet-700'
                }`}
              >
                <User className="w-3.5 h-3.5 text-violet-600" />
                <span>Client Portal</span>
              </Link>

              {/* Receiver Portal */}
              <Link
                to="/inbox"
                className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                  location.pathname.startsWith('/inbox') || location.pathname.startsWith('/cases')
                    ? 'apple-segmented-item-active text-amber-700'
                    : 'text-[#6e6e73] hover:text-amber-700'
                }`}
              >
                <Shield className="w-3.5 h-3.5 text-amber-600" />
                <span>Receiver Portal</span>
              </Link>

              <Link
                to="/arena"
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  location.pathname === '/arena'
                    ? 'apple-segmented-item-active'
                    : 'text-[#6e6e73] hover:text-[#1d1d1f]'
                }`}
              >
                Arena
              </Link>

              <Link
                to="/reports"
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  location.pathname === '/reports'
                    ? 'apple-segmented-item-active'
                    : 'text-[#6e6e73] hover:text-[#1d1d1f]'
                }`}
              >
                Reports
              </Link>
            </div>
          </nav>

          {/* Right: Dual Login Options, Role Badge & Health */}
          <div className="flex items-center gap-3 text-xs">
            {/* Backend Simulator / Live Toggle */}
            <div className="hidden lg:flex items-center rounded-lg p-0.5 bg-stone-200/60 border border-[#EAE5DC]">
              <button
                onClick={() => handleModeToggle('mock')}
                className={`px-2.5 py-1 rounded-md text-[11px] font-semibold flex items-center gap-1 transition-all ${
                  mode === 'mock'
                    ? 'bg-white text-stone-900 shadow-xs'
                    : 'text-stone-500 hover:text-stone-900'
                }`}
              >
                <Sparkles className="w-3 h-3 text-amber-500" /> Demo
              </button>
              <button
                onClick={() => handleModeToggle('live')}
                className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all ${
                  mode === 'live'
                    ? 'bg-white text-stone-900 shadow-xs'
                    : 'text-stone-500 hover:text-stone-900'
                }`}
              >
                Live API
              </button>
            </div>

            {/* Health Status Dot (§ 7.10) */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowHealthModal(!showHealthModal)}
                className="p-1.5 rounded-lg hover:bg-stone-200/60 transition-colors flex items-center gap-1.5"
                title={`Health: ${health.ok ? 'All systems operational' : 'Warnings present'}`}
              >
                <span
                  className={`w-2.5 h-2.5 rounded-full ring-2 ring-white shadow-xs transition-colors ${
                    health.ok && health.problems.length === 0
                      ? 'bg-[#2e7d32]'
                      : health.problems.length > 0
                      ? 'bg-[#ef6c00]'
                      : 'bg-[#c62828]'
                  }`}
                />
              </button>

              {/* Health Problems Modal */}
              {showHealthModal && (
                <div className="absolute right-0 mt-2 w-72 p-4 bg-white rounded-2xl shadow-xl border border-[#EAE5DC] z-50 text-xs">
                  <div className="flex items-center justify-between pb-2 border-b border-stone-100">
                    <span className="font-bold text-stone-900 flex items-center gap-1.5">
                      <Activity className="w-3.5 h-3.5 text-stone-400" /> Model Engine Status
                    </span>
                    <span className="font-mono text-[10px] text-stone-400">{health.device}</span>
                  </div>

                  <div className="mt-3 space-y-2">
                    {health.problems.length === 0 ? (
                      <div className="flex items-center gap-2 text-emerald-700 font-semibold">
                        <Check className="w-4 h-4" /> All forensic checks operational
                      </div>
                    ) : (
                      <div>
                        <p className="font-semibold text-amber-700 mb-1">Warnings reported:</p>
                        <ul className="space-y-1 text-stone-600 list-disc list-inside">
                          {health.problems.map((p, i) => (
                            <li key={i}>{p}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* User Session or Dual Login Trigger */}
            {user ? (
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setShowUserMenu(!showUserMenu)}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-full apple-glass hover:bg-white/90 transition-all shadow-xs"
                >
                  <span
                    className={`w-6 h-6 rounded-full flex items-center justify-center font-bold text-[10px] shadow-xs ${
                      user.role === 'client'
                        ? 'bg-violet-100 text-violet-800'
                        : 'bg-amber-100 text-amber-800'
                    }`}
                  >
                    {user.avatarText}
                  </span>
                  <div className="text-left hidden sm:block">
                    <span className="font-semibold text-[#1d1d1f] block leading-tight text-xs">
                      {user.name}
                    </span>
                    <span className="text-[10px] text-[#86868b] capitalize block leading-tight">
                      {user.role}
                    </span>
                  </div>
                  <ChevronDown className="w-3.5 h-3.5 text-[#86868b]" />
                </button>

                {showUserMenu && (
                  <div className="absolute right-0 mt-2 w-56 p-1.5 apple-glass-elevated rounded-2xl shadow-2xl z-50 text-xs space-y-1 animate-in fade-in">
                    <div className="p-2.5 border-b border-black/5">
                      <span className="font-bold text-[#1d1d1f] block">{user.name}</span>
                      <span className="text-[11px] text-[#86868b] font-mono block truncate">
                        {user.email}
                      </span>
                    </div>

                    {user.role === 'client' ? (
                      <button
                        onClick={() => {
                          loginAsReviewer('asha');
                          setShowUserMenu(false);
                          navigate('/inbox');
                        }}
                        className="w-full text-left p-2 rounded-xl hover:bg-black/5 flex items-center gap-2 font-medium text-[#1d1d1f] transition-colors"
                      >
                        <Shield className="w-4 h-4 text-amber-600" />
                        <span>Switch to Reviewer Role</span>
                      </button>
                    ) : (
                      <button
                        onClick={() => {
                          loginAsClient('Marcus Vance');
                          setShowUserMenu(false);
                          navigate('/portal');
                        }}
                        className="w-full text-left p-2 rounded-xl hover:bg-black/5 flex items-center gap-2 font-medium text-[#1d1d1f] transition-colors"
                      >
                        <User className="w-4 h-4 text-violet-600" />
                        <span>Switch to Client Role</span>
                      </button>
                    )}

                    <button
                      onClick={() => {
                        logout();
                        setShowUserMenu(false);
                        navigate('/');
                      }}
                      className="w-full text-left p-2 rounded-xl hover:bg-rose-50 text-rose-600 flex items-center gap-2 font-medium transition-colors"
                    >
                      <LogOut className="w-4 h-4" />
                      <span>Sign Out</span>
                    </button>
                  </div>
                )}
              </div>
            ) : (
              /* Two Login / Signup Options (Apple-Styled) */
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => openAuthModal('client')}
                  className="hidden sm:flex items-center gap-1.5 px-4 py-1.5 rounded-full apple-glass hover:bg-white text-[#1d1d1f] font-semibold text-xs transition-all shadow-xs apple-btn"
                >
                  <User className="w-3.5 h-3.5 text-violet-600" />
                  <span>Client Login</span>
                </button>

                <button
                  type="button"
                  onClick={() => openAuthModal('reviewer')}
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-[#1d1d1f] hover:bg-black text-white font-semibold text-xs transition-all shadow-sm apple-btn"
                >
                  <Shield className="w-3.5 h-3.5 text-amber-300" />
                  <span>Reviewer Login</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Global Auth Modal */}
      <AuthModal />
    </>
  );
};
