import React, { useState, useEffect } from 'react';
import { api } from '../lib/api';
import { BarChart3, ShieldCheck, Zap, AlertCircle } from 'lucide-react';

export const ReportsPage: React.FC = () => {
  const [heldoutData, setHeldoutData] = useState<any>(null);
  const [evalMarkdown, setEvalMarkdown] = useState<string>('');
  const [latencyMarkdown, setLatencyMarkdown] = useState<string>('');
  const [billingMarkdown, setBillingMarkdown] = useState<string>('');
  const [storyMarkdown, setStoryMarkdown] = useState<string>('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchReports = async () => {
      try {
        const heldout = await api.getHeldoutReport();
        const evalMd = await api.getReportMarkdown('eval');
        const latencyMd = await api.getReportMarkdown('latency');
        // newer checks: measured on the HPC; each card simply stays empty if its report is missing
        setBillingMarkdown(await api.getReportMarkdown('medical_billing').catch(() => ''));
        setStoryMarkdown(await api.getReportMarkdown('damage_story').catch(() => ''));
        setHeldoutData(heldout);
        setEvalMarkdown(evalMd);
        setLatencyMarkdown(latencyMd);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetchReports();
  }, []);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 text-center text-xs text-zinc-400">
        Loading evaluation benchmarks…
      </div>
    );
  }

  const families = heldoutData?.families || {};
  const robustness = heldoutData?.robustness || {};

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#FAF8F5] text-stone-900 py-8 px-4 sm:px-6">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold bg-blue-50 text-blue-800 border border-blue-200">
            <BarChart3 className="w-3.5 h-3.5" /> Empirical Evaluation & Benchmarks
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-stone-900 mt-2">
            Model Generalization & Robustness Reports
          </h1>
          <p className="text-xs text-stone-500 max-w-2xl leading-relaxed">
            Comprehensive held-out evaluation across modern generator architectures, compression channels, and inference latencies.
          </p>
        </div>

        {/* 1. Generator Family Held-out Table (§ 7.9) */}
        <div className="apple-glass-elevated p-6 rounded-3xl border border-[#EAE5DC] shadow-md space-y-4">
          <h3 className="text-sm font-bold text-stone-900 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            Detection by Generator Family (Held-out Test Set)
          </h3>

          <div className="overflow-x-auto rounded-2xl border border-stone-200 bg-white shadow-xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-stone-100 text-stone-700 font-mono border-b border-stone-200 font-bold">
                <tr>
                  <th className="p-3.5">Generator Family</th>
                  <th className="p-3.5 text-right">Samples (n)</th>
                  <th className="p-3.5 text-right">AUC</th>
                  <th className="p-3.5 text-right">TPR @ 1% FPR</th>
                  <th className="p-3.5 text-right">Flagged HIGH</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100 font-mono">
                {Object.entries(families).map(([famKey, val]: [string, any]) => {
                  let noteLabel = null;
                  if (famKey === 'flux') {
                    noteLabel = (
                      <span className="ml-2 text-[10px] font-sans px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-900 border border-amber-300 font-semibold">
                        Flux: never trained or calibrated on
                      </span>
                    );
                  } else if (famKey === 'gan') {
                    noteLabel = (
                      <span className="ml-2 text-[10px] font-sans px-2.5 py-0.5 rounded-full bg-stone-200 text-stone-800 border border-stone-300 font-semibold">
                        GAN: eval-only (reconstruction blind spot)
                      </span>
                    );
                  }

                  return (
                    <tr key={famKey} className="hover:bg-stone-50/80 transition-colors">
                      <td className="p-3.5 font-bold font-sans text-stone-900 flex items-center">
                        <span className="uppercase tracking-wide">{famKey}</span>
                        {noteLabel}
                      </td>
                      <td className="p-3.5 text-right text-stone-700 font-medium">{val.n}</td>
                      <td className="p-3.5 text-right font-extrabold text-stone-950">
                        {val.auc.toFixed(3)}
                      </td>
                      <td className="p-3.5 text-right text-emerald-700 font-bold">
                        {(val.tpr_at_1fpr * 100).toFixed(1)}%
                      </td>
                      <td className="p-3.5 text-right text-rose-700 font-bold">
                        {val.flagged_high}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* 2. Robustness Row (§ 7.9) */}
        <div className="apple-glass-elevated p-6 rounded-3xl border border-[#EAE5DC] shadow-md space-y-4">
          <h3 className="text-sm font-bold text-stone-900 flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-500" />
            Robustness Across Image Degradation Channels (AUC)
          </h3>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 font-mono text-center">
            {Object.entries(robustness).map(([qual, auc]: [string, any]) => (
              <div
                key={qual}
                className="p-3.5 rounded-2xl bg-white border border-[#EAE5DC] shadow-xs pencil-hover"
              >
                <span className="text-[11px] text-stone-500 font-bold block uppercase tracking-wider">{qual}</span>
                <span className="text-lg font-extrabold text-stone-900 block mt-1">
                  {Number(auc).toFixed(3)}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* 3. Eval & Latency Markdown Sections */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
          <div className="apple-glass-card p-6 rounded-3xl border border-[#EAE5DC] shadow-md space-y-3">
            <h4 className="text-xs font-bold text-stone-700 uppercase tracking-wider">
              Evaluation Details (eval_latest.md)
            </h4>
            <div className="prose prose-sm max-w-none text-xs leading-relaxed whitespace-pre-line font-sans text-stone-800">
              {evalMarkdown || 'Not measured yet: run make eval.'}
            </div>
          </div>

          <div className="apple-glass-card p-6 rounded-3xl border border-[#EAE5DC] shadow-md space-y-3">
            <h4 className="text-xs font-bold text-stone-700 uppercase tracking-wider">
              Latency Benchmark (latency_latest.md)
            </h4>
            <div className="prose prose-sm max-w-none text-xs leading-relaxed whitespace-pre-line font-sans text-stone-800">
              {latencyMarkdown || 'Not measured yet: run make bench.'}
            </div>
          </div>
        </div>

        {/* 4. Newer checks: health-insurance billing + damage vs story */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
          <div className="apple-glass-card p-6 rounded-3xl border border-[#EAE5DC] shadow-md space-y-3">
            <h4 className="text-xs font-bold text-stone-700 uppercase tracking-wider">
              Medical Billing Check (medical_billing.md)
            </h4>
            <div className="prose prose-sm max-w-none text-xs leading-relaxed whitespace-pre-line font-sans text-stone-800">
              {billingMarkdown || 'Not measured yet: run scripts/eval_medical.py.'}
            </div>
          </div>

          <div className="apple-glass-card p-6 rounded-3xl border border-[#EAE5DC] shadow-md space-y-3">
            <h4 className="text-xs font-bold text-stone-700 uppercase tracking-wider">
              Damage vs Story Check (damage_story.md)
            </h4>
            <div className="prose prose-sm max-w-none text-xs leading-relaxed whitespace-pre-line font-sans text-stone-800">
              {storyMarkdown || 'Not measured yet: run scripts/eval_damage_story.py.'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
