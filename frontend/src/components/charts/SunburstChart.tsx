import React, { useState } from 'react';

interface SunburstData {
  ids: string[];
  labels: string[];
  parents: string[];
  values: number[];
}

interface SunburstChartProps {
  sunburst?: SunburstData;
}

export const SunburstChart: React.FC<SunburstChartProps> = ({ sunburst }) => {
  const [hoveredNode, setHoveredNode] = useState<{ label: string; value: number } | null>(null);

  if (!sunburst || !sunburst.ids || sunburst.ids.length === 0) {
    return null;
  }

  // Leaves of the generator tree from the backend's family map (evidence.sunburst):
  // a node that is nobody's parent. Values are probabilities; slices under 0.5 % are hidden.
  const FAMILY_COLORS: Record<string, string[]> = {
    root: ['#2e7d32'],                                                    // Real
    diffusion: ['#3b82f6', '#60a5fa', '#8b5cf6', '#6366f1', '#0ea5e9', '#a78bfa'],
    edited: ['#f59e0b', '#fbbf24', '#d97706'],
  };
  const used: Record<string, number> = {};
  const parentSet = new Set(sunburst.parents);
  const segments = sunburst.ids
    .map((id, i) => ({ id, i }))
    .filter(({ id }) => id !== 'root' && !parentSet.has(id))
    .map(({ id, i }) => {
      const fam = sunburst.parents[i] || 'root';
      const palette = FAMILY_COLORS[fam] || ['#a8a29e'];
      const color = palette[(used[fam] = (used[fam] ?? -1) + 1) % palette.length];
      return { label: sunburst.labels[i], value: Math.round(sunburst.values[i] * 1000) / 10, color, family: fam };
    })
    .filter((s) => s.value >= 0.5)
    .sort((a, b) => b.value - a.value);
  if (segments.length === 0) return null;
  const dominant = segments[0];

  let cumulativeAngle = -90; // Start at top
  const total = segments.reduce((sum, s) => sum + s.value, 0);

  const radiusOuter = 80;
  const radiusInner = 48;
  const cx = 100;
  const cy = 100;

  return (
    <div className="apple-glass-card pencil-hover p-4 rounded-xl border border-stone-200/80 shadow-xs">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-xs font-bold text-stone-900 uppercase tracking-wider">
          Generator Family Attribution
        </h4>
        <span className="text-[11px] font-mono text-stone-500 font-semibold">family_map</span>
      </div>

      <div className="flex items-center justify-center gap-6">
        <div className="relative w-[150px] h-[150px] shrink-0">
          <svg viewBox="0 0 200 200" className="w-full h-full overflow-visible">
            {segments.map((seg, idx) => {
              const sliceAngle = (seg.value / total) * 360;
              const startAngle = cumulativeAngle;
              const endAngle = cumulativeAngle + sliceAngle;
              cumulativeAngle = endAngle;

              const rad1 = (startAngle * Math.PI) / 180;
              const rad2 = (endAngle * Math.PI) / 180;

              const x1Outer = cx + radiusOuter * Math.cos(rad1);
              const y1Outer = cy + radiusOuter * Math.sin(rad1);
              const x2Outer = cx + radiusOuter * Math.cos(rad2);
              const y2Outer = cy + radiusOuter * Math.sin(rad2);

              const x1Inner = cx + radiusInner * Math.cos(rad2);
              const y1Inner = cy + radiusInner * Math.sin(rad2);
              const x2Inner = cx + radiusInner * Math.cos(rad1);
              const y2Inner = cy + radiusInner * Math.sin(rad1);

              const largeArcFlag = sliceAngle > 180 ? 1 : 0;

              const pathData = `
                M ${x1Outer} ${y1Outer}
                A ${radiusOuter} ${radiusOuter} 0 ${largeArcFlag} 1 ${x2Outer} ${y2Outer}
                L ${x1Inner} ${y1Inner}
                A ${radiusInner} ${radiusInner} 0 ${largeArcFlag} 0 ${x2Inner} ${y2Inner}
                Z
              `;

              return (
                <path
                  key={idx}
                  d={pathData}
                  fill={seg.color}
                  className="transition-all duration-200 cursor-pointer hover:opacity-85 hover:scale-105 origin-center"
                  onMouseEnter={() => setHoveredNode({ label: seg.label, value: seg.value })}
                  onMouseLeave={() => setHoveredNode(null)}
                />
              );
            })}

            {/* Inner Center Label */}
            <circle cx={cx} cy={cy} r={radiusInner - 2} className="fill-stone-50" />
            <text
              x={cx}
              y={cy - 4}
              textAnchor="middle"
              className="text-xs font-bold font-mono fill-stone-900"
            >
              {hoveredNode ? `${hoveredNode.value}%` : `${dominant.value}%`}
            </text>
            <text
              x={cx}
              y={cy + 12}
              textAnchor="middle"
              className="text-[9px] uppercase tracking-wider fill-stone-500 font-sans font-semibold"
            >
              {hoveredNode ? hoveredNode.label : dominant.label}
            </text>
          </svg>
        </div>

        {/* Legend */}
        <div className="space-y-1.5 text-xs">
          {segments.map((seg, idx) => (
            <div
              key={idx}
              className="flex items-center justify-between gap-3 text-stone-800 font-medium"
            >
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: seg.color }} />
                <span>{seg.label}</span>
              </div>
              <span className="font-mono font-semibold">{seg.value}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
