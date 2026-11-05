import React from 'react';
import { Link2 } from 'lucide-react';
import { Signal } from '../types';

// Fraud-ring memory: earlier claims that share a photo, VIN, repair shop / hospital, claimant or
// the same hospital stay with this one (backend signal `cross_claim`, evidence.links).
interface LinkRow {
  kind: 'photo' | 'vin' | 'vendor' | 'claimant' | 'stay';
  value: string;
  case_id: string;
  ts: string;
}

const KIND_LABEL: Record<LinkRow['kind'], string> = {
  photo: 'Same photo (or a resized / recompressed copy)',
  vin: 'Same VIN',
  vendor: 'Same repair shop / hospital',
  claimant: 'Same claimant name',
  stay: 'Same hospital stay',
};

// Show what helps the reviewer, never a name or a full VIN in the clear.
function shown(row: LinkRow): string {
  if (row.kind === 'vendor') return row.value;
  if (row.kind === 'vin') return `•••${row.value.slice(-6)}`;
  return '—';
}

export const LinkedClaimsPanel: React.FC<{ signal?: Signal }> = ({ signal }) => {
  const links: LinkRow[] = Array.isArray(signal?.evidence?.links) ? signal!.evidence.links : [];
  if (!signal || signal.applicable === false) return null;

  return (
    <div className="apple-glass-card p-5 rounded-2xl border border-[#EAE5DC] shadow-xs space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-bold text-stone-700 uppercase tracking-wider flex items-center gap-1.5">
          <Link2 className="w-4 h-4 text-stone-700" />
          Linked Claims · Fraud-Ring Memory
        </h4>
        <span className="text-[10px] text-stone-500 font-mono font-medium">
          stored as SHA-256 hashes · last 180 days
        </span>
      </div>
      {links.length === 0 ? (
        <p className="text-xs text-stone-500 py-2">
          No earlier claim shares this claim's photos, VIN, repair shop, claimant or hospital stay.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-stone-200 bg-white">
          <table className="w-full text-left text-xs">
            <thead className="bg-stone-100 text-stone-700 border-b border-stone-200 font-mono font-bold">
              <tr>
                <th className="p-2.5">Earlier claim</th>
                <th className="p-2.5">What is shared</th>
                <th className="p-2.5">Detail</th>
                <th className="p-2.5 text-right">Seen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100 font-mono">
              {links.map((row, idx) => (
                <tr key={idx} className="hover:bg-stone-50 transition-colors">
                  <td className="p-2.5 font-bold text-stone-900">{row.case_id}</td>
                  <td className="p-2.5">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-sm font-bold uppercase text-[10px] ${
                        row.kind === 'photo' || row.kind === 'stay'
                          ? 'bg-rose-100 text-rose-800'
                          : row.kind === 'vin'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-stone-100 text-stone-700'
                      }`}
                    >
                      {KIND_LABEL[row.kind] ?? row.kind}
                    </span>
                  </td>
                  <td className="p-2.5 text-stone-700 font-sans max-w-xs truncate font-medium">{shown(row)}</td>
                  <td className="p-2.5 text-right font-mono text-stone-500 text-[11px] font-medium">
                    {new Date(row.ts).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
