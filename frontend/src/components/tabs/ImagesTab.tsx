import React, { useState, useEffect, useRef } from 'react';
import { ImageResult, Signal, ApiConfig, Region } from '../../types';
import { SignalCard } from '../SignalCard';
import { SunburstChart } from '../charts/SunburstChart';
import { AlertTriangle, Layers, Eye, EyeOff } from 'lucide-react';

interface ImagesTabProps {
  image: ImageResult;
  signals: Signal[];
  config?: ApiConfig;
}

export const ImagesTab: React.FC<ImagesTabProps> = ({ image, signals, config }) => {
  const [activeOverlay, setActiveOverlay] = useState<'heatmap' | 'reconstruction'>('heatmap');
  const [opacity, setOpacity] = useState<number>(50);
  const [showRegions, setShowRegions] = useState<boolean>(true);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Filter signals relevant to this image (fast and deep tiers, plus image lane)
  const imageSignals = signals.filter(
    (s) => s.tier === 'fast' || s.tier === 'deep'
  );

  const familyMapSignal = signals.find((s) => s.name === 'family_map');
  const sunburstData = familyMapSignal?.evidence?.sunburst;

  // Render photo + tinted red overlay on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const baseImg = new Image();
    baseImg.crossOrigin = 'anonymous';
    baseImg.src = image.urls.photo;

    baseImg.onload = () => {
      canvas.width = baseImg.naturalWidth || 800;
      canvas.height = baseImg.naturalHeight || 550;

      // 1. Draw base photo
      ctx.drawImage(baseImg, 0, 0, canvas.width, canvas.height);

      // 2. Determine overlay URL
      const overlayUrl =
        activeOverlay === 'heatmap' ? image.urls.heatmap : image.urls.reconstruction;

      if (overlayUrl && opacity > 0) {
        const overlayImg = new Image();
        overlayImg.crossOrigin = 'anonymous';
        overlayImg.src = overlayUrl;

        overlayImg.onload = () => {
          // Offscreen canvas to tint grayscale white into vibrant red
          const offCanvas = document.createElement('canvas');
          offCanvas.width = canvas.width;
          offCanvas.height = canvas.height;
          const offCtx = offCanvas.getContext('2d');
          if (!offCtx) return;

          offCtx.drawImage(overlayImg, 0, 0, canvas.width, canvas.height);
          const imgData = offCtx.getImageData(0, 0, canvas.width, canvas.height);
          const data = imgData.data;

          // Grayscale tint: white pixels (high value) become red (255, 0, 0)
          for (let i = 0; i < data.length; i += 4) {
            const gray = (data[i] + data[i + 1] + data[i + 2]) / 3;
            // Tint to red with intensity proportional to grayscale value
            data[i] = 220; // R
            data[i + 1] = 20; // G
            data[i + 2] = 20; // B
            data[i + 3] = Math.round(gray * (opacity / 100)); // Alpha based on slider & heat
          }

          offCtx.putImageData(imgData, 0, 0);
          ctx.drawImage(offCanvas, 0, 0);

          // 3. Draw region boxes if enabled
          if (showRegions && image.claim.regions) {
            drawRegionBoxes(ctx, image.claim.regions, canvas.width, canvas.height);
          }
        };
      } else if (showRegions && image.claim.regions) {
        drawRegionBoxes(ctx, image.claim.regions, canvas.width, canvas.height);
      }
    };
  }, [image, activeOverlay, opacity, showRegions]);

  const drawRegionBoxes = (
    ctx: CanvasRenderingContext2D,
    regions: Region[],
    width: number,
    height: number
  ) => {
    const letters = ['A', 'B', 'C', 'D', 'E'];
    regions.forEach((region, i) => {
      const [x1, y1, x2, y2] = region.box;
      const boxW = x2 - x1;
      const boxH = y2 - y1;

      // Yellow outline box
      ctx.strokeStyle = '#facc15'; // Yellow-400
      ctx.lineWidth = 3;
      ctx.setLineDash([6, 4]);
      ctx.strokeRect(x1, y1, boxW, boxH);
      ctx.setLineDash([]); // Reset

      // Region Label Pill (e.g. Region A)
      const label = `Region ${letters[i] || i + 1}`;
      ctx.font = 'bold 14px Inter, sans-serif';
      const textMetrics = ctx.measureText(label);
      const pillW = textMetrics.width + 16;
      const pillH = 24;

      ctx.fillStyle = '#facc15';
      ctx.fillRect(x1, Math.max(0, y1 - pillH), pillW, pillH);

      ctx.fillStyle = '#1e293b';
      ctx.fillText(label, x1 + 8, Math.max(16, y1 - 6));
    });
  };

  const hasReconstruction = !!image.urls.reconstruction;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      {/* Left Column (60%): Canvas + Controls + Regions */}
      <div className="lg:col-span-7 space-y-4">
        {/* Quality flag warning banner */}
        {image.quality_flag && (
          <div className="flex items-center gap-3 p-3.5 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 text-xs">
            <AlertTriangle className="w-5 h-5 shrink-0 text-amber-600" />
            <div>
              <span className="font-bold">Image Quality Warning: </span>
              {image.quality_reasons.join(', ')}
            </div>
          </div>
        )}

        {/* Canvas Display Card */}
        <div
          ref={containerRef}
          className="relative bg-stone-900 rounded-3xl overflow-hidden border border-stone-300 shadow-md group"
        >
          <canvas
            ref={canvasRef}
            className="w-full h-auto block max-h-[520px] object-contain mx-auto"
          />

          {/* Floating Canvas Badges */}
          <div className="absolute top-3 left-3 flex items-center gap-2">
            <span className="px-2.5 py-1 rounded-md text-[11px] font-mono font-medium bg-black/70 backdrop-blur-md text-white border border-white/10">
              {image.name}
            </span>
            <span className="px-2 py-1 rounded-md text-[10px] font-mono text-zinc-300 bg-black/60 backdrop-blur-md">
              SHA: {image.sha256.substring(0, 10)}…
            </span>
          </div>
        </div>

        {/* Overlay Control Bar */}
        <div className="apple-glass-card p-4 rounded-2xl border border-[#EAE5DC] shadow-xs flex flex-wrap items-center justify-between gap-4 text-xs">
          {/* Overlay Toggles */}
          <div className="flex items-center gap-2">
            <span className="text-stone-700 font-bold flex items-center gap-1.5">
              <Layers className="w-4 h-4 text-stone-500" /> Overlay:
            </span>
            <div className="inline-flex rounded-xl p-0.5 bg-stone-100 border border-[#EAE5DC]">
              <button
                type="button"
                onClick={() => setActiveOverlay('heatmap')}
                className={`px-3 py-1 rounded-lg font-bold transition-all cursor-pointer ${
                  activeOverlay === 'heatmap'
                    ? 'bg-white text-stone-900 shadow-xs'
                    : 'text-stone-500 hover:text-stone-900'
                }`}
              >
                Edit heatmap
              </button>
              <button
                type="button"
                disabled={!hasReconstruction}
                onClick={() => setActiveOverlay('reconstruction')}
                className={`px-3 py-1 rounded-lg font-bold transition-all ${
                  !hasReconstruction
                    ? 'opacity-40 cursor-not-allowed text-stone-400'
                    : activeOverlay === 'reconstruction'
                    ? 'bg-white text-stone-900 shadow-xs'
                    : 'text-stone-500 hover:text-stone-900'
                }`}
                title={!hasReconstruction ? 'Reconstruction test running in deep scan...' : ''}
              >
                Reconstruction map {!hasReconstruction && '⏳'}
              </button>
            </div>
          </div>

          {/* Opacity Slider */}
          <div className="flex items-center gap-3 flex-1 min-w-[200px] max-w-[260px]">
            <span className="text-stone-700 font-bold shrink-0">Opacity:</span>
            <input
              type="range"
              min="0"
              max="100"
              value={opacity}
              onChange={(e) => setOpacity(Number(e.target.value))}
              className="w-full accent-rose-600 h-1.5 bg-stone-200 rounded-lg cursor-pointer"
            />
            <span className="font-mono text-stone-900 w-8 text-right font-bold">
              {opacity}%
            </span>
          </div>

          {/* Region Toggle */}
          <button
            type="button"
            onClick={() => setShowRegions(!showRegions)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-[#EAE5DC] bg-white text-stone-800 hover:bg-stone-50 shadow-xs pencil-hover font-semibold transition-colors cursor-pointer"
          >
            {showRegions ? <Eye className="w-3.5 h-3.5 text-amber-500" /> : <EyeOff className="w-3.5 h-3.5 text-stone-400" />}
            <span>Boxes</span>
          </button>
        </div>

        {/* Region List */}
        {image.claim.regions && image.claim.regions.length > 0 && (
          <div className="apple-glass-card p-4 rounded-2xl border border-[#EAE5DC] shadow-xs space-y-2">
            <h4 className="text-xs font-bold text-stone-800 uppercase tracking-wider">
              Detected Regions
            </h4>
            <div className="space-y-2">
              {image.claim.regions.map((reg, idx) => (
                <div
                  key={idx}
                  className="flex items-start justify-between gap-3 p-3 rounded-xl bg-stone-50 border border-stone-200 text-xs"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded-md bg-yellow-400 text-stone-950 font-bold font-mono text-[10px]">
                        Region {['A', 'B', 'C', 'D'][idx] || idx + 1}
                      </span>
                      <span className="font-mono text-stone-500 font-medium text-[11px]">
                        [coords: {reg.box.join(', ')}]
                      </span>
                    </div>
                    <p className="text-stone-800 font-normal leading-relaxed">{reg.reason}</p>
                  </div>

                  {reg.stage === 2 && (
                    <span className="shrink-0 px-2.5 py-1 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                      corroborated by reconstruction test
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Right Column (40%): Streamed Signal Cards + Sunburst */}
      <div className="lg:col-span-5 space-y-3.5">
        <div className="flex items-center justify-between pb-1">
          <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
            Image Signal Stream ({imageSignals.length} checks)
          </h3>
          <span className="text-[11px] font-mono text-zinc-400">Order of arrival</span>
        </div>

        {/* Signals */}
        <div className="space-y-2.5">
          {imageSignals.map((sig) => (
            <SignalCard key={sig.name} signal={sig} config={config} />
          ))}
        </div>

        {/* Generator Family Sunburst */}
        {sunburstData && <SunburstChart sunburst={sunburstData} />}

        {/* Footer timing caption */}
        <div className="mt-4 pt-3 border-t border-[#EAE5DC] text-center font-mono text-[11px] text-stone-500 font-medium">
          first card {fmtS(image.timing.first_card_s)} · fast tier{' '}
          {fmtS(image.timing.fast_tier_s)} · deep{' '}
          {image.timing.deep_s ? fmtS(image.timing.deep_s) : 'running…'}
        </div>
      </div>
    </div>
  );
};

// sub-second timings read better in ms ("0.0 s" looked like a missing value)
function fmtS(s: number | null | undefined): string {
  if (s === null || s === undefined) return '—';
  return s < 1 ? `${Math.round(s * 1000)} ms` : `${s.toFixed(1)} s`;
}
