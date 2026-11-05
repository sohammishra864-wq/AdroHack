import React, { useRef, useEffect, useState } from 'react';
import { DocResult, Signal, ApiConfig } from '../../types';
import { SignalCard } from '../SignalCard';
import { FileText, Clock, AlertCircle, CheckCircle2, Sliders } from 'lucide-react';

interface DocumentsTabProps {
  document: DocResult;
  signals: Signal[];
  config?: ApiConfig;
}

export const DocumentsTab: React.FC<DocumentsTabProps> = ({
  document: doc,
  signals,
  config,
}) => {
  const [showOcrBoxes, setShowOcrBoxes] = useState<boolean>(true);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Filter doc tier signals
  const docSignals = signals.filter((s) => s.tier === 'doc');

  // Extract evidence objects
  const ocrSignal = signals.find((s) => s.name === 'ocr_confidence_dip');
  const words = ocrSignal?.evidence?.words as
    | Array<{ text: string; conf: number; page: number; box: [number, number, number, number] }>
    | undefined;

  const pdfUpdateSignal = signals.find((s) => s.name === 'pdf_incremental_update');
  const diffRows = pdfUpdateSignal?.evidence?.diff as [string, string][] | undefined;

  const producerSignal = signals.find((s) => s.name === 'pdf_producer_mismatch');
  const metadata = producerSignal?.evidence as
    | { producer?: string; creator?: string; created?: string; modified?: string; days_between?: number }
    | undefined;

  // Collect field problem bullets from arithmetic, dates, format
  const fieldProblems: string[] = [];
  ['field_arithmetic', 'field_dates', 'field_format'].forEach((sigName) => {
    const s = signals.find((item) => item.name === sigName);
    if (s?.evidence?.problems && Array.isArray(s.evidence.problems)) {
      fieldProblems.push(...s.evidence.problems);
    }
  });

  // Health-insurance upcoding check (backend signal `medical_billing`)
  const billingSignal = signals.find((s) => s.name === 'medical_billing');
  const billingIssues: string[] = Array.isArray(billingSignal?.evidence?.issues) ? billingSignal!.evidence.issues : [];
  const billingCode: string | undefined = billingSignal?.evidence?.icd10;

  // Render Document Page Canvas with OCR word boxes
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !doc.urls.page) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = doc.urls.page;

    img.onload = () => {
      canvas.width = img.naturalWidth || 650;
      canvas.height = img.naturalHeight || 840;

      // 1. Draw page image
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

      // 2. Draw OCR word confidence boxes if available
      if (showOcrBoxes && words && words.length > 0) {
        words.forEach((w) => {
          const [x1, y1, x2, y2] = w.box;
          const boxW = x2 - x1;
          const boxH = y2 - y1;

          // Color rule: green >= 80, amber >= 60, red below
          let strokeColor = '#2e7d32'; // green
          let fillBg = 'rgba(46, 125, 50, 0.15)';
          if (w.conf < 60) {
            strokeColor = '#c62828'; // red
            fillBg = 'rgba(198, 40, 40, 0.25)';
          } else if (w.conf < 80) {
            strokeColor = '#ef6c00'; // amber
            fillBg = 'rgba(239, 108, 0, 0.2)';
          }

          ctx.fillStyle = fillBg;
          ctx.fillRect(x1, y1, boxW, boxH);

          ctx.strokeStyle = strokeColor;
          ctx.lineWidth = 1.5;
          ctx.strokeRect(x1, y1, boxW, boxH);

          // Confidence text tag
          ctx.fillStyle = strokeColor;
          ctx.font = 'bold 10px monospace';
          ctx.fillText(`${w.conf}%`, x1, Math.max(10, y1 - 3));
        });
      }
    };
  }, [doc, showOcrBoxes, words]);

  // Highlight changed characters between two strings
  const renderHighlightedDiff = (earlier: string, final: string) => {
    return (
      <div className="flex items-center gap-1 font-mono">
        <span className="text-stone-800 font-semibold">{final}</span>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Document Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-4 apple-glass-card rounded-2xl border border-[#EAE5DC] shadow-xs">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center text-blue-600 border border-blue-200">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-stone-900 flex items-center gap-2">
              {doc.name}
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono uppercase bg-stone-100 text-stone-700 font-bold border border-stone-200">
                {doc.doc_type}
              </span>
            </h3>
            <p className="text-xs text-stone-500 font-medium">
              {doc.from_ocr ? 'Text extracted from Optical Character Recognition (OCR)' : 'Text extracted from native PDF stream'}
            </p>
          </div>
        </div>

        <div className="text-xs font-mono text-stone-500 font-medium">
          timing: {doc.timing.total_s < 1 ? `${Math.round(doc.timing.total_s * 1000)} ms` : `${doc.timing.total_s.toFixed(1)} s`}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Page Render + Diff Table + Metadata */}
        <div className="lg:col-span-7 space-y-5">
          {/* Page Render Canvas */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-stone-700 uppercase tracking-wider">
                Document Render (Page 1)
              </span>
              {words && (
                <button
                  type="button"
                  onClick={() => setShowOcrBoxes(!showOcrBoxes)}
                  className="flex items-center gap-1 text-xs font-semibold text-stone-600 hover:text-stone-900 cursor-pointer pencil-hover px-2 py-0.5 rounded-lg border border-[#EAE5DC] bg-white"
                >
                  <Sliders className="w-3.5 h-3.5" />
                  <span>{showOcrBoxes ? 'Hide OCR Confidence' : 'Show OCR Confidence'}</span>
                </button>
              )}
            </div>

            <div className="bg-stone-100 p-2.5 rounded-2xl border border-[#EAE5DC] flex justify-center shadow-xs">
              <canvas
                ref={canvasRef}
                className="w-full h-auto max-h-[580px] object-contain shadow-md rounded-xl"
              />
            </div>
          </div>

          {/* Version Diff Table ("The Time Machine") - Prominent Key Demo Moment */}
          {diffRows && diffRows.length > 0 && (
            <div className="apple-glass-elevated p-5 rounded-2xl border-2 border-rose-300 shadow-md space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-rose-100 flex items-center justify-center text-rose-600">
                    <Clock className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-stone-900">
                      PDF Version History Diff ("Time Machine")
                    </h4>
                    <p className="text-xs text-rose-700 font-semibold">
                      Tampering detected: Document was incrementally updated after issue date
                    </p>
                  </div>
                </div>
                <span className="px-2.5 py-1 rounded-md text-[11px] font-bold bg-rose-100 text-rose-800 border border-rose-200">
                  REVISED TOTAL DETECTED
                </span>
              </div>

              <div className="overflow-hidden rounded-xl border border-stone-200 bg-white">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-stone-100 text-stone-700 border-b border-stone-200 font-bold">
                    <tr>
                      <th className="p-3 w-1/2">Earlier Version (Original Output)</th>
                      <th className="p-3 w-1/2">Final Version (Submitted Claim)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100">
                    {diffRows.map(([earlier, final], idx) => (
                      <tr key={idx} className="bg-white">
                        <td className="p-3 text-stone-500 bg-stone-50/70 line-through">
                          {earlier}
                        </td>
                        <td className="p-3 text-rose-700 font-bold bg-rose-50/50">
                          {final}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* PDF Metadata Table */}
          {metadata && (
            <div className="apple-glass-card p-4 rounded-xl border border-[#EAE5DC] shadow-xs space-y-2">
              <h4 className="text-xs font-bold text-stone-700 uppercase tracking-wider">
                PDF Metadata & Generation Delta
              </h4>
              <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                <div>
                  <span className="text-stone-500 block text-[11px] font-medium">Producer:</span>
                  <span className="font-mono text-stone-900 font-bold">{metadata.producer || '—'}</span>
                </div>
                <div>
                  <span className="text-stone-500 block text-[11px] font-medium">Creator Software:</span>
                  <span className="font-mono text-stone-900 font-bold">{metadata.creator || '—'}</span>
                </div>
                <div>
                  <span className="text-stone-500 block text-[11px] font-medium">Created Date:</span>
                  <span className="font-mono text-stone-900 font-semibold">{metadata.created || '—'}</span>
                </div>
                <div>
                  <span className="text-stone-500 block text-[11px] font-medium">Modified Date:</span>
                  <span className="font-mono text-stone-900 font-semibold">{metadata.modified || '—'}</span>
                </div>
                {metadata.days_between !== undefined && metadata.days_between < 0.01 && (
                  <div className="col-span-2 pt-1 border-t border-stone-100 text-emerald-700 font-bold">
                    No modification after the document was created.
                  </div>
                )}
                {metadata.days_between !== undefined && metadata.days_between >= 0.01 && (
                  <div className="col-span-2 pt-1 border-t border-stone-100 text-rose-700 font-bold">
                    ⚠️ {metadata.days_between.toFixed(2)} days elapsed between document creation and subsequent modification.
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Field Flags Bullet List */}
          {billingIssues.length > 0 && (
            <div className="bg-rose-50 p-4 rounded-xl border border-rose-200 space-y-2">
              <div className="flex items-center gap-2 text-rose-900 font-bold text-xs">
                <AlertCircle className="w-4 h-4 text-rose-600" />
                <span>Medical Billing vs Diagnosis{billingCode ? ` (ICD-10 ${billingCode})` : ''}:</span>
              </div>
              <ul className="list-disc list-inside space-y-1 text-xs text-rose-950 font-medium">
                {billingIssues.map((issue, i) => (
                  <li key={i}>{issue}</li>
                ))}
              </ul>
            </div>
          )}

          {fieldProblems.length > 0 && (
            <div className="bg-amber-50 p-4 rounded-xl border border-amber-200 space-y-2">
              <div className="flex items-center gap-2 text-amber-900 font-bold text-xs">
                <AlertCircle className="w-4 h-4 text-amber-600" />
                <span>Document Logic & Calculation Inconsistencies:</span>
              </div>
              <ul className="list-disc list-inside space-y-1 text-xs text-amber-950 font-medium">
                {fieldProblems.map((prob, i) => (
                  <li key={i}>{prob}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Right Column: Signal Cards */}
        <div className="lg:col-span-5 space-y-3">
          <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider pb-1">
            Document Analysis Cards ({docSignals.length})
          </h4>
          {docSignals.map((sig) => (
            <SignalCard key={sig.name} signal={sig} config={config} />
          ))}
        </div>
      </div>
    </div>
  );
};
