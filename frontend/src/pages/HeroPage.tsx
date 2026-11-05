import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  Shield,
  Play,
  ArrowRight,
  Sparkles,
  User,
  ChevronRight,
  X,
  FileCheck2,
  CheckCircle,
} from 'lucide-react';

export const HeroPage: React.FC = () => {
  const [showDemoModal, setShowDemoModal] = useState(false);
  const { openAuthModal } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="relative min-h-[calc(100vh-4rem)] overflow-hidden ripple-bg text-stone-900 flex flex-col justify-between">
      {/* Decorative Radial Ambient Rings simulating liquid ripples */}
      <div className="absolute inset-0 pointer-events-none flex items-center justify-center overflow-hidden">
        <div className="w-[850px] h-[850px] rounded-full border border-stone-300/30 animate-pulse opacity-60" />
        <div className="w-[1150px] h-[1150px] rounded-full border border-stone-300/20" />
        <div className="w-[1450px] h-[1450px] rounded-full border border-stone-300/15" />
      </div>

      {/* Main Hero Container */}
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 pt-8 pb-16 w-full flex-1 flex flex-col justify-between">
        {/* Top Center Pill: Protection For All */}
        <div className="flex items-center justify-center w-full mb-4">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/95 border border-[#EAE5DC] shadow-xs text-xs font-bold tracking-wider uppercase text-stone-800">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
            <Shield className="w-3.5 h-3.5 text-amber-500 fill-amber-400" />
            <span>Protection For All</span>
          </div>
        </div>

        {/* Centerpiece Hero Title with 3D Glass Bubble Cat */}
        <div className="my-auto py-8 text-center flex flex-col items-center">
          <h1 className="text-4xl sm:text-6xl lg:text-7xl font-semibold tracking-[-0.035em] text-[#1d1d1f] leading-[1.08] select-none font-sans max-w-5xl">
            Claims verified in seconds.
            <br />
            <span className="inline-flex items-center justify-center flex-wrap gap-3 mt-2">
              <span>Fraud caught</span>

              {/* 3D Glass Sphere with Cat Asset inside - Enhanced Apple Specular Orb */}
              <span className="relative inline-flex items-center justify-center w-16 h-16 sm:w-20 sm:h-20 lg:w-24 lg:h-24 rounded-full glass-orb align-middle mx-1 shadow-2xl ring-8 ring-white/50 backdrop-blur-md transition-transform hover:scale-105 cursor-pointer">
                {/* Refractive highlight */}
                <span className="absolute top-2 left-4 w-7 h-3 rounded-full bg-white/90 -rotate-30 filter blur-[0.5px]" />
                {/* Cat face inside orb */}
                <span className="text-3xl sm:text-4xl select-none filter drop-shadow-md">
                  🐱
                </span>
                {/* Bubble caustic glow */}
                <span className="absolute inset-0 rounded-full border border-white/80 pointer-events-none" />
              </span>

              <span>in real-time.</span>
            </span>
          </h1>

          <p className="mt-5 text-sm sm:text-base text-[#6e6e73] max-w-xl mx-auto leading-relaxed font-normal tracking-[-0.01em]">
            Instant approval for genuine policyholders, deep AI forensics for adjusters.
          </p>

          {/* Dual Audience Action Buttons (Apple-Style Squircle Pills) */}
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3.5 sm:gap-4">
            {/* Play Button */}
            <button
              onClick={() => setShowDemoModal(true)}
              className="flex items-center gap-2.5 px-6 py-3 rounded-full bg-[#1d1d1f] text-white font-semibold text-xs tracking-tight hover:bg-black transition-all shadow-md active:scale-95 apple-btn"
            >
              <div className="w-4 h-4 rounded-full bg-white text-[#1d1d1f] flex items-center justify-center">
                <Play className="w-2.5 h-2.5 fill-current ml-0.5" />
              </div>
              <span>SEE HOW IT WORKS</span>
            </button>

            {/* Client Portal Button */}
            <Link
              to="/portal"
              className="flex items-center gap-2 px-6 py-3 rounded-full apple-glass-elevated text-violet-700 hover:text-violet-800 border border-violet-200/80 font-semibold text-xs tracking-tight transition-all shadow-xs group apple-btn"
            >
              <User className="w-4 h-4 text-violet-600" />
              <span>CLIENT PORTAL</span>
              <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-1" />
            </Link>

            {/* Receiver Portal Button */}
            <Link
              to="/inbox"
              className="flex items-center gap-2 px-6 py-3 rounded-full apple-glass text-[#1d1d1f] hover:bg-white border border-white/80 font-semibold text-xs tracking-tight transition-all shadow-xs group apple-btn"
            >
              <Shield className="w-4 h-4 text-amber-600" />
              <span>RECEIVER PORTAL</span>
              <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-1" />
            </Link>
          </div>
        </div>

        {/* Bottom Bento Showcase Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full pt-8 items-stretch">
          {/* Bento Card 1: Warm Honey Ochre (X Faster Claim Processing) */}
          <div className="relative rounded-[2.25rem] p-7 overflow-hidden bg-gradient-to-br from-[#F5A623] to-[#F7B731] text-[#1d1d1f] shadow-2xl flex flex-col justify-between min-h-[240px] group transition-all hover:-translate-y-1 border border-white/60">
            <div className="z-10">
              <div className="flex items-baseline">
                <span className="text-5xl sm:text-6xl font-black tracking-[-0.04em] font-sans">2–6s</span>
              </div>
              <p className="font-extrabold text-sm text-amber-950 leading-tight mt-1 max-w-[170px] tracking-tight">
                Per Claim, End to End
              </p>
              <p className="text-xs text-amber-950/75 mt-1.5 max-w-[160px] leading-snug">
                Photos, PDFs and ID checked on one GPU, cards streaming as they finish.
              </p>
            </div>

            {/* Forensics Check Mock Cutout Graphic */}
            <div className="absolute right-0 bottom-0 w-[55%] h-[85%] rounded-tl-3xl overflow-hidden bg-white/25 border-t border-l border-white/60 shadow-inner flex flex-col justify-end p-3 backdrop-blur-xs">
              <div className="w-full h-[75%] rounded-2xl bg-black/5 border border-white/70 p-2 flex flex-col justify-between">
                <div className="w-full h-8 rounded-xl bg-white/70 border border-white/80 flex items-center justify-center text-[10px] font-bold text-stone-900 tracking-tight shadow-xs">
                  FAST TIER → DEEP TIER
                </div>
                <div className="grid grid-cols-2 gap-1.5 text-[9px] font-bold text-amber-950">
                  <div className="h-6 rounded-lg bg-white/50 flex items-center justify-center">C2PA · EXIF</div>
                  <div className="h-6 rounded-lg bg-white/50 flex items-center justify-center">CLIP · TruFor</div>
                </div>
              </div>
            </div>
          </div>

          {/* Bento Card 2: Vivid Royal Apple Violet ($YM Fraud Losses Prevented) */}
          <div className="relative rounded-[2.25rem] p-7 overflow-hidden bg-gradient-to-br from-[#5E5CE6] to-[#7B79FF] text-white shadow-2xl flex flex-col justify-between min-h-[240px] group transition-all hover:-translate-y-1 border border-white/40">
            {/* Orbital Rings Background */}
            <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
              <div className="w-48 h-48 rounded-full border border-white/20" />
              <div className="w-64 h-64 rounded-full border border-white/15" />
            </div>

            {/* Orbiting Avatar Cutouts */}
            <div className="absolute top-5 right-8 w-8 h-8 rounded-full apple-glass border border-white/60 flex items-center justify-center text-xs shadow-md">
              👨‍💼
            </div>
            <div className="absolute bottom-6 left-6 w-8 h-8 rounded-full apple-glass border border-white/60 flex items-center justify-center text-xs shadow-md">
              👩‍⚕️
            </div>

            <div className="z-10 my-auto text-center flex flex-col items-center">
              <div className="flex items-baseline justify-center">
                <span className="text-5xl sm:text-6xl font-black tracking-[-0.04em] font-sans">0.898</span>
                <span className="text-3xl font-extrabold ml-1 text-amber-300">AUC</span>
              </div>
              <span className="text-xs font-bold tracking-[0.15em] uppercase text-white/95 mt-1">
                ON AN UNSEEN GENERATOR
              </span>
              <p className="text-[11px] text-white/80 mt-1 max-w-[210px] leading-tight">
                Flux was never seen in training, and it is still detected.
              </p>
            </div>

            {/* Brand Corner */}
            <div className="z-10 flex items-center justify-between text-[11px] text-white/80 pt-2">
              <span className="font-mono">Live Defense</span>
              <div className="flex items-center gap-1 font-bold">
                <Shield className="w-3.5 h-3.5 text-amber-300" /> ClaimShield
              </div>
            </div>
          </div>

          {/* Bento Card 3: Frosted White Cream Glass (Zero-Knowledge Privacy) */}
          <div className="relative rounded-[2.25rem] p-7 apple-glass-elevated text-[#1d1d1f] shadow-2xl flex flex-col justify-between min-h-[240px] group transition-all hover:-translate-y-1 border border-white/90">
            {/* Floating 3D Bubble with Miniature Yellow Car */}
            <div className="absolute -top-7 right-6 w-20 h-20 rounded-full glass-orb flex items-center justify-center shadow-2xl ring-4 ring-white/60">
              <span className="text-3xl select-none filter drop-shadow">🚗</span>
            </div>

            <div className="space-y-1.5 pt-2">
              <span className="inline-block text-xs font-semibold text-[#86868b] tracking-tight">
                Privacy by Design
              </span>
              <h3 className="text-2xl font-bold tracking-tight text-[#1d1d1f] leading-snug">
                Zero-Knowledge <span className="text-[#5E5CE6] font-extrabold">Privacy</span>
              </h3>
              <p className="text-xs text-[#86868b] leading-relaxed">
                Uploaded photos and documents are auto-deleted immediately after scoring ends. Only cryptographic hashes remain in the audit trail.
              </p>
            </div>

            <div className="pt-4 border-t border-black/5">
              <Link
                to="/inbox"
                className="inline-flex items-center gap-1.5 text-xs font-bold text-[#1d1d1f] hover:text-[#5E5CE6] transition-colors uppercase tracking-wider underline underline-offset-4"
              >
                <span>OPEN THE CLAIMS INBOX</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Interactive "See How It Works" Walkthrough Modal */}
      {showDemoModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 backdrop-blur-sm p-4 animate-in fade-in">
          <div className="w-full max-w-xl bg-white rounded-3xl p-6 border border-[#EAE5DC] shadow-2xl space-y-5">
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-stone-900 text-white flex items-center justify-center">
                  <Shield className="w-4 h-4 text-amber-300" />
                </div>
                <h3 className="text-sm font-bold text-stone-900">How ClaimShield Works</h3>
              </div>
              <button
                onClick={() => setShowDemoModal(false)}
                className="p-1 rounded-lg text-stone-400 hover:text-stone-700 hover:bg-stone-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div className="p-4 rounded-2xl bg-violet-50/60 border border-violet-100 space-y-2">
                <div className="flex items-center gap-2 font-bold text-violet-800">
                  <User className="w-4 h-4" />
                  <span>For Clients (Policyholders)</span>
                </div>
                <ul className="space-y-1.5 text-stone-600 leading-relaxed list-disc list-inside">
                  <li>Upload damage photos & repair estimates online in seconds.</li>
                  <li>Live biometric match with ID ensures zero account takeover.</li>
                  <li>Instant approvals for legitimate claims with fast direct deposit.</li>
                </ul>
              </div>

              <div className="p-4 rounded-2xl bg-amber-50/60 border border-amber-100 space-y-2">
                <div className="flex items-center gap-2 font-bold text-amber-800">
                  <Shield className="w-4 h-4" />
                  <span>For Adjusters (Reviewers)</span>
                </div>
                <ul className="space-y-1.5 text-stone-600 leading-relaxed list-disc list-inside">
                  <li>Detects AI inpainting with an edit-localization heatmap and noise forensics.</li>
                  <li>Incremental PDF version diffs catch inflated invoice totals.</li>
                  <li>Waterfall score attribution and tamper history audit trails.</li>
                </ul>
              </div>
            </div>

            <div className="pt-2 flex justify-end gap-2 border-t border-stone-100">
              <button
                type="button"
                onClick={() => {
                  setShowDemoModal(false);
                  openAuthModal('client');
                }}
                className="px-4 py-2 rounded-xl text-xs font-bold text-violet-700 bg-violet-50 hover:bg-violet-100"
              >
                Login as Client
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowDemoModal(false);
                  openAuthModal('reviewer');
                }}
                className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-stone-900 hover:bg-stone-800 shadow-md"
              >
                Login as Reviewer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
