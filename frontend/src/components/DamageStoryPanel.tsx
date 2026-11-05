import React from 'react';
import { Car } from 'lucide-react';
import { Signal } from '../types';

// Damage vs story (backend signal `damage_story`): what the claimant says happened against what
// CLIP sees in the photos. Shown only when the story says something checkable.
const SEVERITY = ['No visible damage', 'Light scratch', 'Dent', 'Severe crash damage'];
const STORY_SEVERITY: Record<number, string> = { 1: 'Minor', 2: 'Moderate', 3: 'Severe crash' };

export const DamageStoryPanel: React.FC<{ signal?: Signal }> = ({ signal }) => {
  if (!signal || signal.applicable === false || signal.score === null) return null;
  const ev = signal.evidence || {};
  const sev: number[] = Array.isArray(ev.severity_probs) ? ev.severity_probs : [];
  const loc: Record<string, number> = ev.location_probs || {};
  const mismatch = (signal.score ?? 0) > 0;

  return (
    <div className="apple-glass-card p-5 rounded-2xl border border-[#EAE5DC] shadow-xs space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-bold text-stone-700 uppercase tracking-wider flex items-center gap-1.5">
          <Car className="w-4 h-4 text-stone-700" />
          Damage vs Story
        </h4>
        <span
          className={`inline-block px-2 py-0.5 rounded-sm font-bold uppercase text-[10px] ${
            mismatch ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'
          }`}
        >
          {mismatch ? 'does not fit' : 'consistent'}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
        <div className="bg-stone-50/80 p-3 rounded-xl border border-[#EAE5DC] space-y-1.5">
          <div className="font-bold text-stone-800">Claimant says</div>
          <div className="font-mono text-stone-700">
            impact: <span className="font-bold text-stone-900">{ev.story_location ?? 'not stated'}</span>
          </div>
          <div className="font-mono text-stone-700">
            severity:{' '}
            <span className="font-bold text-stone-900">
              {ev.story_severity ? STORY_SEVERITY[ev.story_severity] : 'not stated'}
            </span>
          </div>
        </div>

        <div className="bg-stone-50/80 p-3 rounded-xl border border-[#EAE5DC] space-y-1.5">
          <div className="font-bold text-stone-800">
            Photos show <span className="font-normal text-stone-500">(best-matching of {ev.photos ?? 1})</span>
          </div>
          {sev.map((p, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="w-32 shrink-0 text-stone-700">{SEVERITY[i]}</span>
              <div className="flex-1 h-1.5 rounded-full bg-stone-200 overflow-hidden">
                <div className="h-full rounded-full bg-stone-700" style={{ width: `${Math.round(p * 100)}%` }} />
              </div>
              <span className="w-9 text-right font-mono text-stone-600">{Math.round(p * 100)}%</span>
            </div>
          ))}
          {Object.keys(loc).length > 0 && (
            <div className="font-mono text-stone-600 pt-1">
              front {Math.round((loc.front ?? 0) * 100)}% · rear {Math.round((loc.rear ?? 0) * 100)}%
            </div>
          )}
        </div>
      </div>

      <p className="text-[11px] text-stone-500 leading-relaxed">
        Zero-shot CLIP reading, confidence capped at {signal.confidence.toFixed(1)}: flags only clear contradictions and
        never decides a claim on its own.
      </p>
    </div>
  );
};
