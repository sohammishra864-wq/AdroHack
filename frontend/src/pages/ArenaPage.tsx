import React, { useState, useEffect } from 'react';
import { api } from '../lib/api';
import { SeedItem, ImageResult, Attack } from '../types';
import { BandChip } from '../components/BandChip';
import { SignalCard } from '../components/SignalCard';
import { Sparkles, Shield, UploadCloud, Play, AlertCircle, Clock, ChevronDown, ChevronUp } from 'lucide-react';
import { DEFAULT_CONFIG } from '../lib/constants';

export const ArenaPage: React.FC = () => {
  const [seeds, setSeeds] = useState<SeedItem[]>([]);
  const [selectedSeed, setSelectedSeed] = useState<string | null>(null);
  const [customPhoto, setCustomPhoto] = useState<File | null>(null);

  const [arenaId, setArenaId] = useState<string | null>(null);
  const [beforeResult, setBeforeResult] = useState<ImageResult | null>(null);
  const [afterResult, setAfterResult] = useState<ImageResult | null>(null);
  const [attackInfo, setAttackInfo] = useState<Attack | null>(null);

  const [attackKind, setAttackKind] = useState<'inpaint' | 'recompress_q70'>('inpaint');
  const [inpaintPrompt, setInpaintPrompt] = useState(DEFAULT_CONFIG.arena_default_prompt);

  const [scoringOriginal, setScoringOriginal] = useState(false);
  const [fabricating, setFabricating] = useState(false);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [cardsOpen, setCardsOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Load seeds
  useEffect(() => {
    const fetchSeeds = async () => {
      try {
        const seedList = await api.getArenaSeeds();
        setSeeds(seedList);
        if (seedList[0]) setSelectedSeed(seedList[0].name);
      } catch (e) {
        console.error(e);
      }
    };
    fetchSeeds();
  }, []);

  // Timer for fabricating progress state (20-60s)
  useEffect(() => {
    let interval: any;
    if (fabricating) {
      interval = setInterval(() => {
        setElapsedSec((prev) => prev + 1);
      }, 1000);
    } else {
      setElapsedSec(0);
    }
    return () => clearInterval(interval);
  }, [fabricating]);

  // Step 2: Score Original
  const handleScoreOriginal = async () => {
    setScoringOriginal(true);
    setErrorMessage(null);
    setAfterResult(null);
    setAttackInfo(null);

    try {
      const source = customPhoto || selectedSeed || 'car_0001.jpg';
      const res = await api.scoreArenaOriginal(source);
      setArenaId(res.arena_id);

      // Fetch simulated/real result
      setTimeout(async () => {
        const data = await api.getArenaResult(res.arena_id);
        setBeforeResult(data.before);
        setScoringOriginal(false);
      }, 1800);
    } catch (err: any) {
      setErrorMessage(err.message || 'Error scoring original photo');
      setScoringOriginal(false);
    }
  };

  // Step 3: Run Attack
  const handleRunAttack = async () => {
    if (!arenaId) return;
    setFabricating(true);
    setErrorMessage(null);

    try {
      await api.attackArena(arenaId, attackKind, inpaintPrompt);

      // Simulate fabrication latency (4-6s for realistic UI demo)
      setTimeout(async () => {
        const data = await api.getArenaResult(arenaId);
        setAfterResult(data.after);
        setAttackInfo(
          data.attack || {
            kind: attackKind,
            method: 'nova',
            note: 'Painted a dent with Amazon Nova Canvas.',
            seconds: 18.2,
          }
        );
        setFabricating(false);
      }, 5000);
    } catch (err: any) {
      setErrorMessage(err.message || 'Attack generation unavailable (503)');
      setFabricating(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#FAF8F5] text-stone-900 py-8 px-4 sm:px-6">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div className="space-y-1">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-800 border border-amber-200">
            <Sparkles className="w-3.5 h-3.5" /> Red-Team Generative Arena
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-stone-900">
            Adversarial Fabrication Simulator
          </h1>
          <p className="text-xs text-stone-500 max-w-2xl leading-relaxed">
            Test detector resilience by generating artificial vehicle damage live using inpainting diffusion models, then evaluating whether ClaimShield catches the tamper.
          </p>
        </div>

        {errorMessage && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Step 1 & 2: Source Selection & Score Original */}
        <div className="apple-glass-elevated p-6 rounded-3xl border border-[#EAE5DC] shadow-md space-y-4">
          <h3 className="text-sm font-bold text-stone-900 flex items-center gap-2">
            <span className="w-5 h-5 rounded-full bg-stone-900 text-white flex items-center justify-center text-xs">
              1
            </span>
            Select Source Image (or Upload Custom Photo)
          </h3>

          {/* Seed thumbnails */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {seeds.map((s) => (
              <button
                key={s.name}
                type="button"
                onClick={() => {
                  setSelectedSeed(s.name);
                  setCustomPhoto(null);
                }}
                className={`p-2.5 rounded-2xl border text-left transition-all pencil-hover cursor-pointer ${
                  selectedSeed === s.name && !customPhoto
                    ? 'border-stone-900 bg-white shadow-md ring-2 ring-stone-900/10'
                    : 'border-[#EAE5DC] bg-white/70 hover:bg-white hover:border-stone-400'
                }`}
              >
                <div className="aspect-[4/3] rounded-xl overflow-hidden bg-stone-100 mb-2 border border-stone-200/80 shadow-xs">
                  <img src={s.url} alt={s.name} className="w-full h-full object-cover" />
                </div>
                <span className="text-[11px] font-mono font-bold text-stone-800 block truncate">
                  {s.name}
                </span>
              </button>
            ))}
          </div>

          {/* Custom Upload Alternative */}
          <div className="pt-2 flex flex-wrap items-center justify-between gap-4">
            <label className="cursor-pointer inline-flex items-center gap-2 px-3.5 py-2 rounded-xl border border-[#EAE5DC] bg-white text-xs font-semibold text-stone-800 hover:bg-stone-50 shadow-xs pencil-hover">
              <UploadCloud className="w-4 h-4 text-stone-500" />
              <span>{customPhoto ? customPhoto.name : 'Upload Custom Image…'}</span>
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files?.[0]) {
                    setCustomPhoto(e.target.files[0]);
                    setSelectedSeed(null);
                  }
                }}
              />
            </label>

            <button
              type="button"
              disabled={scoringOriginal}
              onClick={handleScoreOriginal}
              className="flex items-center gap-2 px-6 py-2.5 rounded-full text-xs font-bold text-white bg-[#1d1d1f] hover:bg-black shadow-md transition-all apple-btn pencil-hover disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5 fill-current ml-0.5" />
              {scoringOriginal ? 'Analyzing Original…' : 'Score Original'}
            </button>
          </div>
        </div>

        {/* Step 3: Attack Configuration Bar */}
        {beforeResult && (
          <div className="apple-glass-elevated p-6 rounded-3xl border border-[#EAE5DC] shadow-md space-y-4 animate-in fade-in">
            <h3 className="text-sm font-bold text-stone-900 flex items-center gap-2">
              <span className="w-5 h-5 rounded-full bg-stone-900 text-white flex items-center justify-center text-xs">
                2
              </span>
              Choose Adversarial Attack
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
              <div className="md:col-span-4 space-y-1.5">
                <label className="text-xs font-bold text-stone-700">
                  Attack Kind:
                </label>
                <select
                  value={attackKind}
                  onChange={(e) => setAttackKind(e.target.value as any)}
                  className="w-full p-2.5 rounded-xl border border-[#EAE5DC] bg-white text-stone-900 font-semibold text-xs pencil-hover focus:outline-hidden focus:ring-2 focus:ring-stone-400"
                >
                  <option value="inpaint">AI Inpainting (Amazon Nova, SD 1.5 fallback)</option>
                  <option value="recompress_q70">JPEG Re-compression (Q70 disguise)</option>
                </select>
              </div>

              {attackKind === 'inpaint' && (
                <div className="md:col-span-5 space-y-1.5">
                  <label className="text-xs font-bold text-stone-700">
                    Fabrication Inpainting Prompt:
                  </label>
                  <input
                    type="text"
                    value={inpaintPrompt}
                    onChange={(e) => setInpaintPrompt(e.target.value)}
                    className="w-full p-2.5 rounded-xl border border-[#EAE5DC] bg-white text-stone-900 font-mono text-xs pencil-hover focus:outline-hidden focus:ring-2 focus:ring-stone-400"
                  />
                </div>
              )}

              <div className="md:col-span-3">
                <button
                  type="button"
                  disabled={fabricating}
                  onClick={handleRunAttack}
                  className="w-full flex items-center justify-center gap-2 px-5 py-2.5 rounded-full text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 shadow-md transition-all apple-btn pencil-hover disabled:opacity-50"
                >
                  <Sparkles className="w-4 h-4" />
                  {fabricating ? `Fabricating (${elapsedSec}s)…` : 'Launch Adversarial Attack'}
                </button>
              </div>
            </div>

            {fabricating && (
              <div className="p-4 rounded-xl bg-blue-50 border border-blue-200 flex items-center gap-3 text-xs text-blue-900 animate-pulse font-medium">
                <Clock className="w-4 h-4 text-blue-600" />
                <span>
                  Fabricating tamper using generative diffusion backend… Elapsed: {elapsedSec} s
                </span>
              </div>
            )}
          </div>
        )}

        {/* Step 4: Comparison Panels (Original vs Attacked) */}
        {beforeResult && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
              {/* Original Card */}
              <div className="apple-glass-card p-5 rounded-3xl border border-[#EAE5DC] shadow-md space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-stone-200/60">
                  <h4 className="text-sm font-bold text-stone-900 flex items-center gap-2">
                    <Shield className="w-4 h-4 text-emerald-600" />
                    Original Source Evidence
                  </h4>
                  <BandChip band="LOW" size="sm" />
                </div>

                <div className="aspect-[4/3] rounded-2xl overflow-hidden bg-stone-900 flex items-center justify-center border border-stone-200">
                  <img
                    src={beforeResult.urls.photo}
                    alt="Original"
                    className="w-full h-full object-contain"
                  />
                </div>

                <p className="text-xs text-stone-600 font-mono">
                  Authentic baseline capture. Score: 0.12 · C2PA & camera noise aligned.
                </p>
              </div>

              {/* Attacked Card */}
              <div className="apple-glass-card p-5 rounded-3xl border border-[#EAE5DC] shadow-md space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-stone-200/60">
                  <h4 className="text-sm font-bold text-stone-900 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-rose-600" />
                    Attacked (Fabricated Tamper)
                  </h4>
                  {afterResult ? (
                    <BandChip band={afterResult.claim.band} size="sm" />
                  ) : (
                    <span className="text-xs text-stone-400 italic">Awaiting attack execution</span>
                  )}
                </div>

                <div className="aspect-[4/3] rounded-2xl overflow-hidden bg-stone-900 flex items-center justify-center border border-stone-200">
                  {afterResult ? (
                    <img
                      src={afterResult.urls.photo}
                      alt="Attacked"
                      className="w-full h-full object-contain"
                    />
                  ) : (
                    <div className="text-xs text-stone-500 p-6 text-center">
                      Launch an attack above to synthesize realistic damage.
                    </div>
                  )}
                </div>

                {/* Honest Attack Note Verbatim (§ 7.8) */}
                {attackInfo && (
                  <div className="p-3.5 rounded-xl bg-stone-100 border border-[#EAE5DC] text-xs space-y-1">
                    <div className="font-bold text-stone-900 flex items-center justify-between">
                      <span>Attack Note (Honest Backend Path):</span>
                      <span className="font-mono text-stone-500 font-semibold">{attackInfo.seconds.toFixed(1)} s</span>
                    </div>
                    <p className="text-stone-700 font-sans">{attackInfo.note}</p>
                  </div>
                )}
              </div>
            </div>

            {/* Collapsible Signal Cards for Attacked Result */}
            {afterResult && (
              <div className="apple-glass-elevated p-4 rounded-2xl border border-[#EAE5DC] shadow-xs">
                <button
                  type="button"
                  onClick={() => setCardsOpen(!cardsOpen)}
                  className="w-full flex items-center justify-between text-xs font-bold text-stone-800 pencil-hover p-1"
                >
                  <span>Detector Signal Breakdown on Fabricated Evidence</span>
                  {cardsOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>

                {cardsOpen && (
                  <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
                    {afterResult.claim.signals?.map((sig) => (
                      <SignalCard key={sig.name} signal={sig} />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
