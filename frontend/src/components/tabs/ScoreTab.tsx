import React, { useState } from 'react';
import { ClaimScore, Signal, ApiConfig, AuditRecord } from '../../types';
import { GaugeChart } from '../charts/GaugeChart';
import { WaterfallChart } from '../charts/WaterfallChart';
import { SignalCard } from '../SignalCard';
import { BandChip } from '../BandChip';
import { LinkedClaimsPanel } from '../LinkedClaimsPanel';
import { DamageStoryPanel } from '../DamageStoryPanel';
import { api } from '../../lib/api';
import { Check, X, AlertTriangle, ShieldCheck, Send, MessageSquareQuote } from 'lucide-react';

interface ScoreTabProps {
  caseId: string;
  claim: ClaimScore;
  narrative: { text: string; source: 'template' | 'llm' };
  signals: Signal[];
  history: AuditRecord[];
  onDecisionSubmitted: () => void;
  config?: ApiConfig;
}

export const ScoreTab: React.FC<ScoreTabProps> = ({
  caseId,
  claim,
  narrative,
  signals,
  history,
  onDecisionSubmitted,
  config,
}) => {
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  // Claim-level signals (tier: 'claim')
  const claimSignals = signals.filter((s) => s.tier === 'claim');

  // Lane scores string: "image 0.78 · document 0.66 · identity 0.12" (hide null lanes)
  const laneItems: string[] = [];
  if (claim.image_score !== null) laneItems.push(`image ${claim.image_score.toFixed(2)}`);
  if (claim.document_score !== null) laneItems.push(`document ${claim.document_score.toFixed(2)}`);
  if (claim.identity_score !== null) laneItems.push(`identity ${claim.identity_score.toFixed(2)}`);
  const laneScoreString = laneItems.join(' · ');

  const handleDecision = async (action: 'accept' | 'reject' | 'escalate') => {
    setSubmitting(true);
    setStatusMessage(null);
    try {
      await api.postDecision(caseId, action, note || `Decision: ${action}`);
      setNote('');
      setStatusMessage(`Decision recorded: ${action.toUpperCase()}`);
      onDecisionSubmitted();
    } catch (err: any) {
      setStatusMessage(`Failed: ${err.message || 'Error recording decision'}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Overview: Gauge + Lane Summary */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-center">
        <div className="md:col-span-5 flex justify-center">
          <GaugeChart
            overall={claim.overall}
            band={claim.band}
            config={config}
            pendingDeep={claim.pending_deep}
          />
        </div>

        <div className="md:col-span-7 space-y-3">
          <div className="apple-glass-card p-5 rounded-2xl border border-[#EAE5DC] shadow-xs space-y-2">
            <h4 className="text-xs font-bold text-stone-700 uppercase tracking-wider">
              Lane Decomposition
            </h4>
            <div className="text-sm font-mono font-bold text-stone-900">
              {laneScoreString || 'No lane scores available'}
            </div>
            <p className="text-xs text-stone-600">
              Composite score derived from multi-modal image forensics, PDF structure diffs, and identity verification.
            </p>
          </div>

          {/* Narrative Explanation Callout */}
          <div className="bg-stone-50/80 p-4 rounded-2xl border border-[#EAE5DC] space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-stone-800 flex items-center gap-1.5">
                <MessageSquareQuote className="w-4 h-4 text-blue-600" /> Executive Explanation
              </span>
              <span className="text-[10px] text-stone-500 font-mono font-medium">
                {narrative.source === 'llm'
                  ? 'LLM rewrite of the template (numbers checked)'
                  : 'Written from a template'}
              </span>
            </div>
            <p className="text-xs text-stone-700 leading-relaxed font-sans">
              {narrative.text}
            </p>
          </div>
        </div>
      </div>

      {/* Waterfall Chart */}
      <WaterfallChart waterfall={claim.waterfall} overall={claim.overall} />

      {/* Claim-Level Signals (Cross-Check Verification) */}
      {claimSignals.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-xs font-bold text-stone-700 uppercase tracking-wider pb-1">
            Claim-Level Coherence Checks ({claimSignals.length})
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {claimSignals.map((sig) => (
              <SignalCard key={sig.name} signal={sig} config={config} />
            ))}
          </div>
        </div>
      )}

      {/* Fraud-ring memory + story-vs-photo detail (new checks) */}
      <LinkedClaimsPanel signal={claimSignals.find((s) => s.name === 'cross_claim')} />
      <DamageStoryPanel signal={claimSignals.find((s) => s.name === 'damage_story')} />

      {/* Adjuster Decision Panel */}
      <div className="apple-glass-elevated p-6 rounded-3xl border border-[#EAE5DC] shadow-md space-y-4">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-bold text-stone-900 flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-stone-800" />
            Adjuster Review Decision
          </h4>
          {statusMessage && (
            <span className="text-xs font-bold text-emerald-700">
              {statusMessage}
            </span>
          )}
        </div>

        <div className="space-y-2">
          <label className="text-xs font-bold text-stone-700 block">
            Reviewer Note / Justification (saved to audit trail):
          </label>
          <textarea
            rows={2}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Add explanation for acceptance, rejection reason, or specific escalate notes..."
            className="w-full text-xs p-3 rounded-xl border border-[#EAE5DC] bg-white text-stone-900 placeholder-stone-400 pencil-hover focus:outline-hidden focus:ring-2 focus:ring-stone-400 font-sans"
          />
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button
            type="button"
            disabled={submitting}
            onClick={() => handleDecision('accept')}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-full font-bold text-xs text-white bg-[#2e7d32] hover:bg-[#256629] apple-btn pencil-hover shadow-xs disabled:opacity-50"
          >
            <Check className="w-4 h-4" />
            Accept Claim (Payout)
          </button>

          <button
            type="button"
            disabled={submitting}
            onClick={() => handleDecision('reject')}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-full font-bold text-xs text-white bg-[#c62828] hover:bg-[#a81f1f] apple-btn pencil-hover shadow-xs disabled:opacity-50"
          >
            <X className="w-4 h-4" />
            Reject Claim (Fraud Flag)
          </button>

          <button
            type="button"
            disabled={submitting}
            onClick={() => handleDecision('escalate')}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-full font-bold text-xs text-white bg-[#ef6c00] hover:bg-[#cc5c00] apple-btn pencil-hover shadow-xs disabled:opacity-50"
          >
            <AlertTriangle className="w-4 h-4" />
            Escalate to SIU / Special Inv.
          </button>
        </div>
      </div>

      {/* Audit History Table */}
      <div className="apple-glass-card p-5 rounded-2xl border border-[#EAE5DC] shadow-xs space-y-3">
        <h4 className="text-xs font-bold text-stone-700 uppercase tracking-wider">
          Immutable Audit History
        </h4>
        {history.length === 0 ? (
          <p className="text-xs text-stone-500 py-2">No prior decisions recorded on this claim.</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-stone-200 bg-white">
            <table className="w-full text-left text-xs">
              <thead className="bg-stone-100 text-stone-700 border-b border-stone-200 font-mono font-bold">
                <tr>
                  <th className="p-2.5">Reviewer</th>
                  <th className="p-2.5">Action</th>
                  <th className="p-2.5">Band</th>
                  <th className="p-2.5">Note</th>
                  <th className="p-2.5 text-right">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100 font-mono">
                {history.map((row, idx) => (
                  <tr key={idx} className="hover:bg-stone-50 transition-colors">
                    <td className="p-2.5 font-bold text-stone-900">
                      {row.reviewer}
                    </td>
                    <td className="p-2.5">
                      <span
                        className={`inline-block px-2 py-0.5 rounded-sm font-bold uppercase text-[10px] ${
                          row.action === 'accept'
                            ? 'bg-emerald-100 text-emerald-800'
                            : row.action === 'reject'
                            ? 'bg-rose-100 text-rose-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {row.action}
                      </span>
                    </td>
                    <td className="p-2.5">
                      <BandChip band={row.band} size="sm" />
                    </td>
                    <td className="p-2.5 text-stone-700 font-sans max-w-xs truncate font-medium">
                      {row.note}
                    </td>
                    <td className="p-2.5 text-right font-mono text-stone-500 text-[11px] font-medium">
                      {new Date(row.ts).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
