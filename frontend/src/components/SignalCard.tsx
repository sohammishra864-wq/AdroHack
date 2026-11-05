import React, { useState } from 'react';
import { ChevronDown, ChevronRight, HelpCircle } from 'lucide-react';
import { Signal, ApiConfig } from '../types';
import { getFriendlyName, DEFAULT_CONFIG } from '../lib/constants';

interface SignalCardProps {
  signal: Signal;
  config?: ApiConfig;
}

export const SignalCard: React.FC<SignalCardProps> = ({ signal, config = DEFAULT_CONFIG }) => {
  const [expanded, setExpanded] = useState(false);
  const friendlyName = getFriendlyName(signal.name);

  // Band threshold evaluation for dot & score styling
  const lowMax = config.bands?.low_max ?? 0.35;
  const mediumMax = config.bands?.medium_max ?? 0.65;

  let dotColor = '#757575'; // Grey fallback
  let scoreClass = 'text-stone-700 font-mono font-bold';
  let cardBorder = 'border-[#EAE5DC] hover:border-stone-400';
  let cardBg = 'apple-glass-card';

  if (signal.score === null) {
    // Abstained or not applicable
    dotColor = '#9e9e9e';
    cardBg = 'bg-stone-50/70';
  } else if (signal.score >= mediumMax) {
    dotColor = '#c62828'; // Red
    scoreClass = 'text-rose-700 font-mono font-bold';
    cardBorder = 'border-rose-200/80 hover:border-rose-400';
  } else if (signal.score >= lowMax) {
    dotColor = '#ef6c00'; // Amber
    scoreClass = 'text-amber-700 font-mono font-bold';
    cardBorder = 'border-amber-200/80 hover:border-amber-400';
  } else {
    dotColor = '#2e7d32'; // Green
    scoreClass = 'text-emerald-700 font-mono font-bold';
    cardBorder = 'border-emerald-200/80 hover:border-emerald-400';
  }

  // Filter evidence keys: hide 'error' unless card abstained
  const evidenceEntries = Object.entries(signal.evidence || {}).filter(([key]) => {
    if (key === 'error') return signal.abstained;
    if (key === 'sunburst') return false; // Rendered in dedicated sunburst chart
    return true;
  });

  return (
    <div
      className={`rounded-2xl border p-4 text-left transition-all shadow-xs pencil-hover ${cardBorder} ${cardBg}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span
            className="w-2.5 h-2.5 rounded-full shrink-0 shadow-xs"
            style={{ backgroundColor: dotColor }}
            aria-hidden="true"
          />
          <h4 className="font-bold text-sm tracking-tight text-stone-900">
            {friendlyName}
          </h4>
        </div>

        <div className="text-right text-xs shrink-0">
          {signal.score !== null ? (
            <span className={scoreClass}>
              {signal.score.toFixed(2)}{' '}
              <span className="text-stone-500 font-medium">
                · conf {signal.confidence.toFixed(2)}
              </span>
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-stone-600 bg-stone-100 px-2 py-0.5 rounded-md border border-stone-200">
              <HelpCircle className="w-3 h-3 text-stone-500" />
              {signal.applicable === false ? 'not applicable' : 'left out'}
            </span>
          )}
        </div>
      </div>

      {/* Verbatim reason */}
      <p className="mt-2 text-xs leading-relaxed text-stone-700 font-normal">
        {signal.reason}
      </p>

      {/* Collapsible evidence */}
      {evidenceEntries.length > 0 && (
        <div className="mt-2.5 pt-2 border-t border-stone-200/60">
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-[11px] font-semibold text-stone-500 hover:text-stone-800 transition-colors cursor-pointer"
          >
            {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            <span>{expanded ? 'Hide details' : 'Details (evidence)'}</span>
          </button>

          {expanded && (
            <div className="mt-2 rounded-xl bg-stone-50/80 p-3 text-[11px] font-mono border border-[#EAE5DC]">
              <div className="space-y-1.5 overflow-x-auto">
                {evidenceEntries.map(([key, val]) => (
                  <div key={key} className="flex items-start justify-between gap-4">
                    <span className="text-stone-600 font-semibold">{key}:</span>
                    <span className="text-stone-900 font-bold text-right truncate max-w-[220px]">
                      {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
