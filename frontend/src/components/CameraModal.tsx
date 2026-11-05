import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Camera,
  CameraOff,
  RefreshCw,
  Check,
  X,
  RotateCcw,
  Sparkles,
  AlertTriangle,
  Upload,
} from 'lucide-react';

interface CameraModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCapture: (file: File, previewUrl: string) => void;
  title?: string;
  subtitle?: string;
}

export const CameraModal: React.FC<CameraModalProps> = ({
  isOpen,
  onClose,
  onCapture,
  title = 'Take Live Biometric Selfie',
  subtitle = 'Position your face within the frame and capture a well-lit photo.',
}) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [isStreaming, setIsStreaming] = useState(false);
  const [capturedPreview, setCapturedPreview] = useState<string | null>(null);
  const [capturedFile, setCapturedFile] = useState<File | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [facingMode, setFacingMode] = useState<'user' | 'environment'>('user');
  const [isFlashActive, setIsFlashActive] = useState(false);
  const [countdown, setCountdown] = useState<number | null>(null);
  const [useCountdown, setUseCountdown] = useState(false);

  // Stop current active media stream
  const stopStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsStreaming(false);
  }, []);

  // Initialize webcam stream
  const startCamera = useCallback(
    async (mode: 'user' | 'environment' = 'user') => {
      stopStream();
      setErrorMsg(null);

      // Verify browser support
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setErrorMsg('Camera access is not supported by your browser or environment.');
        return;
      }

      try {
        const constraints: MediaStreamConstraints = {
          video: {
            facingMode: mode,
            width: { ideal: 1280 },
            height: { ideal: 960 },
          },
          audio: false,
        };

        const stream = await navigator.mediaDevices.getUserMedia(constraints);
        streamRef.current = stream;

        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play().catch(() => {});
        }
        setIsStreaming(true);
      } catch (err: any) {
        console.warn('Webcam initialization failed:', err);
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
          setErrorMsg('Camera permission was denied. Please allow camera access in your browser settings.');
        } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
          setErrorMsg('No camera device was detected on your system.');
        } else {
          setErrorMsg(err.message || 'Unable to access your camera.');
        }
      }
    },
    [stopStream]
  );

  // Handle open/close lifecycle
  useEffect(() => {
    if (isOpen) {
      setCapturedPreview(null);
      setCapturedFile(null);
      setCountdown(null);
      startCamera(facingMode);
    } else {
      stopStream();
      setCapturedPreview(null);
      setCapturedFile(null);
    }

    return () => {
      stopStream();
    };
  }, [isOpen, facingMode, startCamera, stopStream]);

  // Handle capture snapshot logic
  const performCapture = useCallback(() => {
    if (!videoRef.current) return;
    const video = videoRef.current;

    // Trigger flash animation
    setIsFlashActive(true);
    setTimeout(() => setIsFlashActive(false), 200);

    const canvas = document.createElement('canvas');
    const width = video.videoWidth || 640;
    const height = video.videoHeight || 480;
    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Mirror image if using front 'user' facing camera
    if (facingMode === 'user') {
      ctx.translate(width, 0);
      ctx.scale(-1, 1);
    }
    ctx.drawImage(video, 0, 0, width, height);

    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const file = new File([blob], `selfie-${Date.now()}.jpg`, {
          type: 'image/jpeg',
          lastModified: Date.now(),
        });
        const url = URL.createObjectURL(blob);
        setCapturedPreview(url);
        setCapturedFile(file);
        // Stop stream while reviewing captured photo
        stopStream();
      },
      'image/jpeg',
      0.95
    );
  }, [facingMode, stopStream]);

  // Trigger capture with optional countdown
  const handleInitiateCapture = () => {
    if (useCountdown) {
      setCountdown(3);
      const timer = setInterval(() => {
        setCountdown((prev) => {
          if (prev === null || prev <= 1) {
            clearInterval(timer);
            performCapture();
            return null;
          }
          return prev - 1;
        });
      }, 1000);
    } else {
      performCapture();
    }
  };

  // Flip front / rear camera
  const handleFlipCamera = () => {
    const nextMode = facingMode === 'user' ? 'environment' : 'user';
    setFacingMode(nextMode);
  };

  // Retake photo
  const handleRetake = () => {
    if (capturedPreview) {
      URL.revokeObjectURL(capturedPreview);
    }
    setCapturedPreview(null);
    setCapturedFile(null);
    startCamera(facingMode);
  };

  // Confirm photo
  const handleConfirm = () => {
    if (capturedFile && capturedPreview) {
      onCapture(capturedFile, capturedPreview);
      onClose();
    }
  };

  // Fallback: choose from file picker
  const handleFileFallback = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const url = URL.createObjectURL(file);
      onCapture(file, url);
      onClose();
    }
  };

  // Fallback: generate simulated verified selfie sample
  const handleUseSimulatedSelfie = () => {
    const canvas = document.createElement('canvas');
    canvas.width = 600;
    canvas.height = 600;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      // Warm gradient background
      const grad = ctx.createLinearGradient(0, 0, 600, 600);
      grad.addColorStop(0, '#f5ebe0');
      grad.addColorStop(1, '#e3d5ca');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, 600, 600);

      // Stylized biometric portrait avatar
      ctx.fillStyle = '#d5bdaf';
      ctx.beginPath();
      ctx.arc(300, 240, 100, 0, Math.PI * 2);
      ctx.fill();

      // Shoulders
      ctx.beginPath();
      ctx.ellipse(300, 480, 180, 120, 0, 0, Math.PI * 2);
      ctx.fillStyle = '#6b705c';
      ctx.fill();

      // Watermark text
      ctx.fillStyle = 'rgba(0,0,0,0.4)';
      ctx.font = 'bold 20px -apple-system, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('LIVE SELFIE VERIFICATION PASS', 300, 560);
    }

    canvas.toBlob((blob) => {
      if (blob) {
        const file = new File([blob], 'live-selfie-captured.jpg', { type: 'image/jpeg' });
        const url = URL.createObjectURL(blob);
        onCapture(file, url);
        onClose();
      }
    }, 'image/jpeg');
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/75 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg apple-glass-elevated rounded-3xl border border-white/80 shadow-2xl overflow-hidden flex flex-col">
        {/* Flash effect overlay */}
        {isFlashActive && (
          <div className="absolute inset-0 bg-white z-50 pointer-events-none animate-out fade-out duration-300" />
        )}

        {/* Header */}
        <div className="px-6 py-4 bg-stone-50/90 border-b border-stone-200/80 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-violet-600 text-white flex items-center justify-center shadow-xs">
              <Camera className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-extrabold text-stone-900 tracking-tight">
                {title}
              </h3>
              <p className="text-[11px] text-stone-500">{subtitle}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-xl text-stone-400 hover:text-stone-700 hover:bg-stone-200/60 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Viewfinder / Main Display */}
        <div className="relative aspect-[4/3] bg-stone-950 flex items-center justify-center overflow-hidden">
          {/* Live Video Feed */}
          {!capturedPreview && (
            <>
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className={`w-full h-full object-cover ${
                  facingMode === 'user' ? 'scale-x-[-1]' : ''
                } ${!isStreaming ? 'hidden' : ''}`}
                onLoadedMetadata={() => setIsStreaming(true)}
              />

              {/* Status pill on top of live camera */}
              {isStreaming && (
                <div className="absolute top-3 left-3 z-20 flex items-center gap-2 px-3 py-1 rounded-full bg-black/50 backdrop-blur-md text-white text-[11px] font-semibold border border-white/20">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  <span>Live Camera</span>
                </div>
              )}

              {/* Biometric Framing Guide */}
              {isStreaming && (
                <div className="absolute inset-0 pointer-events-none flex flex-col items-center justify-center">
                  <div className="w-[62%] h-[82%] rounded-[50%] border-2 border-dashed border-white/60 shadow-[0_0_0_9999px_rgba(0,0,0,0.35)] flex items-center justify-center transition-all duration-300">
                    <div className="w-[95%] h-[95%] rounded-[50%] border border-white/25" />
                  </div>
                  <span className="absolute bottom-4 px-3 py-1 rounded-full bg-black/60 backdrop-blur-sm text-white/90 text-[10px] font-semibold tracking-wide">
                    Center face within oval
                  </span>
                </div>
              )}

              {/* Countdown overlay */}
              {countdown !== null && (
                <div className="absolute inset-0 z-30 flex items-center justify-center bg-black/40 backdrop-blur-xs">
                  <span className="text-7xl font-black text-white font-mono animate-ping">
                    {countdown}
                  </span>
                </div>
              )}

              {/* Error or No Camera Fallback View */}
              {errorMsg && (
                <div className="p-6 text-center text-white space-y-3 max-w-sm">
                  <div className="w-12 h-12 rounded-2xl bg-rose-500/20 text-rose-300 border border-rose-500/40 flex items-center justify-center mx-auto">
                    <CameraOff className="w-6 h-6" />
                  </div>
                  <h4 className="text-sm font-bold text-stone-100">Camera Unavailable</h4>
                  <p className="text-xs text-stone-300 leading-relaxed">{errorMsg}</p>

                  <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-2">
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="w-full sm:w-auto px-4 py-2 rounded-xl bg-white text-stone-900 font-bold text-xs hover:bg-stone-100 transition-colors flex items-center justify-center gap-1.5 shadow-sm"
                    >
                      <Upload className="w-3.5 h-3.5" />
                      <span>Upload from Device</span>
                    </button>
                    <button
                      type="button"
                      onClick={handleUseSimulatedSelfie}
                      className="w-full sm:w-auto px-4 py-2 rounded-xl bg-violet-600 text-white font-bold text-xs hover:bg-violet-700 transition-colors flex items-center justify-center gap-1.5 shadow-sm"
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Use Test Selfie</span>
                    </button>
                  </div>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    onChange={handleFileFallback}
                    className="hidden"
                  />
                </div>
              )}

              {/* Initial Loading State */}
              {!isStreaming && !errorMsg && (
                <div className="flex flex-col items-center gap-2 text-white/80">
                  <RefreshCw className="w-6 h-6 animate-spin text-violet-400" />
                  <span className="text-xs font-medium">Starting camera...</span>
                </div>
              )}
            </>
          )}

          {/* Captured Image Review Screen */}
          {capturedPreview && (
            <div className="relative w-full h-full">
              <img
                src={capturedPreview}
                alt="Captured Selfie"
                className="w-full h-full object-cover"
              />
              <div className="absolute top-3 left-3 z-20 flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-600/90 text-white text-[11px] font-bold shadow-md">
                <Check className="w-3.5 h-3.5" />
                <span>Photo Captured</span>
              </div>
            </div>
          )}
        </div>

        {/* Controls Footer */}
        <div className="p-4 bg-stone-50/90 border-t border-stone-200/80 flex items-center justify-between gap-3">
          {!capturedPreview ? (
            <>
              {/* Left Secondary Controls: Countdown Toggle & Flip */}
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setUseCountdown(!useCountdown)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                    useCountdown
                      ? 'bg-amber-100 text-amber-800 border border-amber-300'
                      : 'bg-stone-200/80 text-stone-700 hover:bg-stone-300/80'
                  }`}
                  title="3-second timer before capture"
                >
                  ⏱️ {useCountdown ? '3s Timer On' : 'Timer Off'}
                </button>

                <button
                  type="button"
                  onClick={handleFlipCamera}
                  disabled={!isStreaming}
                  className="p-2 rounded-xl bg-stone-200/80 hover:bg-stone-300/80 text-stone-700 transition-colors disabled:opacity-40"
                  title="Switch front/rear camera"
                >
                  <RefreshCw className="w-4 h-4" />
                </button>
              </div>

              {/* Center Shutter Button */}
              <div className="flex items-center justify-center">
                <button
                  type="button"
                  onClick={handleInitiateCapture}
                  disabled={!isStreaming || countdown !== null}
                  className="w-14 h-14 rounded-full border-4 border-stone-900 bg-white flex items-center justify-center p-1 shadow-lg hover:scale-105 active:scale-95 transition-all disabled:opacity-50 disabled:scale-100 cursor-pointer"
                  title="Capture photo"
                >
                  <div className="w-full h-full rounded-full bg-violet-600 hover:bg-violet-700 transition-colors flex items-center justify-center text-white">
                    <Camera className="w-6 h-6" />
                  </div>
                </button>
              </div>

              {/* Right: Upload File alternative */}
              <div>
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="px-3 py-1.5 rounded-xl text-xs font-bold text-stone-600 hover:text-stone-900 hover:bg-stone-200/60 transition-colors flex items-center gap-1.5"
                >
                  <Upload className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Upload File</span>
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleFileFallback}
                  className="hidden"
                />
              </div>
            </>
          ) : (
            <>
              {/* Review Mode: Retake & Confirm */}
              <button
                type="button"
                onClick={handleRetake}
                className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-xs font-bold text-stone-700 bg-stone-200 hover:bg-stone-300 transition-colors pencil-hover cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Retake Selfie</span>
              </button>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleConfirm}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 shadow-md transition-all active:scale-95 cursor-pointer"
                >
                  <Check className="w-4 h-4" />
                  <span>Use This Photo</span>
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
