import React, { useState } from 'react';
import { Signal, ApiConfig } from '../../types';
import { SignalCard } from '../SignalCard';
import { CheckCircle2, XCircle, UserCheck, Camera, RotateCcw, HelpCircle } from 'lucide-react';
import { CameraModal } from '../CameraModal';

interface IdentityTabProps {
  identity: {
    signals: Signal[];
    urls: { id: string; selfie: string };
  } | null;
  config?: ApiConfig;
}

export const IdentityTab: React.FC<IdentityTabProps> = ({ identity, config }) => {
  const [liveSelfieUrl, setLiveSelfieUrl] = useState<string | null>(null);
  const [isCameraOpen, setIsCameraOpen] = useState(false);

  if (!identity) {
    return (
      <div className="flex flex-col items-center justify-center p-12 apple-glass-card rounded-3xl border border-[#EAE5DC] text-center shadow-xs">
        <UserCheck className="w-12 h-12 text-stone-400 mb-3" />
        <h3 className="text-sm font-bold text-stone-800">
          No ID + selfie in this claim.
        </h3>
        <p className="text-xs text-stone-500 max-w-sm mt-1 mb-4">
          Identity biometric verification requires both a photo ID document and a live selfie capture.
        </p>
        <button
          type="button"
          onClick={() => setIsCameraOpen(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-white bg-violet-600 hover:bg-violet-700 shadow-sm transition-all"
        >
          <Camera className="w-4 h-4" />
          <span>Test Live Selfie Camera</span>
        </button>

        <CameraModal
          isOpen={isCameraOpen}
          onClose={() => setIsCameraOpen(false)}
          onCapture={(_, previewUrl) => setLiveSelfieUrl(previewUrl)}
          title="Test Camera Selfie"
          subtitle="Test biometric live facial capture in adjuster view."
        />
      </div>
    );
  }

  const faceMatchSignal = identity.signals.find((s) => s.name === 'face_match');
  // Only claim a verdict when the face check actually ran (abstained / missing → "not checked")
  const notChecked = !faceMatchSignal || faceMatchSignal.score === null;
  const isMismatch = !notChecked && (faceMatchSignal!.score as number) >= 0.5;

  return (
    <div className="space-y-6">
      {/* Big Verdict Line */}
      <div
        className={`flex items-center justify-between p-5 rounded-2xl border-2 shadow-sm ${
          notChecked
            ? 'bg-stone-50 border-stone-200 text-stone-800'
            : isMismatch
            ? 'bg-rose-50 border-rose-200 text-rose-900'
            : 'bg-emerald-50 border-emerald-200 text-emerald-900'
        }`}
      >
        <div className="flex items-center gap-3.5">
          {notChecked ? (
            <HelpCircle className="w-8 h-8 text-stone-500 shrink-0" />
          ) : isMismatch ? (
            <XCircle className="w-8 h-8 text-rose-600 shrink-0" />
          ) : (
            <CheckCircle2 className="w-8 h-8 text-emerald-600 shrink-0" />
          )}
          <div>
            <h3 className="text-lg font-bold tracking-tight">
              {notChecked ? 'Face match not checked' : `Biometric Verdict: ${isMismatch ? 'Different people' : 'Same person'}`}
            </h3>
            <p className="text-xs opacity-90 mt-0.5 font-medium">
              {faceMatchSignal?.reason ||
                (isMismatch
                  ? 'Face embeddings of the ID portrait and the selfie are too far apart.'
                  : 'Facial landmarks between ID portrait and submitted selfie match with high confidence.')}
            </p>
          </div>
        </div>

        {faceMatchSignal?.score !== null && faceMatchSignal?.score !== undefined && (
          <div className="text-right">
            <span className="font-mono text-sm font-bold block">
              mismatch score: {faceMatchSignal.score.toFixed(2)}
            </span>
            <span className="text-[11px] opacity-75 font-mono font-medium">
              conf {faceMatchSignal.confidence.toFixed(2)}
            </span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left (7 cols): ID and Selfie Side by Side */}
        <div className="lg:col-span-7 grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* ID Document Card */}
          <div className="apple-glass-card p-4 rounded-2xl border border-[#EAE5DC] shadow-xs space-y-2">
            <div className="flex items-center justify-between pb-1">
              <span className="text-xs font-bold text-stone-700 uppercase tracking-wider">
                Photo Identification
              </span>
              <span className="text-[10px] font-mono text-stone-500 font-semibold">Government Issued</span>
            </div>
            <div className="aspect-[4/3] rounded-xl overflow-hidden bg-stone-100 border border-stone-200 flex items-center justify-center">
              <img
                src={identity.urls.id}
                alt="Government ID"
                className="w-full h-full object-contain"
              />
            </div>
          </div>

          {/* Live Selfie Card */}
          <div className="apple-glass-card p-4 rounded-2xl border border-[#EAE5DC] shadow-xs space-y-2">
            <div className="flex items-center justify-between pb-1">
              <div>
                <span className="text-xs font-bold text-stone-700 uppercase tracking-wider block">
                  Submitted Live Selfie
                </span>
                <span className="text-[10px] font-mono text-stone-500 font-semibold">
                  {liveSelfieUrl ? 'Live Camera Capture' : 'Captured in App'}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setIsCameraOpen(true)}
                className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-bold text-violet-700 bg-violet-50 hover:bg-violet-100 border border-violet-200 pencil-hover transition-colors cursor-pointer"
                title="Test or capture live selfie with webcam"
              >
                <Camera className="w-3.5 h-3.5" />
                <span>{liveSelfieUrl ? 'Retake' : 'Use Camera'}</span>
              </button>
            </div>
            <div className="aspect-[4/3] rounded-xl overflow-hidden bg-stone-100 border border-stone-200 flex items-center justify-center relative">
              <img
                src={liveSelfieUrl || identity.urls.selfie}
                alt="Claimant Selfie"
                className="w-full h-full object-contain"
              />
              {liveSelfieUrl && (
                <div className="absolute bottom-2 left-2 px-2 py-0.5 rounded-md bg-emerald-600/90 text-white text-[10px] font-bold shadow-xs">
                  Live Stream Captured
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right (5 cols): Identity Signal Cards */}
        <div className="lg:col-span-5 space-y-3">
          <h4 className="text-xs font-bold text-stone-700 uppercase tracking-wider pb-1">
            Biometric & Anti-Spoofing Checks
          </h4>
          {identity.signals.map((sig) => (
            <SignalCard key={sig.name} signal={sig} config={config} />
          ))}
        </div>
      </div>

      <CameraModal
        isOpen={isCameraOpen}
        onClose={() => setIsCameraOpen(false)}
        onCapture={(_, previewUrl) => setLiveSelfieUrl(previewUrl)}
        title="Biometric Selfie Camera"
        subtitle="Test camera facial capture against the ID document in real time."
      />
    </div>
  );
};
